"""Client for generating full trip itineraries with Claude.

Four things make this reliable rather than plausible-sounding-but-wrong:
  1. A real places-search tool Claude must call for every restaurant/
     activity
  2. A real directions tool Claude must call for every transport item
  3. A real web-search tool Claude must call for time-sensitive facts (like
     current transit fares) instead of relying on training data
  4. Forced tool use for the FINAL answer, validated against a strict
     Pydantic schema - so the structure is always parseable even though
     the content along the way came from real tool calls.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass

import anthropic
from pydantic import ValidationError

from clients.directions_client import GoogleMapsDirectionsClient, GoogleMapsDirectionsError
from clients.search_service_client import SearchServiceClient
from itinerary_schemas import ItineraryOption, TripPlanningRequest
from clients.places_client import GoogleMapsPlacesClient, GoogleMapsPlacesError

FINAL_TOOL_NAME = "propose_itineraries"
PLACES_TOOL_NAME = "search_nearby_places"
DIRECTIONS_TOOL_NAME = "get_directions"
WEB_SEARCH_TOOL_NAME = "search_web"
MAX_TOOL_ITERATIONS = 40  # hard cap on tool round trips per option, to bound cost/latency

# Grounding facts so Claude doesn't guess at transport costs from stale
# training data - Berlin fares changed on 2026-01-01 (VBB fare increase,
# 7-day pass discontinued), and can change again at any time. Only the
# PRODUCT names/structure are listed here, deliberately without prices -
# a static price here would go stale exactly like training data does, so
# actual current prices must be looked up live via WEB_SEARCH_TOOL_NAME.
BERLIN_TRANSPORT_FACTS = f"""
Berlin (BVG/VBB) public transport fare PRODUCTS that exist (do not guess
their current prices from memory - always ground them via {WEB_SEARCH_TOOL_NAME},
see below):
- Single ticket, zone AB (inner city) - valid 2 hours, transfers included
- Single ticket, zone ABC (includes BER airport / Potsdam)
- Kurzstrecke (short trip, max 3 U/S-Bahn stops or 6 bus/tram stops)
- 24-hour ticket, zone AB or zone ABC (includes airport)
- Berlin WelcomeCard (48h/72h/4-day/5-day/6-day: transport + attraction discounts)
- Taxi/rideshare from BER airport to central Berlin

IMPORTANT: these are different PRODUCTS for the same trip, not add-ons. For any
stay of 3+ days with multiple trips per day, buying repeated single tickets is
almost always more expensive than a day ticket or a WelcomeCard for the same
period. Before pricing a group's local transport for a day:
1. Call {WEB_SEARCH_TOOL_NAME} for the current price of each product you're
   comparing (e.g. "BVG VBB Berlin single ticket day ticket price 2026",
   "Berlin WelcomeCard price") - fares change and your training data may be
   stale or wrong.
