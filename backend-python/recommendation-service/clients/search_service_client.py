"""HTTP client for calling search-service from recommendation-service.

These are separate deployments (see infra/k8s) - search-service owns the
SERPAPI_API_KEY and the SerpApi client, so anything needing a live SerpApi
call (like baggage pricing) has to go over the network rather than through
a direct Python import.
"""
from __future__ import annotations

import os

import requests

DEFAULT_BASE_URL = "http://search-service:8000"  # in-cluster k8s Service DNS name


class SearchServiceClient:
    def __init__(self, base_url: str | None = None) -> None:
        self._base_url = (base_url or os.environ.get("SEARCH_SERVICE_URL") or DEFAULT_BASE_URL).rstrip("/")

    def fetch_baggage_price(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        booking_token: str,
        return_date: str | None = None,
    ) -> str:
        """Wraps POST /api/v1/search/flights/baggage-price. Returns
        "unavailable" on any failure (network error, search-service down,
        SerpApi error) rather than raising - baggage info is a nice-to-have
        add-on to a finished itinerary, not worth failing the whole option
        generation over.
        """
        body = {
            "origin": origin,
            "destination": destination,
            "departure_date": departure_date,
            "booking_token": booking_token,
            "return_date": return_date,
        }
        try:
            response = requests.post(f"{self._base_url}/api/v1/search/flights/baggage-price", json=body, timeout=15)
            response.raise_for_status()
            return response.json().get("baggage_info", "unavailable")
        except requests.RequestException:
            return "unavailable"

    def fetch_property_address(
        self,
        property_token: str,
        location: str,
        check_in_date: str,
        check_out_date: str,
        adults: int = 1,
        children: int = 0,
    ) -> str:
        """Wraps POST /api/v1/search/hotels/property-details. Returns "" on
        any failure - the caller keeps whatever address it already had
        rather than overwriting it with something worse.
        """
        body = {
            "property_token": property_token,
            "location": location,
            "check_in_date": check_in_date,
            "check_out_date": check_out_date,
            "adults": adults,
            "children": children,
        }
        try:
            response = requests.post(f"{self._base_url}/api/v1/search/hotels/property-details", json=body, timeout=15)
            response.raise_for_status()
            return response.json().get("address", "")
        except requests.RequestException:
            return ""

    def search_web(self, query: str, max_results: int = 5) -> list[dict]:
        """Wraps POST /api/v1/search/web. Returns [] on any failure - a
        failed grounding search shouldn't crash a whole itinerary option;
        the caller (Claude, via the tool result) sees an empty result set
        and can say a price is an estimate rather than state a stale or
        made-up number as fact.
        """
        body = {"query": query, "max_results": max_results}
        try:
            response = requests.post(f"{self._base_url}/api/v1/search/web", json=body, timeout=15)
            response.raise_for_status()
            return response.json().get("results", [])
        except requests.RequestException:
            return []