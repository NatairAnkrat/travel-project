"""Client for getting real travel time/distance between two points via the
official Google Routes API (the current version of Directions API).

This includes REAL public-transit routing (actual U-Bahn/S-Bahn/bus lines and schedules),
not a distance-based estimate.
"""
from __future__ import annotations

import os

import requests

COMPUTE_ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"

_TRAVEL_MODES = {
    "walking": "WALK",
    "transit": "TRANSIT",
    "driving": "DRIVE",
    "cycling": "BICYCLE",
}

FIELD_MASK = "routes.duration,routes.distanceMeters,routes.travelAdvisory.transitFare"


class GoogleMapsDirectionsError(Exception):
    """Raised when the Routes API returns an error or an unusable response."""


class GoogleMapsDirectionsClient:
    def __init__(self, api_key: str | None = None) -> None:
        key = api_key or os.environ.get("GOOGLE_MAPS_API_KEY")
        if not key:
            raise GoogleMapsDirectionsError("GOOGLE_MAPS_API_KEY is not set")
        self._api_key = key

    def get_directions(
        self,
        origin_lat: float,
        origin_lon: float,
        dest_lat: float,
        dest_lon: float,
        mode: str = "walking",
    ) -> dict:
        travel_mode = _TRAVEL_MODES.get(mode)
        if travel_mode is None:
            raise GoogleMapsDirectionsError(f"Unknown mode '{mode}' - must be one of {list(_TRAVEL_MODES)}")

        body = {
            "origin": {"location": {"latLng": {"latitude": origin_lat, "longitude": origin_lon}}},
            "destination": {"location": {"latLng": {"latitude": dest_lat, "longitude": dest_lon}}},
            "travelMode": travel_mode,
        }
        if travel_mode == "DRIVE":
            body["routingPreference"] = "TRAFFIC_AWARE"

        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self._api_key,
            "X-Goog-FieldMask": FIELD_MASK,
        }

        try:
            response = requests.post(COMPUTE_ROUTES_URL, json=body, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            raise GoogleMapsDirectionsError(self._extract_error_detail(exc)) from exc
        except ValueError as exc:
            raise GoogleMapsDirectionsError(f"Unparseable response: {exc}") from exc

        routes = data.get("routes", [])
        if not routes:
            return {
                "mode": mode, "distance_meters": None, "duration_minutes": None,
                "formatted_distance": "unknown", "formatted_duration": "unknown",
                "transit_fare_eur": None, "is_estimated": False,
            }

        route = routes[0]
        duration_seconds = self._parse_duration_seconds(route.get("duration", "0s"))
        distance_meters = route.get("distanceMeters", 0)
        transit_fare = route.get("travelAdvisory", {}).get("transitFare")

        return {
            "mode": mode,
            "distance_meters": distance_meters,
            "duration_minutes": round(duration_seconds / 60),
            "formatted_distance": f"{distance_meters / 1000:.1f} km",
            "formatted_duration": f"{round(duration_seconds / 60)} min",
            # Real fare for THIS exact journey, from Google's own transit fare
            # data - only present when mode="transit" and Google could resolve
            # fare info for every leg (depends on whether BVG publishes fare
            # data to Google; not guaranteed). Null otherwise - not an error,
            # just "no live fare for this specific route", fall back to
            # search_web-grounded fare-product prices in that case.
            "transit_fare_eur": self._parse_fare_eur(transit_fare),
            "is_estimated": False,  # real routed result, not a fallback estimate
        }

    @staticmethod
    def _parse_duration_seconds(duration_str: str) -> int:
        # Routes API returns durations like "1234s" - a plain string
        return int(duration_str.rstrip("s")) if duration_str.endswith("s") else 0

    @staticmethod
    def _parse_fare_eur(transit_fare: dict | None) -> float | None:
        # transitFare is a Money object: {"currencyCode": "EUR", "units": "4", "nanos": 500000000}
        # units is int64-as-string (protobuf JSON convention), nanos is
        # billionths of a unit - only trust it if it's actually in EUR,
        # since every cost_eur field downstream assumes that currency.
        if not transit_fare or transit_fare.get("currencyCode") != "EUR":
            return None
        units = int(transit_fare.get("units", 0) or 0)
        nanos = transit_fare.get("nanos", 0) or 0
        return round(units + nanos / 1e9, 2)

    @staticmethod
    def _extract_error_detail(exc: requests.RequestException) -> str:
        response = getattr(exc, "response", None)
        return response.text if response is not None else str(exc)
