"""Client for searching accommodation via SerpApi's Google Hotels engine.

Mirrors the structure of google_flights_client.py: same error-handling
pattern, same idea of a cheap "search" call followed by a more expensive
"details" call only for the offers that actually matter.
"""
from __future__ import annotations

import os
from datetime import date
from urllib.parse import quote

import serpapi


class SerpApiHotelsError(Exception):
    """Raised when SerpApi returns an error status for a search."""


class GoogleHotelsClient:
    # The only accessibility filter Google Hotels currently exposes
    WHEELCHAIR_ACCESSIBLE_AMENITY_ID = "53"

    def __init__(self, api_key: str | None = None) -> None:
        key = api_key or os.environ.get("SERPAPI_API_KEY")
        if not key:
            raise SerpApiHotelsError("SERPAPI_API_KEY is not set")
        self._client = serpapi.Client(api_key=key)

    # Google Hotels' "type" field only ever returns "hotel" or "vacation
    # rental" - there's no separate "hostel" category at the data level,
    # even when the property's own name says "Hostel". We derive a more
    # specific label from the name as a best-effort display hint - this
    # is cosmetic only, it doesn't affect search/filtering.
    _CATEGORY_KEYWORDS = {
        "hostel": "hostel",
        "apartment": "apartment",
        "aparthotel": "apartment",
        "guesthouse": "guesthouse",
        "guest house": "guesthouse",
        "bed and breakfast": "b&b",
        "b&b": "b&b",
    }

    def search(
        self,
        location: str,
        check_in_date: str,
        check_out_date: str,
        adults: int = 1,
        children: int = 0,
        children_ages: list[int] | None = None,
        currency: str = "EUR",
        wheelchair_accessible: bool = False,
    ) -> list[dict]:
        """Searches properties for a location and date range.

        Returns price/rating/amenity-summary info and a property_token for
        each result - full address and house rules require a separate
        get_property_details() call per property

        children_ages is REQUIRED (one age per child, 1-17) whenever
        children > 0 - Google Hotels rejects the search otherwise.
        """
        if children > 0 and (not children_ages or len(children_ages) != children):
            raise SerpApiHotelsError(
                f"children={children} but children_ages has "
                f"{len(children_ages) if children_ages else 0} entries - "
                f"one age (1-17) is required per child"
            )

        params = {
            "engine": "google_hotels",
            "q": location,
            "check_in_date": check_in_date,
            "check_out_date": check_out_date,
            "adults": adults,
            "children": children,
            "currency": currency,
            "hl": "en",
        }
        if children > 0:
            params["children_ages"] = ",".join(str(age) for age in children_ages)
        if wheelchair_accessible:
            params["amenities"] = self.WHEELCHAIR_ACCESSIBLE_AMENITY_ID

        results = self._safe_search(params)
        if "error" in results:
            raise SerpApiHotelsError(results["error"])

        nights = (date.fromisoformat(check_out_date) - date.fromisoformat(check_in_date)).days

        properties = results.get("properties", [])
        return [self._to_dict(p, currency, nights, location, check_in_date, check_out_date) for p in properties]

    @classmethod
    def _guess_category(cls, name: str, google_type: str) -> str:
        name_lower = name.lower()
        for keyword, label in cls._CATEGORY_KEYWORDS.items():
            if keyword in name_lower:
                return label
        return google_type  # fall back to Google's own "hotel"/"vacation rental"

    @classmethod
    def _to_dict(cls, p: dict, currency: str, nights: int, location: str, check_in_date: str, check_out_date: str) -> dict:
        rate_per_night = p.get("rate_per_night", {})
        total_rate = p.get("total_rate", {})

        exact_total = total_rate.get("extracted_lowest")
        nightly = rate_per_night.get("extracted_lowest")

        # Fall back to rate_per_night * nights if total_rate is missing for
        # some result (happens for a handful of listings)
        total_price = exact_total if exact_total is not None else (
            nightly * nights if nightly is not None else None
        )

        gps = p.get("gps_coordinates", {})
        name = p.get("name", "Unknown")

        return {
            "name": name,
            "type": cls._guess_category(name, p.get("type", "")),
            "rate_per_night": nightly,
            "total_price": total_price,
            "currency": currency,
            "check_in_time": p.get("check_in_time", ""),
            "check_out_time": p.get("check_out_time", ""),
            "overall_rating": p.get("overall_rating"),
            "hotel_class": p.get("extracted_hotel_class"),
            "amenities_summary": ", ".join(p.get("amenities", [])[:6]),
            "property_token": p.get("property_token"),
            "latitude": gps.get("latitude"),
            "longitude": gps.get("longitude"),
            # SerpApi's general search results already include "link" for
            # most properties (usually the property's own website) - use
            # it directly when present. When it's missing (happens for a
            # handful of listings), fall back to a plain Google Hotels
            # search URL built from data we already have
            "booking_url": p.get("link") or cls._fallback_search_url(name, location, check_in_date, check_out_date),
        }

    @staticmethod
    def _fallback_search_url(name: str, location: str, check_in_date: str, check_out_date: str) -> str:
        query = quote(f"{name} {location}")
        return (
            f"https://www.google.com/travel/hotels?q={query}"
            f"&checkin={check_in_date}&checkout={check_out_date}"
        )


    def get_property_details(
        self,
        property_token: str,
        location: str,
        check_in_date: str,
        check_out_date: str,
        adults: int = 1,
        children: int = 0,
        currency: str = "EUR",
    ) -> dict:
        """Second call needed for address and house rules.

        Google Hotels only returns gps_coordinates in the main search
        results - the actual street address, phone number, and rule/policy
        text only come back once you pin a specific property via its
        property_token, mirroring the same "search first, drill down
        second" pattern as flight offers.
        """
        params = {
            "engine": "google_hotels",
            "q": location,
            "check_in_date": check_in_date,
            "check_out_date": check_out_date,
            "adults": adults,
            "children": children,
            "currency": currency,
            "hl": "en",
            "property_token": property_token,
        }

        try:
            results = self._safe_search(params)
        except SerpApiHotelsError:
            return {}

        if "error" in results:
            return {}

        return {
            "address": results.get("address", ""),
            "phone": results.get("phone", ""),
            "description": results.get("description", ""),
            # essential_info holds short policy-adjacent facts (e.g.
            # "Entire house", "Sleeps 2", "1 bedroom") - not full legal
            # house rules text, which Google Hotels does not expose as a
            # separate structured field.
            "essential_info": "; ".join(results.get("essential_info", [])),
            "excluded_amenities": ", ".join(results.get("excluded_amenities", [])),
        }

    def _safe_search(self, params: dict) -> dict:
        """Wraps the raw serpapi call so HTTP errors surface their real
        response body instead of a bare 400 with no explanation.
        """
        try:
            return self._client.search(params)
        except Exception as exc:  # serpapi.exceptions.HTTPError and friends
            detail = self._extract_error_detail(exc)
            raise SerpApiHotelsError(f"SerpApi request failed: {detail}") from exc

    @staticmethod
    def _extract_error_detail(exc: Exception) -> str:
        """Digs the actual response body out of a wrapped HTTP error -
        see google_flights_client.py for why all three places are checked.
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
