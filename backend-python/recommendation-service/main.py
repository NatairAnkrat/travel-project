"""recommendation-service: wraps recommendation_stage.run() (which itself
runs claude_itinerary_client's tool-use loop, up to MAX_TOOL_ITERATIONS
per tier x 3 tiers) behind an async job API.

This is NOT a synchronous endpoint on purpose - a full run can take
several minutes, well past any sane ingress/gateway timeout. The pattern:
  POST /api/v1/recommendations   -> 202 + job_id, work starts in the background
  GET  /api/v1/recommendations/{job_id} -> poll for status/result

FastAPI's BackgroundTasks is enough for a single-replica deployment. If
this service is ever scaled to >1 replica, move job execution to a real
queue (the infra doc mentions this as a possible next step) so a job
started on pod A isn't silently lost if the poll request lands on pod B.
"""
from __future__ import annotations

import logging
import os

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import db
import jobs
import places_repository

# Loads variables from a local .env file if one exists (for running the
# service on your laptop) - a no-op in production, where OpenShift injects
# real environment variables directly and no .env file is present.
load_dotenv()
from clients.claude_itinerary_client import ClaudeItineraryClient, ItineraryGenerationError
from clients.search_service_client import SearchServiceClient
from itinerary_schemas import GroupInput, TripPlanningRequest
import recommendation_stage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="recommendation-service")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")


@app.get("/health")
def health():
    if not ANTHROPIC_API_KEY:
        return JSONResponse(status_code=503, content={"status": "error", "detail": "ANTHROPIC_API_KEY is not set"})
    try:
        db.check_connection()
    except Exception as exc:
        return JSONResponse(status_code=503, content={"status": "error", "database": str(exc)})
    return {"status": "ok", "database": "connected"}


class RecommendationRequest(TripPlanningRequest):
    travel_version_id: str
    requested_by: str
    # Present only when this generation is an EDIT of a prior version (see
    # edit-service). previous_itinerary is the prior proposal dict
    # ({"options": [...]}); edit_instruction is the free-text change request.
    previous_itinerary: dict | None = None
    edit_instruction: str | None = None


class RecommendationCreatedResponse(BaseModel):
    job_id: str


@app.post("/api/v1/recommendations", status_code=202, response_model=RecommendationCreatedResponse)
def create_recommendation(request: RecommendationRequest, background_tasks: BackgroundTasks):
    trip_request = TripPlanningRequest(
        groups=request.groups,
        user_preferences=request.user_preferences,
        travel_pace=request.travel_pace,
        flight_offers=request.flight_offers,
        hotel_offers=request.hotel_offers,
    )

    handle = jobs.create_job(request.travel_version_id, request.requested_by, trip_request)
    background_tasks.add_task(_run_job, handle, request.groups, request.user_preferences,
                               request.travel_pace, request.flight_offers, request.hotel_offers,
                               request.previous_itinerary, request.edit_instruction)

    return RecommendationCreatedResponse(job_id=handle.ai_job_id)


@app.get("/api/v1/recommendations/{job_id}")
def get_recommendation(job_id: str):
    status = jobs.get_job_status(job_id)
    if status is None:
        raise HTTPException(status_code=404, detail="job not found")
    return status


def _run_job(
    handle: jobs.JobHandle,
    groups: list[GroupInput],
    user_preferences: str,
    travel_pace: str,
    flight_offers: list[dict],
    hotel_offers: list[dict],
    previous_itinerary: dict | None = None,
    edit_instruction: str | None = None,
) -> None:
    """Runs on FastAPI's background thread pool, after the 202 response
    has already been sent - errors here can't propagate to an HTTP
    response, so they're caught and written into ai_results/ai_jobs
    instead of raising.
    """
    try:
        client = ClaudeItineraryClient(api_key=ANTHROPIC_API_KEY)
        result = recommendation_stage.run(
            groups=groups, user_preferences=user_preferences, travel_pace=travel_pace,
            flight_offers=flight_offers, hotel_offers=hotel_offers, client=client,
            search_client=SearchServiceClient(),
            previous_itinerary=previous_itinerary, edit_instruction=edit_instruction,
        )
        jobs.complete_job(handle, result.proposal)

        # Best-effort: persist the real places found during generation and
        # their photos. A failure here must not flip an already-successful
        # job to failed, so it's caught and logged separately from the
        # generation itself.
        try:
            places_repository.save_found_places(handle.travel_version_id, result.found_places_by_option)
        except Exception:
            logger.exception("Failed to persist places/photos for job %s", handle.ai_job_id)
    except ItineraryGenerationError as exc:
        logger.error("Itinerary generation failed for job %s: %s", handle.ai_job_id, exc)
        jobs.fail_job(handle, str(exc))
    except Exception as exc:  # last-resort guard so a bug never leaves a job stuck "processing" forever
        logger.exception("Unexpected error in job %s", handle.ai_job_id)
        jobs.fail_job(handle, f"unexpected error: {exc}")
