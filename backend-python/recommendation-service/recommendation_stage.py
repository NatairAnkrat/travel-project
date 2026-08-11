"""Recommendation stage: turns flight offers + hotel offers + user
preferences into complete, bookable itineraries via Claude.

This is the third stage of the pipeline (flights -> hotels -> this).
Mirrors flight_stage/hotel_stage in spirit: a plain function that takes
already-fetched data and returns a plain result, no CLI/print/file I/O -
easy to wrap in a Celery task or call directly from a script.
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from itertools import combinations
from math import atan2, cos, radians, sin, sqrt

from clients.claude_itinerary_client import TIERS, ClaudeItineraryClient, ItineraryGenerationError
from clients.search_service_client import SearchServiceClient
from itinerary_schemas import (
    FlightSelection, GroupInput, GroupPriceBreakdown, HotelSelection, ItineraryProposal,
    ScheduleItemType, TripPlanningRequest,
)
from preference_filter import apply_filter_for_prompt, filter_preferences

MAX_HOTEL_DISTANCE_KM = 1.5 # mirrors the system prompt's proximity rule
MAX_VENUE_DISTANCE_KM = 10.0 # meal/activity items should normally stay within this of the group's hotel
MIN_HOTEL_RATING = 3.5 # default quality bar; only relaxed if nothing else fits budget
REAL_PLACE_MATCH_TOLERANCE_DEG = 0.0002  # ~15-20m - float rounding slack, not "close enough to be a different place"
TIMING_GAP_TOLERANCE_MINUTES = 10  # slack for rounding before a gap is flagged as unexplained


@dataclass
class RunResult:
    """run()'s return value: the validated proposal, plus every real place
    found per option during generation. found_places_by_option is what
    _validate_places_are_real (below) checks the final schedule items
    against, to catch a place Claude recalled from training data instead
    of actually finding via search_nearby_places. Exposed on the return
    value (not just used internally) so a future caller can reuse the
    same real-place data for other purposes without a second search.
    """
    proposal: ItineraryProposal
    found_places_by_option: dict[int, list[dict]]


def run(
    groups: list[GroupInput],
    user_preferences: str,
    travel_pace: str,
    flight_offers: list[dict],
    hotel_offers: list[dict],
    client: ClaudeItineraryClient | None = None,
    search_client: SearchServiceClient | None = None,
) -> RunResult:
    filtered_prefs = filter_preferences(user_preferences)
    for dropped in filtered_prefs.dropped:
        print(f"[info] Preference dropped (not groundable): '{dropped.text}' - {dropped.reason}")
    cleaned_preferences = apply_filter_for_prompt(filtered_prefs, user_preferences)

    groups = [_clean_group_preferences(group) for group in groups]

    filtered_hotel_offers = _filter_quality_hotels(hotel_offers, groups)

    request = TripPlanningRequest(
        groups=groups,
        user_preferences=cleaned_preferences,
        travel_pace=travel_pace,
        flight_offers=flight_offers,
        hotel_offers=filtered_hotel_offers,
    )

    itinerary_client = client or ClaudeItineraryClient()

    options = []
    found_places_by_option: dict[int, list[dict]] = {}
    for option_id, tier in enumerate(TIERS, start=1):
        try:
            result = itinerary_client.generate_option(request, tier)
        except ItineraryGenerationError as exc:
            # One tier failing shouldn't sink the whole trip plan - log
            # and continue, so the person still gets whatever tiers did
            # succeed instead of nothing at all.
            print(f"[warning] Tier '{tier.name}' failed to generate: {exc}")
            continue

        option = result.option

        # Force the id/summary to reflect the tier reliably, rather than
        # trusting Claude to fill option_id consistently across separate
        # calls that can't see each other's output.
        option.option_id = option_id
        if tier.name.lower() not in option.summary.lower():
            option.summary = f"[{tier.name}] {option.summary}"

        options.append(option)
        found_places_by_option[option_id] = result.found_places

    if not options:
        raise ItineraryGenerationError("All itinerary options failed to generate")

    for option in options:
        _compute_price_breakdowns(option, groups)

    proposal = ItineraryProposal(options=options)

    resolved_search_client = search_client or SearchServiceClient()
    _fetch_baggage_info(proposal, flight_offers, resolved_search_client)
    _fetch_hotel_addresses(proposal, filtered_hotel_offers, groups, resolved_search_client)

    _validate_budgets(proposal, groups)
    _validate_hotel_proximity(proposal)
    _validate_places_are_real(proposal, found_places_by_option)
    _validate_transitions(proposal)
    _validate_schedule_timing(proposal)
    _validate_realistic_distances(proposal)
    _validate_shared_activities(proposal)
    return RunResult(proposal=proposal, found_places_by_option=found_places_by_option)


def _clean_group_preferences(group: GroupInput) -> GroupInput:
    """Runs a group's own preferences through the same cheap not-groundable
    filter as the trip-wide user_preferences (see preference_filter.py) -
    a group-specific request can be just as unsatisfiable as a trip-wide
    one (e.g. "our room must smell like lavender"), and would otherwise
    burn tool-use rounds in the same way.
    """
    if not group.preferences or not group.preferences.strip():
        return group

    filtered = filter_preferences(group.preferences)
    for dropped in filtered.dropped:
        print(f"[info] Group {group.group_id} preference dropped (not groundable): '{dropped.text}' - {dropped.reason}")
    cleaned = apply_filter_for_prompt(filtered, group.preferences)
    return group.model_copy(update={"preferences": cleaned})


def _filter_quality_hotels(hotel_offers: list[dict], groups: list[GroupInput]) -> list[dict]:
    """Keeps only well-rated hotel offers (>= MIN_HOTEL_RATING) per group by
    default. If a group has no well-rated offers at all within whatever
    budget filtering already happened upstream, falls back to including the
    lower-rated ones for that group rather than leaving it with nothing to
    choose from - and tags those with quality_fallback so the prompt (and
    a human reading the final plan) knows quality had to be compromised.
    """
    by_group: dict[int, list[dict]] = defaultdict(list)
    for offer in hotel_offers:
        group_id = _safe_int(offer.get("group_id"))
        if group_id is not None:
            by_group[group_id].append(offer)

    result: list[dict] = []
    for group in groups:
        candidates = by_group.get(group.group_id, [])
        well_rated = [o for o in candidates if (_safe_float(o.get("overall_rating")) or 0) >= MIN_HOTEL_RATING]

        if well_rated:
            result.extend(well_rated)
        elif candidates:
            print(f"[warning] Group {group.group_id}: no hotel offers rated >= {MIN_HOTEL_RATING} "
                  f"within budget - falling back to lower-rated options")
            for offer in candidates:
                offer = {**offer, "quality_fallback": True}
                result.append(offer)

    return result


def _safe_float(value) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _safe_int(value) -> int | None:
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _compute_price_breakdowns(option, groups: list[GroupInput]) -> None:
    """Overwrites option.price_breakdown entirely, computed from the actual
    cost_eur on every schedule item plus the chosen flight/hotel offers -
    the same "don't trust the model's arithmetic, verify it" approach
    already used for place-reality and hotel-proximity checks elsewhere in
    this file. Claude's own price_breakdown numbers (its first draft) are
    discarded here rather than merely flagged, because unlike "is this
    plan over budget" (a yes/no fact worth double-checking), the
    per-category totals are pure arithmetic over data we already have in
    full - there's no reason to trust a second, independently-typed copy
    of the same numbers over summing the real line items ourselves.
    """
    flights_by_group = {f.group_id: f.price_eur for f in option.flight_selections}
    hotels_by_group = {h.group_id: h.price_eur for h in option.hotel_selections}
    budgets_by_group = {g.group_id: g.budget_max for g in groups}
    group_ids = {g.group_id for g in groups}

    meals_by_group: dict[int, float] = defaultdict(float)
    activities_by_group: dict[int, float] = defaultdict(float)
    transport_by_group: dict[int, float] = defaultdict(float)

    for day in option.days:
        for item in day.items:
            if item.type not in (ScheduleItemType.MEAL, ScheduleItemType.ACTIVITY, ScheduleItemType.TRANSPORT):
                continue
            target_group_ids = item.applies_to_group_ids or list(group_ids)
            for group_id in target_group_ids:
                if item.type == ScheduleItemType.MEAL:
                    meals_by_group[group_id] += item.cost_eur
                elif item.type == ScheduleItemType.ACTIVITY:
                    activities_by_group[group_id] += item.cost_eur
                else:
                    transport_by_group[group_id] += item.cost_eur

    recomputed: list[GroupPriceBreakdown] = []
    for group_id in sorted(group_ids):
        flights_cost = round(flights_by_group.get(group_id, 0.0), 2)
        hotel_cost = round(hotels_by_group.get(group_id, 0.0), 2)
        activities_cost = round(activities_by_group.get(group_id, 0.0), 2)
        meals_cost = round(meals_by_group.get(group_id, 0.0), 2)
        local_transport_cost = round(transport_by_group.get(group_id, 0.0), 2)
        total_cost = round(flights_cost + hotel_cost + activities_cost + meals_cost + local_transport_cost, 2)
        budget = budgets_by_group.get(group_id)

        recomputed.append(GroupPriceBreakdown(
            group_id=group_id, flights_cost=flights_cost, hotel_cost=hotel_cost,
            activities_cost=activities_cost, meals_cost=meals_cost,
            local_transport_cost=local_transport_cost, total_cost=total_cost,
            budget_max=budget, within_budget=(budget is None or total_cost <= budget),
        ))

    option.price_breakdown = recomputed


def _fetch_baggage_info(proposal: ItineraryProposal, flight_offers: list[dict], search_client: SearchServiceClient) -> None:
    """Looks up real baggage pricing for each option's chosen flight - one
    extra SerpApi call (via search-service) per flight_selection, done only
    for the options that made it into the final proposal, not every offer
    that was ever searched.

    FlightSelection doesn't carry the flight_offers entry's booking_token
    (see itinerary_schemas.FlightSelection) - an opaque token isn't the
    kind of field worth trusting Claude to copy verbatim across a
    multi-step tool-use conversation, unlike booking_url. So this matches
    each selection back to its source offer by group_id + closest price
    instead, the same "recover it from data we already have" approach as
    the booking_url on the search results page.
    """
    for option in proposal.options:
        for selection in option.flight_selections:
            offer = _match_flight_offer(selection, flight_offers)
            if offer is None or not offer.get("booking_token"):
                selection.baggage_info = "unavailable"
                print(
                    f"[warning] Option {option.option_id}, group {selection.group_id}: could not match "
                    f"flight selection (price={selection.price_eur}) back to a source offer with a "
                    f"booking_token - skipping baggage lookup"
                )
                continue

            selection.baggage_info = search_client.fetch_baggage_price(
                origin=offer.get("origin_airport", ""),
                destination=offer.get("destination_airport", ""),
                departure_date=offer.get("outbound_date", ""),
                booking_token=offer["booking_token"],
                return_date=offer.get("return_date"),
            )


def _match_flight_offer(selection: FlightSelection, flight_offers: list[dict]) -> dict | None:
    candidates = [
        offer for offer in flight_offers
        if offer.get("group_id") == selection.group_id and offer.get("status") == "ok"
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda offer: abs((offer.get("price") or 0.0) - selection.price_eur))


def _fetch_hotel_addresses(
    proposal: ItineraryProposal, hotel_offers: list[dict], groups: list[GroupInput], search_client: SearchServiceClient,
) -> None:
    """Looks up the real street address for each option's chosen hotel -
    one extra SerpApi call (via search-service) per hotel_selection, done
    only for the hotels that made it into the final proposal. Replaces the
    old approach of fetching details for the single cheapest in-budget
    property per group/date-range up front in search-service - that offer
    was frequently not the one Claude actually picked, so most lookups
    were wasted and Claude's chosen hotels often had no real address at all.

    Matches each selection back to its source offer by group_id +
    latitude/longitude, since the system prompt requires Claude to copy
    those exactly from the offer (unlike the address itself, which Claude
    otherwise just wrote from context - see HotelSelection.address).
    """
    adults_by_group = {g.group_id: g.adults for g in groups}
    children_by_group = {g.group_id: g.children for g in groups}

    for option in proposal.options:
        for selection in option.hotel_selections:
            offer = _match_hotel_offer(selection, hotel_offers)
            if offer is None or not offer.get("property_token"):
                print(
                    f"[warning] Option {option.option_id}, group {selection.group_id}: could not match "
                    f"hotel selection ('{selection.hotel_name}') back to a source offer with a "
                    f"property_token - address is whatever Claude wrote, not independently verified"
                )
                continue

            real_address = search_client.fetch_property_address(
                property_token=offer["property_token"],
                location=offer.get("location", ""),
                check_in_date=offer.get("check_in_date", ""),
                check_out_date=offer.get("check_out_date", ""),
                adults=adults_by_group.get(selection.group_id, 1),
                children=children_by_group.get(selection.group_id, 0),
            )
            if real_address:
                selection.address = real_address


def _match_hotel_offer(selection: HotelSelection, hotel_offers: list[dict]) -> dict | None:
    for offer in hotel_offers:
        if offer.get("group_id") != selection.group_id or offer.get("status") != "ok":
            continue
        lat, lon = offer.get("latitude"), offer.get("longitude")
        if lat is None or lon is None:
            continue
        if (abs(lat - selection.latitude) <= REAL_PLACE_MATCH_TOLERANCE_DEG
                and abs(lon - selection.longitude) <= REAL_PLACE_MATCH_TOLERANCE_DEG):
            return offer
    return None


def _validate_budgets(proposal: ItineraryProposal, groups: list[GroupInput]) -> None:
    """Now just a final report/log pass, since _compute_price_breakdowns
    already made within_budget correct by construction - this only prints
    a visible warning for anything over budget, for whoever is watching
    the logs/monitoring.
    """
    for option in proposal.options:
        for breakdown in option.price_breakdown:
            if not breakdown.within_budget:
                print(
                    f"[warning] Option {option.option_id}, group {breakdown.group_id}: "
                    f"total {breakdown.total_cost:.2f} EUR exceeds budget {breakdown.budget_max:.2f} EUR"
                )


def _validate_places_are_real(proposal: ItineraryProposal, found_places_by_option: dict[int, list[dict]]) -> None:
    """Post-hoc check that every meal/activity item's coordinates actually
    match a real result search_nearby_places returned during that same
    option's generation - not just "has some coordinates" (which
    _validate_realistic_distances already checks), but "these exact
    coordinates came from a real tool call, not from Claude's memory".

    This is what would have caught a long-closed venue Claude recalled
    from training data instead of finding via the tool: a hallucinated or
    recalled place has no matching entry in found_places_by_option, even
    if Claude filled in plausible-looking coordinates for it.

    Matches on coordinates (within REAL_PLACE_MATCH_TOLERANCE_DEG) rather
    than on name string equality, because tool results and the schema
    field are supposed to carry the exact same lat/lon by construction
    (see the system prompt's "copy their exact ... latitude, and
    longitude" instruction) - coordinate matching also avoids false
    negatives from minor name formatting differences (e.g. umlauts,
    trailing "GmbH").
    """
    for option in proposal.options:
        real_places = found_places_by_option.get(option.option_id, [])

        for day in option.days:
            for item in day.items:
                if item.type.value not in ("meal", "activity"):
                    continue
                if item.latitude is None or item.longitude is None:
                    continue  # already flagged by _validate_realistic_distances

                if not _matches_any_real_place(item.latitude, item.longitude, real_places):
                    print(
                        f"[warning] Option {option.option_id}, day {day.day_number}: "
                        f"'{item.title}' at ({item.latitude}, {item.longitude}) does not match any "
                        f"real result returned by search_nearby_places during this option's "
                        f"generation - likely recalled from training data rather than actually "
                        f"searched. Verify this place still exists before showing it to the user."
                    )


def _matches_any_real_place(latitude: float, longitude: float, real_places: list[dict]) -> bool:
    for place in real_places:
        place_lat, place_lon = place.get("latitude"), place.get("longitude")
        if place_lat is None or place_lon is None:
            continue
        if (abs(place_lat - latitude) <= REAL_PLACE_MATCH_TOLERANCE_DEG
                and abs(place_lon - longitude) <= REAL_PLACE_MATCH_TOLERANCE_DEG):
            return True
    return False


def _validate_realistic_distances(proposal: ItineraryProposal) -> None:
    """Post-hoc check using REAL coordinates now that meal/activity items
    carry them (from search_nearby_places results), instead of trusting
    Claude's prose description of how far something is.

    Compares each meal/activity item against the NEAREST of its
    neighboring stops in that group's day (the item right before or right
    after it - hotel counts as the anchor for the first/last stop of the
    day), not always the hotel. A restaurant between a morning activity
    and an afternoon one can legitimately be far from the hotel while
    still being exactly the right choice - see _find_anchor_coords.
    """
    for option in proposal.options:
        hotel_by_group = {h.group_id: h for h in option.hotel_selections}
        group_ids = {h.group_id for h in option.hotel_selections}

        for day in option.days:
            for group_id in group_ids:
                relevant_items = [
                    item for item in day.items
                    if not item.applies_to_group_ids or group_id in item.applies_to_group_ids
                ]
                relevant_items.sort(key=lambda item: item.time)
                hotel = hotel_by_group.get(group_id)

                for idx, item in enumerate(relevant_items):
                    if item.type not in (ScheduleItemType.MEAL, ScheduleItemType.ACTIVITY):
                        continue
                    if item.latitude is None or item.longitude is None:
                        print(f"[warning] Option {option.option_id}, day {day.day_number}: "
                              f"'{item.title}' has no coordinates - was it actually found via "
                              f"search_nearby_places, or invented?")
                        continue

                    anchors = _neighboring_anchor_coords(relevant_items, idx, hotel)
                    if not anchors:
                        continue  # nothing to compare against for this group/day

                    nearest_km = min(_haversine_km(lat, lon, item.latitude, item.longitude) for lat, lon in anchors)
                    if nearest_km > MAX_VENUE_DISTANCE_KM:
                        print(
                            f"[warning] Option {option.option_id}, group {group_id}, day {day.day_number}: "
                            f"'{item.title}' is {nearest_km:.1f} km from the nearest neighboring stop "
                            f"(previous/next item, or hotel) - exceeds the {MAX_VENUE_DISTANCE_KM} km "
                            f"sanity check"
                        )


def _neighboring_anchor_coords(items: list, idx: int, hotel) -> list[tuple[float, float]]:
    """Finds reference points for item at `items[idx]` from its IMMEDIATE
    neighbors only (not walking further through the list). A transport
    item as an immediate neighbor means the trip to/from this stop is
    already grounded in a real get_directions result (see
    _validate_transitions and the system prompt's transport rule) - any
    distance is legitimate in that case, so that side is skipped rather
    than treated as an anchor. check_in/check_out resolve to the hotel's
    own coordinates. Falls back to the hotel only when this item has no
    neighbors at all (the only item of the day) - otherwise an empty
    result (both sides transport-connected) is a valid "nothing to flag"
    outcome, not a reason to fall back to the hotel and risk the exact
    false positive this function replaced.
    """
    anchors: list[tuple[float, float]] = []
    has_any_neighbor = False

    for step in (-1, 1):
        i = idx + step
        if not (0 <= i < len(items)):
            continue
        has_any_neighbor = True
        neighbor = items[i]

        if neighbor.type == ScheduleItemType.TRANSPORT:
            continue  # real transit already explains this leg - not an anchor to check distance against
        if neighbor.latitude is not None and neighbor.longitude is not None:
            anchors.append((neighbor.latitude, neighbor.longitude))
        elif neighbor.type in (ScheduleItemType.CHECK_IN, ScheduleItemType.CHECK_OUT) and hotel is not None:
            anchors.append((hotel.latitude, hotel.longitude))

    if not anchors and not has_any_neighbor and hotel is not None:
        anchors.append((hotel.latitude, hotel.longitude))

    return anchors


def _validate_schedule_timing(proposal: ItineraryProposal) -> None:
    """Post-hoc check that consecutive items for the same group actually
    line up in time: `time` is a START time and `duration_minutes` is now
    required (see itinerary_schemas.ScheduleItem), so the next item should
    start at this_item.time + this_item.duration_minutes. Built per-group
    like _validate_transitions, for the same reason - groups can be on
    parallel tracks the same day.

    Only warns; a real intentional gap (a long lunch, deliberate rest time
    folded badly into the numbers) can look identical to a plain addition
    mistake from the data alone, so this flags it for a human rather than
    silently rewriting anyone's schedule.
    """
    for option in proposal.options:
        group_ids = {h.group_id for h in option.hotel_selections}

        for day in option.days:
            for group_id in group_ids:
                relevant_items = [
                    item for item in day.items
                    if not item.applies_to_group_ids or group_id in item.applies_to_group_ids
                ]
                relevant_items.sort(key=lambda item: item.time)

                for prev_item, curr_item in zip(relevant_items, relevant_items[1:]):
                    prev_minutes = _parse_time_to_minutes(prev_item.time)
                    curr_minutes = _parse_time_to_minutes(curr_item.time)
                    if prev_minutes is None or curr_minutes is None:
                        print(f"[warning] Option {option.option_id}, group {group_id}, day {day.day_number}: "
                              f"could not parse time '{prev_item.time}' or '{curr_item.time}' as HH:MM")
                        continue

                    actual_gap = curr_minutes - prev_minutes
                    expected_gap = prev_item.duration_minutes

                    if abs(actual_gap - expected_gap) > TIMING_GAP_TOLERANCE_MINUTES:
                        print(
                            f"[warning] Option {option.option_id}, group {group_id}, day {day.day_number}: "
                            f"'{prev_item.title}' starts {prev_item.time} and states duration_minutes="
                            f"{expected_gap}, so '{curr_item.title}' should start around "
                            f"{_minutes_to_time(prev_minutes + expected_gap)} - it actually starts at "
                            f"{curr_item.time} ({actual_gap} min gap). Verify this is intentional free "
                            f"time accounted for somewhere, not a scheduling mistake."
                        )


_TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})$")


def _parse_time_to_minutes(time_str: str) -> int | None:
    match = _TIME_RE.match(time_str.strip())
    if not match:
        return None
    hours, minutes = int(match.group(1)), int(match.group(2))
    if not (0 <= hours < 24 and 0 <= minutes < 60):
        return None
    return hours * 60 + minutes


def _minutes_to_time(total_minutes: int) -> str:
    total_minutes %= 24 * 60
    return f"{total_minutes // 60:02d}:{total_minutes % 60:02d}"


def _validate_hotel_proximity(proposal: ItineraryProposal) -> None:
    """Post-hoc check for the "groups must stay close together" rule.

    Same reasoning as the budget check: the system prompt asks for this,
    but nothing guarantees Claude honored it, especially once several
    groups with different budgets push it toward different hotels. This
    only warns - it doesn't relocate anyone - so a human (or a future
    retry loop) can act on it.
    """
    for option in proposal.options:
        hotels = option.hotel_selections
        if len(hotels) < 2:
            continue  # nothing to compare for a single group

        for hotel_a, hotel_b in combinations(hotels, 2):
            distance_km = _haversine_km(
                hotel_a.latitude, hotel_a.longitude, hotel_b.latitude, hotel_b.longitude
            )
            if distance_km > MAX_HOTEL_DISTANCE_KM:
                print(
                    f"[warning] Option {option.option_id}: group {hotel_a.group_id}'s hotel "
                    f"({hotel_a.hotel_name}) is {distance_km:.1f} km from group {hotel_b.group_id}'s "
                    f"hotel ({hotel_b.hotel_name}) - exceeds the {MAX_HOTEL_DISTANCE_KM} km target"
                )


def _validate_transitions(proposal: ItineraryProposal) -> None:
    """Post-hoc check for "a transport item must exist between every pair of
    consecutive physical locations". Built per-group (not on the raw flat
    item list) because groups can split onto different parallel tracks on
    the same day (e.g. one group takes a taxi while others take transit) -
    checking the flat list directly would misfire on those legitimate splits.

    This is a heuristic (string equality on "location") and won't catch
    every real gap or avoid every false positive, but it surfaces the
    common case: two consecutive items with different locations and
    nothing describing how the group got from one to the other.
    """
    for option in proposal.options:
        group_ids = {h.group_id for h in option.hotel_selections}

        for day in option.days:
            for group_id in group_ids:
                relevant_items = [
                    item for item in day.items
                    if not item.applies_to_group_ids or group_id in item.applies_to_group_ids
                ]
                relevant_items.sort(key=lambda item: item.time)

                for prev_item, curr_item in zip(relevant_items, relevant_items[1:]):
                    if prev_item.type.value == "transport" or curr_item.type.value in ("transport", "flight"):
                        continue
                    if prev_item.location and curr_item.location and prev_item.location != curr_item.location:
                        print(
                            f"[warning] Option {option.option_id}, group {group_id}, day {day.day_number}: "
                            f"no transport item between '{prev_item.title}' ({prev_item.location}) and "
                            f"'{curr_item.title}' ({curr_item.location})"
                        )


def _validate_shared_activities(proposal: ItineraryProposal) -> None:
    """Post-hoc check for "groups never split into different meals/
    activities" (system prompt rule 12). There is only one travel_pace for
    the whole request (see TripPlanningRequest) - no per-group pace exists
    to justify splitting meal/activity items by group, so
    applies_to_group_ids must always be empty on those two item types.

    Unlike _validate_transitions, this is NOT about transport (groups can
    legitimately take different transport modes to the same shared stop -
    that's still one shared activity, just reached differently) - only
    meal/activity items themselves are checked here.
    """
    for option in proposal.options:
        for day in option.days:
            for item in day.items:
                if item.type not in (ScheduleItemType.MEAL, ScheduleItemType.ACTIVITY):
                    continue
                if item.applies_to_group_ids:
                    print(
                        f"[warning] Option {option.option_id}, day {day.day_number}: "
                        f"'{item.title}' has applies_to_group_ids={item.applies_to_group_ids} - meals/"
                        f"activities must never be split by group, this should be empty ([])"
                    )


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two GPS points, in kilometers."""
    r = 6371.0  # Earth's radius in km
    phi1, phi2 = radians(lat1), radians(lat2)
    d_phi = radians(lat2 - lat1)
    d_lambda = radians(lon2 - lon1)
    a = sin(d_phi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(d_lambda / 2) ** 2
    return r * 2 * atan2(sqrt(a), sqrt(1 - a))
