"""Client for general web search via SerpApi's Google Search engine.

Used as a grounding tool for time-sensitive facts that don't fit the
flights/hotels domain (e.g. current local transit fare-product prices) -
same "search first, don't trust training data" principle as the flights/
hotels clients, just for arbitrary text queries instead of a specific
vertical.
"""
from __future__ import annotations

import os

import serpapi


class SerpApiSearchError(Exception):
    """Raised when SerpApi returns an error status for a search."""


class GoogleSearchClient:
    def __init__(self, api_key: str | None = None) -> None:
        key = api_key or os.environ.get("SERPAPI_API_KEY")
        if not key:
            raise SerpApiSearchError("SERPAPI_API_KEY is not set")
        self._client = serpapi.Client(api_key=key)

    def search(self, query: str, max_results: int = 5) -> list[dict]:
        """Real, current Google search results for `query` - title/snippet/
        link per organic result, so a caller can ground a time-sensitive
        fact (a price, a policy, an hours-of-operation) instead of relying
        on a model's training data.
        """
        params = {"engine": "google", "q": query, "hl": "en", "num": max_results}

        try:
            results = self._client.search(params)
        except Exception as exc:  # serpapi.exceptions.HTTPError and friends
            detail = self._extract_error_detail(exc)
            raise SerpApiSearchError(f"SerpApi request failed: {detail}") from exc

        if "error" in results:
            raise SerpApiSearchError(results["error"])

        organic = results.get("organic_results", [])[:max_results]
        return [
            {"title": r.get("title", ""), "snippet": r.get("snippet", ""), "link": r.get("link", "")}
            for r in organic
        ]

    @staticmethod
    def _extract_error_detail(exc: Exception) -> str:
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