2. Do the arithmetic (estimated rides/day x days x the single-ticket price you
   just found vs the multi-day product's price you just found) and pick
   whichever is actually cheaper in total for that group's specific trip
   length and usage pattern.
3. State which product you chose, its price, and that it came from a live
   search (not memory) in the notes field of the schedule item where that
   group buys it (e.g. the first transport item of the day), and put its
   real cost in that item's cost_eur - this is what actually gets summed
   into local_transport_cost, there is no separate free-text place for
   "reasoning" in the final output.

For a single transit RIDE, prefer {DIRECTIONS_TOOL_NAME}'s own transit_fare_eur
when it returns one (mode="transit") - that's Google's live computed fare for
that EXACT journey, more precise than a general product price. If the group
already bought a day ticket/WelcomeCard covering that ride, that ride's own
cost_eur is 0 (it's prepaid by the pass), regardless of what transit_fare_eur says.
"""

SYSTEM_PROMPT = f"""You are a meticulous trip planner building complete, bookable
day-by-day itineraries for group trips arriving in Berlin, Germany.

{BERLIN_TRANSPORT_FACTS}

You have three research tools. You MUST use all of them where relevant - do
not recall place names, walking times, transit durations, or current prices
from memory.

{PLACES_TOOL_NAME}: returns REAL, currently-existing businesses with real GPS
coordinates near a given point.
- Before adding ANY meal or activity schedule item, call it with a query
  (e.g. "currywurst", "museum", "italian restaurant") and coordinates
  chosen for where the group ACTUALLY is at that point in the day - not
  always the hotel. Use whichever of these is most relevant:
    - the group's hotel, if this is the first/last stop of the day
    - the previous stop's coordinates, if the group already moved there
    - if you already know the NEXT planned stop too (e.g. you're placing
      lunch between a morning activity and an afternoon one), prefer a
      point roughly between the previous and next stop, so the meal sits
      conveniently on the route rather than forcing a detour back near
      the hotel. A restaurant near neither stop but technically "central"
      is a worse choice than one directly on the way.
- Only use places the tool actually returned. Copy their exact name,
  address, latitude, longitude, and maps_url into the schedule item -
  maps_url becomes that item's `url` field, letting the traveler open the
  real place directly instead of just reading its name.
- If it returns nothing useful, try a broader or different query rather
  than falling back to a remembered/generic suggestion.
- Prefer results with a higher rating and more reviews (userRatingCount)
  when several options fit; avoid anything with a low rating (below ~3.8)
  if a well-reviewed alternative exists nearby.

{DIRECTIONS_TOOL_NAME}: returns the REAL duration and distance for one
specific travel mode (walking/transit/driving) between two exact coordinates.
- Before adding ANY "transport" schedule item, call it with the origin and
  destination coordinates (from the previous stop and the next stop - both
  of which should already have real coordinates from hotel offers or
  {PLACES_TOOL_NAME}) and the mode you're considering.
- Use its returned duration_minutes as that item's duration_minutes EXACTLY -
  do not round it, and do not estimate it yourself instead of calling the tool.
- Set that item's transport_mode to the exact mode you called the tool with -
  this is a required field now, not just prose in the title/description.
- If walking would take too long for the group's pace or a wheelchair user's
  needs, call it again with mode="transit" or mode="driving" and compare -
  choose whichever real result actually fits, rather than assuming.
- If mode="transit", check the result's transit_fare_eur - when present, it's
  Google's own live fare for this exact ride (see the transport fare rules
  above for how it interacts with day tickets/WelcomeCards).

{WEB_SEARCH_TOOL_NAME}: returns REAL, current Google search results (title,
snippet, link) for a text query.
- Use it to ground any time-sensitive fact you'd otherwise have to guess from
  training data - most importantly, current Berlin transport fare-product
  prices (see above), but also things like a museum's current entry fee if
  that affects a group's budget.
- Read the snippet text, not just the title - the actual number/fact is
  usually in the snippet. If results are ambiguous or don't contain a clear
  answer, try a more specific query rather than guessing from the closest result.

Time and duration rules - these matter as much as the place/route grounding
above, and are checked programmatically after you submit:
- `time` on every item is a START time, never a range. Every item also has a
  REQUIRED `duration_minutes`: for a meal/activity it is the actual time you
  are allotting (a real decision - 45 min for a quick lunch, 90-120 for a
  sit-down dinner or museum, not a filler number); for a transport item it
  MUST be the exact duration_minutes {DIRECTIONS_TOOL_NAME} returned.
- The next item for the same group must start at this item's
  time + duration_minutes. Compute this addition yourself and double-check
  it before submitting - do not eyeball clock times.
- If there is real unstructured time with nothing scheduled (the group rests
  at the hotel, has free afternoon time before a dinner reservation), that
  time is NOT a gap you leave unexplained - fold it into the preceding
  item's duration_minutes (e.g. a "Free time / rest at hotel" transport or
  activity item covering that block) so the arithmetic above still holds
  exactly, or extend the following meal/activity's own duration_minutes
  backward. A schedule where two consecutive times don't add up correctly
  is treated as a bug, not a stylistic choice.

