from __future__ import annotations

import logging
from datetime import datetime, timedelta

from clients.google_flights_client import GoogleFlightsClient, SerpApiFlightsError
from schemas import FlightGroupInput, FlightOffer, FlightSearchRequest

logger = logging.getLogger(__name__)


def build_date_pairs(base_departure_str: str, trip_length_nights: int, date_range_days: int) -> list[tuple[str, str]]:
    base_departure = datetime.strptime(base_departure_str, "%Y-%m-%d").date()
    pairs = []
    for offset in range(-date_range_days, date_range_days + 1):
        outbound = base_departure + timedelta(days=offset)
        inbound = outbound + timedelta(days=trip_length_nights)
        pairs.append((outbound.isoformat(), inbound.isoformat()))
    return pairs


def search(client: GoogleFlightsClient, request: FlightSearchRequest) -> tuple[str, str, list[FlightOffer]]:
    """Resolves both cities, then searches every group x date-pair
    combination. Returns (resolved_origin_name, resolved_destination_name, offers).
    """
    origin = _resolve_city_or_raise(client, request.origin_city)
    destination = _resolve_city_or_raise(client, request.destination_city)

    date_pairs = build_date_pairs(request.base_departure_date, request.trip_length_nights, request.date_range_days)

    offers: list[FlightOffer] = []
    for group in request.groups:
        offers.extend(_search_group(client, origin["kgmid"], destination["kgmid"], date_pairs, group, request.top_n_outbound))

    return origin["name"], destination["name"], offers


def _resolve_city_or_raise(client: GoogleFlightsClient, city_name: str) -> dict:
    try:
        return client.resolve_city(city_name)
    except SerpApiFlightsError as exc:
        raise ValueError(f"Could not resolve city '{city_name}': {exc}") from exc


def _search_group(
    client: GoogleFlightsClient,
    origin_kgmid: str,
    destination_kgmid: str,
    date_pairs: list[tuple[str, str]],
    group: FlightGroupInput,
    top_n_outbound: int,
) -> list[FlightOffer]:
    rows: list[FlightOffer] = []
    group_size = group.adults + group.children
    group_label = f"{group.adults}A+{group.children}C" if group.children else f"{group.adults}A"

    for outbound_date, return_date in date_pairs:
        try:
            raw_offers = client.search_round_trip(
                origin_kgmid, destination_kgmid, outbound_date, return_date,
                adults=group.adults, children=group.children, children_ages=group.children_ages,
                top_n_outbound=top_n_outbound,
            )
        except SerpApiFlightsError as exc:
            logger.warning("Flight search failed for group %s %s->%s: %s", group.group_id, outbound_date, return_date, exc)
            rows.append(_status_offer(group, group_label, group_size, outbound_date, return_date, "search_failed", str(exc)))
            continue

        if not raw_offers:
            rows.append(_status_offer(group, group_label, group_size, outbound_date, return_date, "no_offers_found"))
            continue

        offers_sorted = sorted(raw_offers, key=lambda o: o["price"])
        within_budget = (
            [o for o in offers_sorted if o["price"] <= group.budget_max]
            if group.budget_max is not None else offers_sorted
        )

        if not within_budget:
            cheapest = offers_sorted[0]["price"]
            rows.append(_status_offer(
                group, group_label, group_size, outbound_date, return_date, "no_offers_within_budget",
                f"budget={group.budget_max:.2f}, cheapest_found={cheapest:.2f}",
            ))
            continue

        for offer in within_budget:
            rows.append(FlightOffer(
                group_id=group.group_id, group_composition=group_label, group_size=group_size,
                outbound_date=outbound_date, return_date=return_date,
                airline_outbound=offer["airline_outbound"], airline_return=offer["airline_return"],
                price=offer["price"], currency=offer["currency"],
                outbound_departure_time=offer["outbound_departure_time"],
                outbound_arrival_time=offer["outbound_arrival_time"],
                return_departure_time=offer["return_departure_time"],
                return_arrival_time=offer["return_arrival_time"],
                origin_airport=offer["origin_airport"], destination_airport=offer["destination_airport"],
                origin_latitude=offer["origin_latitude"], origin_longitude=offer["origin_longitude"],
                destination_latitude=offer["destination_latitude"], destination_longitude=offer["destination_longitude"],
                outbound_stops=offer["outbound_stops"], return_stops=offer["return_stops"],
                booking_url=offer.get("booking_url", ""),
                booking_token=offer.get("booking_token") or "",
                status="ok",
            ))

    return rows


def _status_offer(group: FlightGroupInput, group_label: str, group_size: int,
                   outbound_date: str, return_date: str, status: str, note: str = "") -> FlightOffer:
    return FlightOffer(
        group_id=group.group_id, group_composition=group_label, group_size=group_size,
        outbound_date=outbound_date, return_date=return_date, status=status, note=note,
    )
