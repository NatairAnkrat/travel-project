"""Re-search flights + hotels for new dates and map them into the offer shape
recommendation-service consumes.

Only invoked when an edit changes the travel dates - other edits reuse the
offers stored on the previous version's ai_job. search-service's FlightOffer is
already compatible with what generation reads; its HotelOffer only needs
`property_name`/`total_price` aliased to `hotel_name`/`price`.
"""
from __future__ import annotations

from datetime import date

from clients.search_client import SearchClient


class OfferResearchError(Exception):
    pass


def _nights(start_date: str, end_date: str) -> int:
    nights = (date.fromisoformat(end_date) - date.fromisoformat(start_date)).days
    if nights <= 0:
        raise OfferResearchError(f"end_date {end_date} must be after start_date {start_date}")
    return nights


def _flight_groups(groups: list[dict]) -> list[dict]:
    return [
        {
            "group_id": g["group_id"],
            "adults": g.get("adults", 1),
            "children": g.get("children", 0),
            "children_ages": [],
            "budget_max": g.get("budget_max"),
        }
        for g in groups
    ]


def _hotel_groups(groups: list[dict]) -> list[dict]:
    return [
        {
            "group_id": g["group_id"],
            "adults": g.get("adults", 1),
            "children": g.get("children", 0),
            "children_ages": [],
            "budget_max": g.get("budget_max"),
            "wheelchair_accessible": g.get("wheelchair_accessible", False),
        }
        for g in groups
    ]


def _map_hotel_offer(offer: dict) -> dict:
    # Keep every original field; add the aliases generation/the prompt expect.
    return {
        **offer,
        "hotel_name": offer.get("property_name", ""),
        "price": offer.get("total_price"),
    }


def research(
    search_client: SearchClient,
    origin_city: str,
    destination_city: str,
    start_date: str,
    end_date: str,
    groups: list[dict],
) -> tuple[list[dict], list[dict]]:
    """Returns (flight_offers, hotel_offers) already in recommendation-service's
    format for the new dates."""
    nights = _nights(start_date, end_date)

    flight_resp = search_client.search_flights(
        {
            "origin_city": origin_city,
            "destination_city": destination_city,
            "base_departure_date": start_date,
            "trip_length_nights": nights,
            "date_range_days": 0,  # exact new dates, not a window
            "top_n_outbound": 1,
            "groups": _flight_groups(groups),
        }
    )
    flight_offers = flight_resp.get("offers", [])
    ok_offers = [o for o in flight_offers if o.get("status") == "ok"]
    if not ok_offers:
        raise OfferResearchError(f"no flights found for {origin_city} -> {destination_city} on {start_date}")

    # Search hotels only for date pairs that actually have flights (per
    # search-service's HotelSearchRequest contract).
    date_pairs = sorted({(o["outbound_date"], o["return_date"]) for o in ok_offers})
    hotel_resp = search_client.search_hotels(
        {
            "location": f"{destination_city}, Germany",
            "stay_date_ranges": [[ci, co] for ci, co in date_pairs],
            "groups": _hotel_groups(groups),
        }
    )
    hotel_offers = [_map_hotel_offer(o) for o in hotel_resp.get("offers", [])]

    return flight_offers, hotel_offers