Hard rules you must never violate:
1. Hotel check-in must happen within 2 hours of that group's flight arrival time.
2. Hotel check-out must happen at least 5 hours before that group's return flight
   departure time.
3. When there is more than one group, every group's chosen hotel must be within
   easy walking distance or a single short public-transit hop of every other
   group's hotel (same neighborhood, ideally under 1.5 km apart) - groups are
   traveling together and need to coordinate meals and activities easily, even
   if their room type/budget means they aren't in the exact same building.
   Prefer the same hotel for all groups when a suitable option exists for
   everyone's budget and composition. This is checked against the real
   latitude/longitude of the hotel offers - not an approximation.
4. Every group's total_cost (flights + hotel + activities + meals + local transport)
   must not exceed that group's budget_max, if one is set. If you cannot fit a
   comfortable plan within budget, choose cheaper flight/hotel offers from the
   provided lists, or reduce paid activities - never silently exceed the budget.
   Note: price_breakdown is recalculated after you submit from the actual
   cost_eur on every schedule item plus your flight/hotel selections - your
   own numbers here are a first draft, not the final answer. What matters is
   that every priced item's cost_eur is correct and attributed to the right
   group(s) via applies_to_group_ids, since that is what actually gets summed.
5. For local transport, choose the most cost-effective real fare PRODUCT for
   each group's trip length and usage, using CURRENT prices looked up via
   {WEB_SEARCH_TOOL_NAME} (see the transport fare rules above) - do not price
   every single ride as a separate single ticket if a day ticket or WelcomeCard
   would cost less over the whole stay, and never use a guessed/remembered
   price for a fare product.
6. EVERY SINGLE physical transition - between airport and hotel, hotel and any
   meal, meal and any activity, activity and hotel, anywhere a group's location
   changes at all - must appear as its own "transport" schedule item, built
   from a REAL {DIRECTIONS_TOOL_NAME} result (see tool instructions above),
   not an estimate. There must be no gap in the chain of physical locations
   across an entire day. This is checked programmatically after generation -
   unrealistic or missing transitions will be flagged.
7. Respect the stated travel pace: "relaxed" means 1-2 activities per day with
   generous meal/rest time; "moderate" means 2-3; "packed" means 4+ with tight
   but still walkable/rideable transitions.
8. Respect each group's wheelchair_accessible flag: check the real walking
   duration via {DIRECTIONS_TOOL_NAME} before assigning a walking transport
   item to that group - if it's long (over ~20-25 minutes), use transit or
   taxi instead, and say so explicitly in the item's notes.
9. Only choose flights and hotels from the offers actually provided in the
   input - do not invent prices or properties that aren't in the lists. Use
   each hotel offer's actual latitude/longitude for hotel_selections, and
   copy that offer's booking_url unchanged into hotel_selections.booking_url
   so the traveler has somewhere to actually book it. Do the same for
   flights: copy the chosen flight_offers entry's booking_url into
   flight_selections.booking_url. Hotel offers are pre-filtered to
   well-rated properties unless a note says otherwise - if the offers list
   for a group includes a "quality_fallback" note, that means no well-rated
   option fit the budget and lower-rated options had to be included; prefer
   the highest-rated option still available even in that case.
10. Only recommend places {PLACES_TOOL_NAME} actually returned - do not
    invent a place it didn't return, even a plausible-sounding one. Prefer
    well-rated results over poorly-rated ones when both fit the budget.
11. Include breakfast, lunch, and dinner recommendations for every day of the
    stay, matching the user's stated food preferences, using real places
    found via {PLACES_TOOL_NAME}.
