"""Postgres access for edit-service.

Same DB_HOST/... env convention and postgres-main target as the other Python
services (writes go to main; hot/cold are read replicas). edit-service reads
the current version's stored generation input (ai_jobs.prompt) and result
(ai_results.raw_response), creates the next travel_version, and resolves a few
reference lookups (airport -> city) needed to re-search flights when dates
change.
"""
from __future__ import annotations

import json
import os
from contextlib import contextmanager

from dotenv import load_dotenv

import psycopg2
import psycopg2.extras

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "postgres-main"),
    "port": os.getenv("DB_PORT", "5432"),
    "dbname": os.getenv("DB_NAME", "traveldb"),
    "user": os.getenv("DB_USER", "appuser"),
    "password": os.getenv("DB_PASSWORD", ""),
    "client_encoding": "UTF8",
}


class EditDataError(Exception):
    """Raised when the travel/version data an edit needs isn't found or usable."""


@contextmanager
def get_connection():
    conn = psycopg2.connect(**DB_CONFIG, connect_timeout=5)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def check_connection() -> None:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()


def _as_dict(value) -> dict:
    """ai_jobs.prompt is text and ai_results.raw_response is json; normalize
    either (str or already-parsed) into a dict."""
    if value is None:
        return {}
    if isinstance(value, (dict, list)):
        return value
    return json.loads(value)


def load_current_version_context(cur, travel_id: str) -> dict:
    """Everything the edit needs from the current (is_current) version of a
    travel: the version row, the stored generation input (prior groups /
    preferences / pace / offers) and the previous proposal to revise.

    Raises EditDataError with a clear message when the travel has no current
    version or that version was never successfully generated (so there's
    nothing to edit yet).
    """
    cur.execute(
        """
        SELECT id, version_number
        FROM travel_versions
        WHERE travel_id = %s AND is_current = true
        ORDER BY version_number DESC
        LIMIT 1
        """,
        (travel_id,),
    )
    row = cur.fetchone()
    if row is None:
        raise EditDataError(f"travel {travel_id} has no current version to edit")
    version_id, version_number = row

    # Latest ai_job for this version carries the exact TripPlanningRequest that
    # produced it (groups/preferences/pace/flight_offers/hotel_offers).
    cur.execute(
        "SELECT id, prompt FROM ai_jobs WHERE travel_version_id = %s ORDER BY started_at DESC LIMIT 1",
        (version_id,),
    )
    job_row = cur.fetchone()
    if job_row is None:
        raise EditDataError(f"current version {version_id} has no generation job to edit from")
    ai_job_id, prompt = job_row
    prior_request = _as_dict(prompt)

    # The previous proposal = the successful option rows (version > 0; version 0
    # is the failure sentinel written by jobs.fail_job).
    cur.execute(
        "SELECT raw_response FROM ai_results WHERE job_id = %s AND version > 0 ORDER BY version",
        (ai_job_id,),
    )
    options = [_as_dict(r[0]) for r in cur.fetchall()]

    return {
        "version_id": str(version_id),
        "version_number": version_number,
        "prior_request": prior_request,
        "previous_proposal": {"options": options},
    }


def get_travel_dates(cur, travel_id: str) -> tuple[str | None, str | None]:
    cur.execute("SELECT start_date, end_date FROM travels WHERE id = %s", (travel_id,))
    row = cur.fetchone()
    if row is None:
        raise EditDataError(f"travel {travel_id} not found")
    start, end = row
    return (start.isoformat() if start else None, end.isoformat() if end else None)


def create_next_version(cur, travel_id: str, created_by: str, description: str | None) -> dict:
    """Flips the previous current version off and inserts the next version
    (max version_number + 1) as the new current one. Returns the new id +
    number."""
    cur.execute(
        "SELECT COALESCE(MAX(version_number), 0) FROM travel_versions WHERE travel_id = %s",
        (travel_id,),
    )
    next_number = cur.fetchone()[0] + 1

    cur.execute(
        "UPDATE travel_versions SET is_current = false WHERE travel_id = %s AND is_current = true",
        (travel_id,),
    )
    cur.execute(
        """
        INSERT INTO travel_versions (id, travel_id, version_number, description, created_by, is_current, created_at)
        VALUES (gen_random_uuid(), %s, %s, %s, %s, true, now())
        RETURNING id
        """,
        (travel_id, next_number, description, created_by),
    )
    new_id = cur.fetchone()[0]
    return {"version_id": str(new_id), "version_number": next_number}


def update_travel_dates(cur, travel_id: str, start_date: str, end_date: str) -> None:
    cur.execute(
        "UPDATE travels SET start_date = %s, end_date = %s, updated_at = now() WHERE id = %s",
        (start_date, end_date, travel_id),
    )


def city_name_for_iata(cur, iata_code: str) -> str | None:
    """Origin city name for an IATA airport code - used to re-search flights
    when dates change (FlightSearchRequest wants a free-text origin_city)."""
    if not iata_code:
        return None
    cur.execute(
        """
        SELECT c.name
        FROM airports a
        JOIN cities c ON c.id = a.city_id
        WHERE a.iata_code = %s
        LIMIT 1
        """,
        (iata_code,),
    )
    row = cur.fetchone()
    return row[0] if row else None
