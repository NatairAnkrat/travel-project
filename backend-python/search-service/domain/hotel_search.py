from __future__ import annotations

import logging

from clients.google_hotels_client import GoogleHotelsClient, SerpApiHotelsError
from schemas import HotelGroupInput, HotelOffer, HotelSearchRequest

logger = logging.getLogger(__name__)


def search(client: GoogleHotelsClient, request: HotelSearchRequest) -> list[HotelOffer]:
    rows: list[HotelOffer] = []
    for group in request.groups:
        for check_in, check_out in request.stay_date_ranges:
            rows.extend(_search_group_date(client, request.location, group, check_in, check_out))
    return rows


def _search_group_date(
    client: GoogleHotelsClient, location: str, group: HotelGroupInput, check_in: str, check_out: str,
) -> list[HotelOffer]:
    group_size = group.adults + group.children
    group_label = f"{group.adults}A+{group.children}C" if group.children else f"{group.adults}A"

    try:
        properties = client.search(
            location, check_in, check_out,
            adults=group.adults, children=group.children, children_ages=group.children_ages,
            wheelchair_accessible=group.wheelchair_accessible,
        )
    except SerpApiHotelsError as exc:
        logger.warning("Hotel search failed for group %s %s->%s: %s", group.group_id, check_in, check_out, exc)
        return [_status_offer(group, group_label, group_size, check_in, check_out, "search_failed", str(exc))]

    if not properties:
        return [_status_offer(group, group_label, group_size, check_in, check_out, "no_offers_found")]

    properties_sorted = sorted(properties, key=lambda p: p["total_price"] if p["total_price"] is not None else float("inf"))
    within_budget = (
        [p for p in properties_sorted if (p["total_price"] or float("inf")) <= group.budget_max]
        if group.budget_max is not None else properties_sorted
    )

    if not within_budget:
        cheapest = properties_sorted[0]["total_price"]
        return [_status_offer(
            group, group_label, group_size, check_in, check_out, "no_offers_within_budget",
            f"budget={group.budget_max:.2f}, cheapest_found={cheapest}",
        )]

    rows = []
    for prop in within_budget:
        # address is intentionally left blank here - it used to cost an extra
        # get_property_details call for the cheapest in-budget property, but
        # that's frequently not the one Claude ends up choosing. Real
        # addresses are now fetched only for whichever hotels make it into
        # the final itinerary options (see recommendation_stage._fetch_hotel_addresses
        # and /search/hotels/property-details).
        rows.append(HotelOffer(
            group_id=group.group_id, group_composition=group_label, group_size=group_size,
            wheelchair_accessible=group.wheelchair_accessible,
            check_in_date=check_in, check_out_date=check_out, location=location,
            property_name=prop["name"], property_type=prop["type"],
            property_token=prop.get("property_token") or "",
            total_price=prop["total_price"], currency=prop["currency"],
            rate_per_night=prop["rate_per_night"], overall_rating=prop["overall_rating"],
            hotel_class=prop["hotel_class"],
            latitude=prop["latitude"], longitude=prop["longitude"],
            address="", amenities_summary=prop["amenities_summary"],
            booking_url=prop.get("booking_url", ""),
            status="ok",
        ))
    return rows


def _status_offer(group: HotelGroupInput, group_label: str, group_size: int,
                   check_in: str, check_out: str, status: str, note: str = "") -> HotelOffer:
    return HotelOffer(
        group_id=group.group_id, group_composition=group_label, group_size=group_size,
        wheelchair_accessible=group.wheelchair_accessible,
        check_in_date=check_in, check_out_date=check_out, status=status, note=note,
    )
