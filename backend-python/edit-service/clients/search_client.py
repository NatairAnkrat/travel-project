"""HTTP client for search-service - only used when an edit changes dates and
we have to re-price flights and hotels for the new dates."""
from __future__ import annotations

import os

import requests

DEFAULT_BASE_URL = "http://search-service:8000"  # in-cluster k8s Service DNS


class SearchServiceError(Exception):
    pass


class SearchClient:
    def __init__(self, base_url: str | None = None) -> None:
        self._base_url = (base_url or os.environ.get("SEARCH_SERVICE_URL") or DEFAULT_BASE_URL).rstrip("/")

    def search_flights(self, body: dict) -> dict:
        return self._post("/api/v1/search/flights", body)

    def search_hotels(self, body: dict) -> dict:
        return self._post("/api/v1/search/hotels", body)

    def _post(self, path: str, body: dict) -> dict:
        try:
            resp = requests.post(f"{self._base_url}{path}", json=body, timeout=60)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            raise SearchServiceError(f"{path} failed: {exc}") from exc
