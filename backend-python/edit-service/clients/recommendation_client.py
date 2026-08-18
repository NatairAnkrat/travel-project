"""HTTP client for recommendation-service.

edit-service owns the version lifecycle and the "what changed" context, but
generation itself stays in recommendation-service (one Claude engine, with the
prompt-caching / grounding / effort optimizations). We hand it the new
travel_version plus the edit context and let it run its normal async job.
"""
from __future__ import annotations

import os

import requests

DEFAULT_BASE_URL = "http://recommendation-service:8000"  # in-cluster k8s Service DNS


class RecommendationServiceError(Exception):
    pass


class RecommendationClient:
    def __init__(self, base_url: str | None = None) -> None:
        self._base_url = (base_url or os.environ.get("RECOMMENDATION_SERVICE_URL") or DEFAULT_BASE_URL).rstrip("/")

    def start_generation(
        self,
        travel_version_id: str,
        requested_by: str,
        groups: list[dict],
        user_preferences: str,
        travel_pace: str,
        flight_offers: list[dict],
        hotel_offers: list[dict],
        previous_itinerary: dict | None,
        edit_instruction: str | None,
    ) -> str:
        """Kicks off an (edit-aware) generation and returns its job id. Raises
        on any non-2xx - unlike a best-effort grounding call, a failed start
        means the edit itself failed and the caller must surface it."""
        body = {
            "travel_version_id": travel_version_id,
            "requested_by": requested_by,
            "groups": groups,
            "user_preferences": user_preferences,
            "travel_pace": travel_pace,
            "flight_offers": flight_offers,
            "hotel_offers": hotel_offers,
            "previous_itinerary": previous_itinerary,
            "edit_instruction": edit_instruction,
        }
        try:
            resp = requests.post(f"{self._base_url}/api/v1/recommendations", json=body, timeout=30)
            resp.raise_for_status()
            return resp.json()["job_id"]
        except requests.RequestException as exc:
            raise RecommendationServiceError(f"failed to start generation: {exc}") from exc
        except (KeyError, ValueError) as exc:
            raise RecommendationServiceError(f"unexpected response starting generation: {exc}") from exc

    def get_status(self, job_id: str) -> dict | None:
        """Proxies recommendation-service's job status. Returns None on 404
        (unknown job), raises on other transport failures."""
        try:
            resp = requests.get(f"{self._base_url}/api/v1/recommendations/{job_id}", timeout=15)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            raise RecommendationServiceError(f"failed to fetch job status: {exc}") from exc