12. Every meal and activity is for the WHOLE TRIP together - groups never
    split into different activities, restaurants, or paces. Leave
    applies_to_group_ids EMPTY ([]) on every meal/activity item; there is
    only one travel_pace for the entire request (see the user message), so
    there is no per-group pace to justify splitting on. applies_to_group_ids
    should only ever be non-empty for items inherently tied to one group's
    own booking - that group's own flight, or its own hotel check-in/
    check-out if groups are staying in different hotels.
    Each group in GROUPS may also have its own `preferences` text, separate
    from the trip-wide USER PREFERENCES below - since meals/activities are
    always shared, weigh every group's preferences together when choosing
    one: prefer a place/activity that reasonably satisfies all groups (e.g.
    a restaurant with both vegetarian and meat options) over one that only
    suits one group. If groups' preferences genuinely conflict and no single
    good option covers both, pick the best reasonable compromise and say so
    explicitly in that item's notes (which group's preference it favors and
    why) - do not silently ignore one group's stated preference.
13. This is one of several separate calls, each producing one option at a
    specific budget tier (see the tier instructions in the user message) -
    make THIS option internally complete and consistent even though you
    don't see the other tiers being generated separately.

Once you have gathered enough real places and real travel times to build the
full itinerary, call {FINAL_TOOL_NAME} with your complete answer. Do not
respond in plain text."""


@dataclass(frozen=True)
class BudgetTier:
    name: str
    instructions: str


# Three fixed tiers instead of an arbitrary "N distinct options" - each has a
# specific, unambiguous spending target relative to each group's budget_max,
# rather than leaving "how different should these be" up to the model to guess.
TIERS = [
    BudgetTier(
        name="Budget",
        instructions=(
            "Minimize total cost for every group while still satisfying every hard rule. "
            "Choose the cheapest qualifying flight and hotel offers (hostels are fine). "
            "Keep paid activities minimal - prefer free or low-cost sightseeing and "
            "affordable local street food. This option should leave a large budget "
            "surplus for every group."
        ),
    ),
    BudgetTier(
        name="Mid-range comfort",
        instructions=(
            "Aim for noticeably more comfort than the cheapest possible plan. Prefer a "
            "real hotel over a hostel where one is available and fits the budget, add a "
            "bit more restaurant variety and one or two paid activities/tours per group, "
            "while staying clearly under each group's budget_max - leave meaningful "
            "headroom (roughly 20-30% of budget unspent), don't spend right up to the limit."
        ),
    ),
    BudgetTier(
        name="Premium (budget ceiling)",
        instructions=(
            "Spend close to, but never over, each group's budget_max. Choose the most "
            "comfortable available flights and hotels the budget allows, include more "
            "paid activities/tours and higher-quality restaurant recommendations, to "
            "give the best possible experience within the stated budget."
        ),
    ),
]

PLACES_TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {"type": "string", "description": "What to search for, e.g. 'currywurst', 'museum', 'pizza restaurant'"},
        "latitude": {"type": "number", "description": "Latitude of the point to search near"},
        "longitude": {"type": "number", "description": "Longitude of the point to search near"},
    },
    "required": ["query", "latitude", "longitude"],
}

DIRECTIONS_TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "origin_latitude": {"type": "number"},
        "origin_longitude": {"type": "number"},
        "destination_latitude": {"type": "number"},
        "destination_longitude": {"type": "number"},
        "mode": {"type": "string", "enum": ["walking", "transit", "driving", "cycling"]},
    },
    "required": ["origin_latitude", "origin_longitude", "destination_latitude", "destination_longitude", "mode"],
}

WEB_SEARCH_TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {"type": "string", "description": "Search query, e.g. 'BVG VBB Berlin day ticket price 2026'"},
    },
    "required": ["query"],
}


class ItineraryGenerationError(Exception):
    """Raised when Claude's response can't be turned into a valid ItineraryOption."""


@dataclass
class GenerationResult:
    """generate_option()'s return value: the itinerary itself, plus every
    real place search_nearby_places actually returned during that run.

    The found_places list is what lets the caller verify Claude's final
    answer is actually grounded in real tool results, rather than trusting
    the system prompt's "only use places the tool returned" instruction to
    have been followed - an instruction the model can still silently
    violate (e.g. by recalling a well-known but long-closed venue from its
    own training data instead of calling the tool for that specific item).
    """
    option: ItineraryOption
    found_places: list[dict]


class ClaudeItineraryClient:
    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-sonnet-5",
        places_client: GoogleMapsPlacesClient | None = None,
        directions_client: GoogleMapsDirectionsClient | None = None,
        search_service_client: SearchServiceClient | None = None,
    ) -> None:
        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise ItineraryGenerationError("ANTHROPIC_API_KEY is not set")
        self._client = anthropic.Anthropic(api_key=key)
        self._model = model
        self._places_client = places_client or GoogleMapsPlacesClient()
        self._directions_client = directions_client or GoogleMapsDirectionsClient()
        self._search_service_client = search_service_client or SearchServiceClient()

    def generate_option(self, request: TripPlanningRequest, tier: BudgetTier) -> GenerationResult:
        """Generates a SINGLE itinerary option per call. Runs a real
        tool-use loop: Claude can call search_nearby_places and
        get_directions as many times as it needs (up to
        MAX_TOOL_ITERATIONS) to ground the plan in real places and real
        travel times before submitting the final structured itinerary via
        propose_itineraries.

        Every place search_nearby_places returns during this call is
        collected into found_places, local to this call (not shared across
        tiers) - recommendation_stage.py uses it afterward to check that
        every meal/activity item in the final answer actually matches a
        real result, not something Claude wrote from memory.
        """
        found_places: list[dict] = []
        tools = [
            {
                "name": PLACES_TOOL_NAME,
                "description": "Search for real, currently-existing businesses near a GPS point.",
                "input_schema": PLACES_TOOL_SCHEMA,
            },
            {
                "name": DIRECTIONS_TOOL_NAME,
                "description": "Get the real travel duration/distance between two GPS points for one travel mode.",
                "input_schema": DIRECTIONS_TOOL_SCHEMA,
            },
            {
                "name": WEB_SEARCH_TOOL_NAME,
                "description": "Real, current Google search results for a text query - use to ground time-sensitive facts like current transit fares.",
                "input_schema": WEB_SEARCH_TOOL_SCHEMA,
            },
            {
                "name": FINAL_TOOL_NAME,
                "description": "Submit one complete trip itinerary option, once you have gathered real places and real travel times for everything.",
                "input_schema": ItineraryOption.model_json_schema(),
            },
        ]

        messages = [{"role": "user", "content": self._build_user_message(request, tier)}]

        for _ in range(MAX_TOOL_ITERATIONS):
            # Streaming is required, not optional: the SDK refuses plain
            # .create() once max_tokens is high enough that generation could
            # plausibly exceed its non-streaming timeout window.
            with self._client.messages.stream(
                model=self._model,
                max_tokens=32000,  # Sonnet 5 supports up to 128k; 32k comfortably covers one full option
                system=SYSTEM_PROMPT,
                tools=tools,
                tool_choice={"type": "auto"},  # Claude decides: search more, get directions, or submit
                messages=messages,
            ) as stream:
                response = stream.get_final_message()

            if response.stop_reason == "max_tokens":
                raise ItineraryGenerationError(
                    "Claude's response was cut off at the max_tokens limit before finishing - "
                    "the itinerary was too large for a single call."
                )

            tool_use_blocks = [block for block in response.content if block.type == "tool_use"]
            final_block = next((b for b in tool_use_blocks if b.name == FINAL_TOOL_NAME), None)

            if final_block is not None:
                try:
                    option = ItineraryOption.model_validate(final_block.input)
                except ValidationError as exc:
                    raise ItineraryGenerationError(f"Claude's response did not match the schema: {exc}") from exc
                return GenerationResult(option=option, found_places=found_places)

            if not tool_use_blocks:
                raise ItineraryGenerationError(
                    "Claude responded without calling any tool - expected one of "
                    f"{PLACES_TOOL_NAME}, {DIRECTIONS_TOOL_NAME}, {WEB_SEARCH_TOOL_NAME}, {FINAL_TOOL_NAME}"
                )

            # Claude called one or more research tools this turn - execute
            # each for real and feed the real results back before continuing.
            messages.append({"role": "assistant", "content": response.content})
            tool_results = [self._execute_tool_call(block, found_places) for block in tool_use_blocks]
            messages.append({"role": "user", "content": tool_results})

        raise ItineraryGenerationError(
            f"Exceeded {MAX_TOOL_ITERATIONS} tool-use round trips without a final answer"
        )

    def _execute_tool_call(self, block, found_places: list[dict]) -> dict:
        if block.name == PLACES_TOOL_NAME:
            content = self._execute_places_call(block, found_places)
        elif block.name == DIRECTIONS_TOOL_NAME:
            content = self._execute_directions_call(block)
        elif block.name == WEB_SEARCH_TOOL_NAME:
            content = self._execute_web_search_call(block)
        else:
            content = f"Unknown tool '{block.name}'"

        return {"type": "tool_result", "tool_use_id": block.id, "content": content}

    def _execute_places_call(self, block, found_places: list[dict]) -> str:
        try:
            results = self._places_client.search_nearby(
                query=block.input["query"],
                latitude=block.input["latitude"],
                longitude=block.input["longitude"],
            )
            # Record every real result here, regardless of whether Claude
            # ends up using it - this is the ground truth
            # _validate_places_are_real() checks the final answer against.
            found_places.extend(results)
            return json.dumps(results, ensure_ascii=False) if results else (
                "[] (no results for this query/location - try a different query)"
            )
        except GoogleMapsPlacesError as exc:
            return f"Places search failed: {exc}"

    def _execute_directions_call(self, block) -> str:
        try:
            result = self._directions_client.get_directions(
                origin_lat=block.input["origin_latitude"],
                origin_lon=block.input["origin_longitude"],
                dest_lat=block.input["destination_latitude"],
                dest_lon=block.input["destination_longitude"],
                mode=block.input["mode"],
            )
            return json.dumps(result, ensure_ascii=False)
        except GoogleMapsDirectionsError as exc:
            return f"Directions request failed: {exc}"

    def _execute_web_search_call(self, block) -> str:
        results = self._search_service_client.search_web(query=block.input["query"])
        return json.dumps(results, ensure_ascii=False) if results else (
            "[] (no results, or search failed - try a different/more specific query)"
        )

    @staticmethod
    def _build_user_message(request: TripPlanningRequest, tier: BudgetTier) -> str:
        return (
            f"Plan the '{tier.name}' itinerary option for this Berlin trip, using ONLY "
            f"the flight and hotel offers listed below, real places found via "
            f"{PLACES_TOOL_NAME}, real travel times found via {DIRECTIONS_TOOL_NAME}, and "
            f"current prices/facts found via {WEB_SEARCH_TOOL_NAME}.\n\n"
            f"TIER INSTRUCTIONS: {tier.instructions}\n\n"
            f"GROUPS (each group's own `preferences` field, if any, is separate from the "
            f"trip-wide USER PREFERENCES below - see rule 12 for how to weigh them together "
            f"at shared meals/activities):\n"
            f"{json.dumps([g.model_dump() for g in request.groups], indent=2, ensure_ascii=False)}\n\n"
            f"TRAVEL PACE: {request.travel_pace}\n\n"
            f"USER PREFERENCES (trip-wide: food, interests, must-sees, anything else stated):\n"
            f"{request.user_preferences}\n\n"
            f"AVAILABLE FLIGHT OFFERS (already filtered to each group's budget):\n"
            f"{json.dumps(request.flight_offers, indent=2, ensure_ascii=False)}\n\n"
            f"AVAILABLE HOTEL OFFERS (pre-filtered by rating and budget - see rule 9 "
            f"about quality_fallback):\n"
            f"{json.dumps(request.hotel_offers, indent=2, ensure_ascii=False)}\n"
        )
