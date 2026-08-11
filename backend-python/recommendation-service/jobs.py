"""Async job tracking for itinerary generation, backed by the existing
search_requests / ai_jobs / ai_results tables - not a bespoke table.

Flow:
  1. create_job() - inserts a search_requests row (request_type='itinerary',
     status='processing') and one ai_jobs row per tier (status='processing').
     Returns the ai_jobs id list, keyed by tier name, plus the shared
     search_request id used as the public job_id.
  2. The background worker calls recommendation_stage.run(), which
     generates all tiers.
  3. complete_job() writes one ai_results row per generated
     ItineraryOption (raw_response = the full option as JSON) and flips
     ai_jobs.status to 'done'.
  4. fail_job() flips status to 'failed' and records the error as the
     ai_results.summary for visibility.

The ANTHROPIC_MODEL constant matches the model name ClaudeItineraryClient
actually calls, so ai_jobs.model_id points at a real, meaningful ai_models row.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from db import get_connection, get_or_create_ai_model, get_or_create_provider
from itinerary_schemas import ItineraryProposal, TripPlanningRequest

ANTHROPIC_MODEL = "claude-sonnet-5"


@dataclass
class JobHandle:
    search_request_id: str
    ai_job_id: str
    travel_version_id: str


def create_job(travel_version_id: str, requested_by: str, request: TripPlanningRequest) -> JobHandle:
    with get_connection() as conn:
        cur = conn.cursor()

        provider_id = get_or_create_provider(cur, "anthropic", "ai", "https://api.anthropic.com")
        model_id = get_or_create_ai_model(cur, provider_id, ANTHROPIC_MODEL)

        cur.execute(
            """
            INSERT INTO search_requests
                (id, travel_version_id, requested_by, request_type, status, rquid, started_at)
            VALUES (gen_random_uuid(), %s, %s, 'itinerary', 'processing', gen_random_uuid(), now())
            RETURNING id
            """,
            (travel_version_id, requested_by),
        )
        search_request_id = cur.fetchone()[0]

        cur.execute(
            """
            INSERT INTO ai_jobs
                (id, travel_version_id, search_request_id, model_id, prompt, temperature, status, rquid, started_at)
            VALUES (gen_random_uuid(), %s, %s, %s, %s, 0, 'processing', gen_random_uuid(), now())
            RETURNING id
            """,
            (travel_version_id, search_request_id, model_id, json.dumps(request.model_dump(), ensure_ascii=False)),
        )
        ai_job_id = cur.fetchone()[0]

        cur.close()
        return JobHandle(
            search_request_id=str(search_request_id),
            ai_job_id=str(ai_job_id),
            travel_version_id=str(travel_version_id),
        )


def complete_job(handle: JobHandle, proposal: ItineraryProposal) -> None:
    with get_connection() as conn:
        cur = conn.cursor()

        for version, option in enumerate(proposal.options, start=1):
            cur.execute(
                """
                INSERT INTO ai_results (id, job_id, version, summary, raw_response, created_at)
                VALUES (gen_random_uuid(), %s, %s, %s, %s, now())
                """,
                (handle.ai_job_id, version, option.summary, json.dumps(option.model_dump(), ensure_ascii=False)),
            )

        cur.execute(
            "UPDATE ai_jobs SET status = 'done', finished_at = now() WHERE id = %s",
            (handle.ai_job_id,),
        )
        cur.execute(
            "UPDATE search_requests SET status = 'done', finished_at = now() WHERE id = %s",
            (handle.search_request_id,),
        )
        cur.close()


def fail_job(handle: JobHandle, error: str) -> None:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO ai_results (id, job_id, version, summary, raw_response, created_at)
            VALUES (gen_random_uuid(), %s, 0, %s, %s, now())
            """,
            (handle.ai_job_id, f"failed: {error}", json.dumps({"error": error})),
        )
        cur.execute("UPDATE ai_jobs SET status = 'failed', finished_at = now() WHERE id = %s", (handle.ai_job_id,))
        cur.execute("UPDATE search_requests SET status = 'failed', finished_at = now() WHERE id = %s", (handle.search_request_id,))
        cur.close()


def get_job_status(ai_job_id: str) -> dict | None:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT status, started_at, finished_at FROM ai_jobs WHERE id = %s", (ai_job_id,))
        row = cur.fetchone()
        if row is None:
            cur.close()
            return None
        status, started_at, finished_at = row

        cur.execute(
            "SELECT version, summary, raw_response FROM ai_results WHERE job_id = %s ORDER BY version",
            (ai_job_id,),
        )
        results = [{"version": v, "summary": s, "option": r} for v, s, r in cur.fetchall()]
        cur.close()

        return {
            "status": status,
            "started_at": started_at.isoformat() if started_at else None,
            "finished_at": finished_at.isoformat() if finished_at else None,
            "results": results,
        }
