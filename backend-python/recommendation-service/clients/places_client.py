"""Client for finding real, nearby businesses via the official Google
Places API - Text Search endpoint.

This returns real ratings and review counts, which the itinerary prompt
can actually use to prefer well-reviewed places
"""
from __future__ import annotations

import os

import requests

SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"

# Place Photo media endpoint - resolves a photo resource name (returned in
# the search response's places.photos) to an actual image URL. {photo_name}
# is itself a path like "places/XXX/photos/YYY".
PHOTO_MEDIA_URL = "https://places.googleapis.com/v1/{photo_name}/media"

# Only request the fields we actually use

# places.businessStatus is requested specifically so search_nearby can
# drop permanently/temporarily closed businesses before they ever reach the itinerary prompt
# places.id + places.photos are what let the caller persist the place and
# its photos afterwards (see places_repository) - photos here are only
# resource names, the actual image URLs need a second call (fetch_photo_url).
FIELD_MASK = ",".join([
    "places.id",
    "places.displayName",
    "places.formattedAddress",
    "places.location",
    "places.rating",
    "places.userRatingCount",
    "places.priceLevel",
    "places.types",
    "places.businessStatus",
    "places.googleMapsUri",
    "places.photos",
])

# Google's businessStatus enum: "OPERATIONAL", "CLOSED_TEMPORARILY",
# "CLOSED_PERMANENTLY". Anything not OPERATIONAL is dropped - a
# temporarily closed place (renovation, seasonal) is just as useless for
# a specific travel date as a permanently closed one.
_CLOSED_STATUSES = {"CLOSED_TEMPORARILY", "CLOSED_PERMANENTLY"}

_PRICE_LEVEL_LABELS = {
    "PRICE_LEVEL_FREE": "free",
    "PRICE_LEVEL_INEXPENSIVE": "$",
    "PRICE_LEVEL_MODERATE": "$$",
    "PRICE_LEVEL_EXPENSIVE": "$$$",
    "PRICE_LEVEL_VERY_EXPENSIVE": "$$$$",
}


class GoogleMapsPlacesError(Exception):
    """Raised when the Places API returns an error or an unusable response."""


class GoogleMapsPlacesClient:
    def __init__(self, api_key: str | None = None) -> None:
        key = api_key or os.environ.get("GOOGLE_MAPS_API_KEY")
        if not key:
            raise GoogleMapsPlacesError("GOOGLE_MAPS_API_KEY is not set")
        self._api_key = key

    def search_nearby(
        self, query: str, latitude: float, longitude: float, radius_meters: float = 1500, max_results: int = 10
    ) -> list[dict]:
        """Real places matching `query`, biased toward a circle around
        (latitude, longitude). Text Search's locationBias is a soft
        preference, not a hard filter - results slightly outside the
        radius can still appear if they're a strong match for the query.
        """
        body = {
            "textQuery": query,
            "locationBias": {
                "circle": {
                    "center": {"latitude": latitude, "longitude": longitude},
                    "radius": radius_meters,
                }
            },
            "maxResultCount": max_results,
        }
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self._api_key,
            "X-Goog-FieldMask": FIELD_MASK,
        }

        try:
            response = requests.post(SEARCH_URL, json=body, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            raise GoogleMapsPlacesError(self._extract_error_detail(exc)) from exc
        except ValueError as exc:
            raise GoogleMapsPlacesError(f"Unparseable response: {exc}") from exc

        open_places = [
            p for p in data.get("places", [])
            if p.get("businessStatus", "OPERATIONAL") not in _CLOSED_STATUSES
        ]
        return [self._to_dict(p) for p in open_places]

    @staticmethod
    def _to_dict(p: dict) -> dict:
        location = p.get("location", {})
        return {
            "name": p.get("displayName", {}).get("text", "Unknown"),
            "type": ", ".join(p.get("types", [])[:2]),
            "address": p.get("formattedAddress", ""),
            "rating": p.get("rating"),
            "reviews": p.get("userRatingCount"),
            "price": _PRICE_LEVEL_LABELS.get(p.get("priceLevel", ""), ""),
            "latitude": location.get("latitude"),
            "longitude": location.get("longitude"),
            "hours": "",  # opening hours omitted from the field mask to keep calls cheap; add if needed
            "maps_url": p.get("googleMapsUri", ""),
            "place_id": p.get("id", ""),  # Google's stable place id - used to dedupe on persist
            "photos": [photo["name"] for photo in p.get("photos", []) if photo.get("name")],
        }

    def fetch_photo_url(self, photo_name: str, max_width_px: int = 1000) -> str:
        """Resolves a photo resource name (one entry of a search_nearby
        result's "photos") to a direct image URL via the Place Photo media
        endpoint.

        skipHttpRedirect=true makes Google return a small JSON body with a
        photoUri field instead of a 302 redirect to the image itself, so we
        capture the URL without downloading the image. The API key stays in
        the X-Goog-Api-Key header, never in the query string.

        The returned photoUri is short-lived - fine to store directly if
        photos are only shown transiently; for durable storage, download it
        and re-host it (see places_repository._resolve_storage_url).
        """
        url = PHOTO_MEDIA_URL.format(photo_name=photo_name)
        headers = {"X-Goog-Api-Key": self._api_key}
        params = {"maxWidthPx": max_width_px, "skipHttpRedirect": "true"}
        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            return response.json().get("photoUri", "")
        except requests.RequestException as exc:
            raise GoogleMapsPlacesError(self._extract_error_detail(exc)) from exc
        except ValueError as exc:
            raise GoogleMapsPlacesError(f"Unparseable response: {exc}") from exc

    @staticmethod
    def _extract_error_detail(exc: requests.RequestException) -> str:
        response = getattr(exc, "response", None)
        return response.text if response is not None else str(exc)
