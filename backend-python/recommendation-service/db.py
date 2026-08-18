"""Postgres access for recommendation-service.

Uses the same DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD env var
convention as backend-python's main.py, pointed at postgres-main (writes
must go to main - see infra/k8s/postgres: hot/cold are streaming replicas
of main, not separate databases).

Writes go through the existing schema (search_requests / ai_jobs /
ai_results) instead of a bespoke table, so this data shows up in the same
place as anything backend-java/backend-python already write.
"""
from __future__ import annotations

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
    """Raises if main DB is unreachable - used by /health."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()


def get_or_create_provider(cur, name: str, provider_type: str, base_url: str) -> str:
    """Returns providers.id for `name`, inserting a row on first use.
    Avoids requiring a separate seed migration just to register
    'anthropic' / 'google_flights' / 'google_hotels' as known providers.
    """
    cur.execute("SELECT id FROM providers WHERE name = %s", (name,))
    row = cur.fetchone()
    if row:
        return row[0]

    cur.execute(
        """
        INSERT INTO providers (id, name, type, base_url, status, created_at)
        VALUES (gen_random_uuid(), %s, %s, %s, 'active', now())
        RETURNING id
        """,
        (name, provider_type, base_url),
    )
    return cur.fetchone()[0]


def get_or_create_ai_model(cur, provider_id: str, model_name: str) -> str:
    cur.execute(
        "SELECT id FROM ai_models WHERE provider_id = %s AND model_name = %s",
        (provider_id, model_name),
    )
    row = cur.fetchone()
    if row:
        return row[0]

    cur.execute(
        """
        INSERT INTO ai_models (id, provider_id, model_name, is_active, created_at)
        VALUES (gen_random_uuid(), %s, %s, true, now())
        RETURNING id
        """,
        (provider_id, model_name),
    )
    return cur.fetchone()[0]
