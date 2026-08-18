"""Client for searching flights via SerpApi's Google Flights engine.

Extends the original single-adult version with:
  - adults/children per search (needed for group compositions)
  - an optional second call to fetch baggage pricing for a given offer
"""
from __future__ import annotations

import os
import re
from urllib.parse import quote

import airportsdata
import serpapi

# IATA -> {lat, lon, name, city, ...}, loaded once from the bundled offline
# dataset (see https://github.com/mborsetti/airportsdata)
_AIRPORTS = airportsdata.load("IATA")


class SerpApiFlightsError(Exception):
    """Raised when SerpApi returns an error status for a search."""


class GoogleFlightsClient:
    def __init__(self, api_key: str | None = None) -> None:
        key = api_key or os.environ.get("SERPAPI_API_KEY")
        if not key:
            raise SerpApiFlightsError("SERPAPI_API_KEY is not set")
        self._client = serpapi.Client(api_key=key)

    # Real IATA airport codes are always exactly 3 uppercase letters.
    _VALID_IATA_CODE = re.compile(r"^[A-Z]{3}$")

    # Keywords in the airport "name" field that signal this is actually a
    # train/bus/ferry station with an IATA code for combined air+rail ticketing
    _NON_AIRPORT_KEYWORDS = (
        "bahnhof", "hauptbahnhof", "railway", "rail station",
        "train station", "gare", "bus station",
    )

    def resolve_city(self, query: str) -> dict:
        """Resolves a free-text city name (e.g. "Paris") into a Google
        Knowledge Graph ID (kgmid) that can be passed directly as
        departure_id/arrival_id

        Returns {"name": ..., "kgmid": ..., "airports": [{"id": "CDG", "name": ...}, ...]}
        Real airports only - train/bus stations with air-ticketing IATA codes are filtered out.
        Raises SerpApiFlightsError if nothing matches.
        """
        params = {"engine": "google_flights_autocomplete", "q": query}
        results = self._safe_search(params)

        if "error" in results:
            raise SerpApiFlightsError(results["error"])

        suggestions = results.get("suggestions", [])
        # Prefer an exact "city" match over "region" or airport-only suggestions.
        city_matches = [s for s in suggestions if s.get("type") == "city"]
        best_match = city_matches[0] if city_matches else (suggestions[0] if suggestions else None)

        if best_match is None:
            raise SerpApiFlightsError(f"No location found for '{query}'")

        all_airports = best_match.get("airports", [])
        real_airports = [
            a for a in all_airports
            if self._VALID_IATA_CODE.match((a.get("id") or "").upper())
            and not any(kw in (a.get("name") or "").lower() for kw in self._NON_AIRPORT_KEYWORDS)
        ]

        return {
            "name": best_match.get("name", query),
            "kgmid": best_match.get("id"),
            "airports": [
                {"id": a.get("id"), "name": a.get("name")}
                for a in real_airports
            ],
        }

    def search_round_trip(
        self,
        origin: str,
        destination: str,
        outbound_date: str,
        return_date: str,
        adults: int = 1,
        children: int = 0,
        children_ages: list[int] | None = None,
        currency: str = "EUR",
        top_n_outbound: int = 1,
    ) -> list[dict]:
        """Round trip search.

        Google Flights (and this SerpApi wrapper around it) works in two
        steps, same as the browser flow: search returns outbound options
        with a departure_token each; you then re-query with that token to
        get matching return options, whose price is the TOTAL round-trip
        price (not just the return leg).

        top_n_outbound controls how many of the cheapest outbound options
        get a return-leg lookup - each one is an extra API call

        children_ages is required (one age per child, 0-17) whenever
        children > 0. Google Flights has no "age" input of its own - it only
        takes adults/children/infants_on_lap counts - so each age is routed
        into the bucket it actually searches as (see _passenger_buckets).
        """
        if children > 0 and (not children_ages or len(children_ages) != children):
            raise SerpApiFlightsError(
                f"children={children} but children_ages has "
                f"{len(children_ages) if children_ages else 0} entries - "
                f"one age (0-17) is required per child"
            )

        real_adults, real_children, infants_on_lap = self._passenger_buckets(adults, children_ages or [])

        base_params = {
            "engine": "google_flights",
            "departure_id": origin,
            "arrival_id": destination,
            "outbound_date": outbound_date,
            "return_date": return_date,
            "type": "1",  # round trip
            "adults": real_adults,
            "children": real_children,
            "infants_on_lap": infants_on_lap,
            "currency": currency,
            "hl": "en",
        }

        outbound_results = self._safe_search(base_params)
        if "error" in outbound_results:
            raise SerpApiFlightsError(outbound_results["error"])

        outbound_itineraries = (
            outbound_results.get("best_flights", []) + outbound_results.get("other_flights", [])
        )
        if not outbound_itineraries:
            return []

        outbound_sorted = sorted(outbound_itineraries, key=lambda o: o.get("price", float("inf")))

        round_trips: list[dict] = []
        for outbound in outbound_sorted[:top_n_outbound]:
            departure_token = outbound.get("departure_token")
            if not departure_token:
                continue

            return_params = {**base_params, "departure_token": departure_token}
            return_results = self._safe_search(return_params)
            if "error" in return_results:
                continue

            return_itineraries = (
                return_results.get("best_flights", []) + return_results.get("other_flights", [])
            )
            if not return_itineraries:
                continue

            # Take the cheapest return option for this outbound leg -
            # its price is already the full round-trip total.
            cheapest_return = min(return_itineraries, key=lambda o: o.get("price", float("inf")))
            round_trips.append(self._to_round_trip_dict(outbound, cheapest_return, currency, outbound_date, return_date))

        return round_trips

    @staticmethod
    def _passenger_buckets(adults: int, children_ages: list[int]) -> tuple[int, int, int]:
        """Maps each child's age into the passenger bucket Google Flights
        actually searches with: under 2 flies as an infant on lap, 2-11 as
        a child, 12+ counts as a full adult. Returns (adults, children, infants_on_lap).
        """
        extra_adults = sum(1 for age in children_ages if age > 11)
        infants_on_lap = sum(1 for age in children_ages if age < 2)
        real_children = len(children_ages) - extra_adults - infants_on_lap
        return adults + extra_adults, real_children, infants_on_lap

    @staticmethod
    def _to_round_trip_dict(outbound: dict, return_leg: dict, currency: str, outbound_date: str, return_date: str) -> dict:
        out_legs = outbound.get("flights", [])
        ret_legs = return_leg.get("flights", [])
        out_first, out_last = out_legs[0], out_legs[-1]
        ret_first, ret_last = ret_legs[0], ret_legs[-1]

        origin_airport = out_first.get("departure_airport", {}).get("id", "")
        destination_airport = out_last.get("arrival_airport", {}).get("id", "")
        origin_coords = _AIRPORTS.get(origin_airport)
        destination_coords = _AIRPORTS.get(destination_airport)

        return {
            "airline_outbound": out_first.get("airline", "Unknown"),
            "airline_return": ret_first.get("airline", "Unknown"),
            "price": float(return_leg.get("price", 0)),  # total round-trip price
            "currency": currency,
            "outbound_departure_time": out_first.get("departure_airport", {}).get("time", ""),
            "outbound_arrival_time": out_last.get("arrival_airport", {}).get("time", ""),
            "return_departure_time": ret_first.get("departure_airport", {}).get("time", ""),
            "return_arrival_time": ret_last.get("arrival_airport", {}).get("time", ""),
            "origin_airport": origin_airport,
            "destination_airport": destination_airport,
            "origin_latitude": origin_coords["lat"] if origin_coords else None,
            "origin_longitude": origin_coords["lon"] if origin_coords else None,
            "destination_latitude": destination_coords["lat"] if destination_coords else None,
            "destination_longitude": destination_coords["lon"] if destination_coords else None,
            "outbound_stops": max(len(out_legs) - 1, 0),
            "return_stops": max(len(ret_legs) - 1, 0),
            # final booking_token, needed for fetch_baggage_price on a round trip
            "booking_token": return_leg.get("booking_token"),
            "seats_available": None,
            # Google Flights doesn't hand out a real per-offer booking deep
            # link without an extra paid SerpApi call. Rather than add that
            # extra call/infra, build a plain Google Flights SEARCH url
            # from data we already have - it lands the user on the real,
            # live search for this exact route/dates, not a specific seat,
            # but needs nothing new to build.
            "booking_url": GoogleFlightsClient._search_url(origin_airport, destination_airport, outbound_date, return_date),
        }

    @staticmethod
    def _search_url(origin_airport: str, destination_airport: str, outbound_date: str, return_date: str) -> str:
        query = quote(f"Flights from {origin_airport} to {destination_airport} on {outbound_date} through {return_date}")
        return f"https://www.google.com/travel/flights?q={query}"

    def _safe_search(self, params: dict) -> dict:
        """Wraps the raw serpapi call so HTTP errors surface their real
        response body instead of a bare 400 with no explanation, and so
        callers only ever need to catch SerpApiFlightsError.
        """
        try:
            return self._client.search(params)
        except Exception as exc:  # serpapi.exceptions.HTTPError and friends
            detail = self._extract_error_detail(exc)
            raise SerpApiFlightsError(f"SerpApi request failed: {detail}") from exc

    @staticmethod
    def _extract_error_detail(exc: Exception) -> str:
        """Digs the actual response body out of a wrapped HTTP error.

        The serpapi library re-raises the underlying requests error in a
        few different ways depending on version (explicit `raise ... from`,
        implicit chaining, or passing it as a constructor argument), so we
        check all three places rather than assuming one.
        """
        candidates = [
            getattr(exc, "__cause__", None),
            getattr(exc, "__context__", None),
            exc.args[0] if exc.args else None,
        ]
        for candidate in candidates:
            response = getattr(candidate, "response", None)
            if response is not None:
                return response.text
        return str(exc)

    def fetch_baggage_price(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        booking_token: str,
        return_date: str | None = None,
    ) -> str:
        """Second/third call needed to get baggage pricing for one specific
        offer. Pass return_date for round trips (uses the final booking_token
        from search_round_trip), or leave it None for one-way offers.

        Google Flights only exposes baggage_prices once you pin a single
        itinerary via its booking_token - it is not part of the initial
        search results. This makes an extra API call per offer
        """
        params = {
            "engine": "google_flights",
            "departure_id": origin,
            "arrival_id": destination,
            "outbound_date": departure_date,
            "type": "1" if return_date else "2",
            "currency": "EUR",
            "hl": "en",
            "booking_token": booking_token,
        }
        if return_date:
            params["return_date"] = return_date

        try:
            results = self._safe_search(params)
        except SerpApiFlightsError:
            return "unavailable"

        if "error" in results:
            return "unavailable"

        booking_options = results.get("booking_options", [])
        if not booking_options:
            return "unavailable"

        # baggage_prices is a list of free-text strings, e.g. "1 free carry-on",
        # "$35 checked bag" - Google does not expose it as a clean numeric field,
        # so we just join whatever text is available for the cheapest option.
        first_option = booking_options[0].get("together") or booking_options[0]
        baggage_info = first_option.get("baggage_prices", [])
        return "; ".join(baggage_info) if baggage_info else "no baggage info"
