"""Persists the real places found during itinerary generation (restaurants,
attractions - anything search_nearby_places returned) into `places`, and
their photos into `place_photos`.

Photos attach to a place, not to a restaurant/attraction row directly:
that's how the schema models it (place_photos.place_id -> places.id), so one
physical venue has a single photo set no matter how many itineraries point
at it.

places.city_id / country_id are NOT NULL FKs to the reference tables, which
this flow doesn't otherwise carry. They're resolved from the travel's own
destination city (travel_versions -> travels -> destination_city_id ->
cities.country_id) - good enough, since search_nearby_places biases its
results to a circle around that same destination.

Everything here is best-effort: a failure to save a place or a photo must
never sink a job whose itinerary already generated fine, so failures are
caught and logged, not raised.
"""
from __future__ import annotations

import logging

from clients.places_client import GoogleMapsPlacesClient, GoogleMapsPlacesError
from db import get_connection, get_or_create_provider

logger = logging.getLogger(__name__)

# Cap the extra Place Photo media calls per venue - each photo is one HTTP
# call (two, counting the thumbnail), and a handful per place is plenty.
MAX_PHOTOS_PER_PLACE = 3

# Registered lazily via get_or_create_provider, same pattern as 'anthropic'
# in db.py - avoids needing a separate seed migration just to name the source.
GOOGLE_PLACES_PROVIDER = ("google_places", "maps", "https://places.googleapis.com")


def save_found_places(
    travel_version_id: str,
    found_places_by_option: dict[int, list[dict]],
    places_client: GoogleMapsPlacesClient | None = None,
) -> None:
    """Upserts every distinct place found for this travel version and saves
    up to MAX_PHOTOS_PER_PLACE photos each.
    """
    places_by_google_id = _dedupe_places(found_places_by_option)
    if not places_by_google_id:
        return

    client = places_client or _safe_client()

    with get_connection() as conn:
        cur = conn.cursor()

        geo = _get_travel_geo(cur, travel_version_id)
        if geo is None:
            logger.warning(
                "No destination city resolvable for travel_version %s - skipping place persistence",
                travel_version_id,
            )
            cur.close()
            return
        city_id, country_id = geo

        provider_id = get_or_create_provider(cur, *GOOGLE_PLACES_PROVIDER)

        for place in places_by_google_id.values():
            try:
                place_row_id = _upsert_place(cur, place, city_id, country_id)
                if place_row_id is not None:
                    _save_photos(cur, place_row_id, provider_id, place.get("photos", []), client)
            except Exception:  # one bad place shouldn't abort the rest
                logger.exception("Failed to persist place %r", place.get("name"))

        cur.close()


def _dedupe_places(found_places_by_option: dict[int, list[dict]]) -> dict[str, dict]:
    """Collapses the per-option place lists into one dict keyed by Google's
    place_id, so a venue that appears in several options is stored once.
    """
    by_id: dict[str, dict] = {}
    for places in found_places_by_option.values():
        for place in places:
            google_id = place.get("place_id")
            if google_id:
                by_id.setdefault(google_id, place)
    return by_id


def _get_travel_geo(cur, travel_version_id: str) -> tuple[str, str] | None:
    cur.execute(
        """
        SELECT c.id, c.country_id
        FROM travel_versions tv
        JOIN travels t ON t.id = tv.travel_id
        JOIN cities c ON c.id = t.destination_city_id
        WHERE tv.id = %s
        """,
        (travel_version_id,),
    )
    row = cur.fetchone()
    return (row[0], row[1]) if row else None


def _upsert_place(cur, place: dict, city_id: str, country_id: str) -> str | None:
    """Returns places.id for this venue, inserting it on first sight.

    places.latitude/longitude are NOT NULL, so a result missing coordinates
    can't be stored - skipped (returns None) rather than crashing the insert.

    google_place_id has no unique constraint in the schema, so dedupe is a
    SELECT-then-INSERT (like get_or_create_provider) rather than ON CONFLICT.
    """
    latitude, longitude = place.get("latitude"), place.get("longitude")
    if latitude is None or longitude is None:
        return None

    google_place_id = place.get("place_id") or None
    if google_place_id:
        cur.execute("SELECT id FROM places WHERE google_place_id = %s", (google_place_id,))
        row = cur.fetchone()
        if row:
            return row[0]

    cur.execute(
        """
        INSERT INTO places
            (id, city_id, country_id, name, address, latitude, longitude, google_place_id, created_at)
        VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, %s, now())
        RETURNING id
        """,
        (
            city_id,
            country_id,
            place.get("name", "Unknown"),
            place.get("address") or None,
            latitude,
            longitude,
            google_place_id,
        ),
    )
    return cur.fetchone()[0]


def _save_photos(cur, place_id: str, provider_id: str, photo_names: list[str], client) -> None:
    if client is None or not photo_names:
        return

    for photo_name in photo_names[:MAX_PHOTOS_PER_PLACE]:
        cur.execute(
            "SELECT 1 FROM place_photos WHERE place_id = %s AND external_id = %s",
            (place_id, photo_name),
        )
        if cur.fetchone():
            continue  # already stored this exact photo for this place

        try:
            photo_url = client.fetch_photo_url(photo_name, max_width_px=1000)
            thumbnail_url = client.fetch_photo_url(photo_name, max_width_px=200)
        except GoogleMapsPlacesError:
            logger.warning("Could not resolve photo %s - skipping", photo_name)
            continue

        if not photo_url:
            continue

        cur.execute(
            """
            INSERT INTO place_photos
                (id, place_id, provider_id, external_id, photo_url, thumbnail_url, created_at)
            VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, now())
            """,
            (
                place_id,
                provider_id,
                photo_name,
                _resolve_storage_url(photo_url),
                _resolve_storage_url(thumbnail_url) if thumbnail_url else None,
            ),
        )


def _resolve_storage_url(google_photo_uri: str) -> str:
    """SEAM for the storage strategy.

    Right now it stores Google's direct photoUri as-is: simplest, works
    immediately, but the URL is temporary (Google expires it). To switch to
    your own object storage, download google_photo_uri here, upload the
    bytes to your bucket, and return the stable bucket URL instead - nothing
    else in this module has to change.
    """
    return google_photo_uri


def _safe_client() -> GoogleMapsPlacesClient | None:
    try:
        return GoogleMapsPlacesClient()
    except GoogleMapsPlacesError:
        logger.warning("GOOGLE_MAPS_API_KEY not set - places will be saved without photos")
        return None
