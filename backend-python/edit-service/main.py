"""edit-service: revise an existing travel by creating a new travel_version and
regenerating with the previous plan as context.

Flow of POST /api/v1/travels/{travel_id}/edit:
  1. Load the current version's stored generation input (prior groups /
     preferences / pace / offers, from ai_jobs.prompt) and its previous
     proposal (ai_results).
  2. Apply the requested `changes` on top.
  3. Offers: reuse the prior ones, UNLESS the dates changed - then re-search
     flights + hotels via search-service for the new dates.
  4. Create the next travel_version (new current one).
  5. Hand off to recommendation-service with the new version + edit context
     (previous itinerary + free-text instruction). It runs its normal async
     job; we return that job id to poll.

Generation itself is NOT duplicated here - recommendation-service stays the one
Claude engine (with its caching / grounding / effort optimizations).
"""
from __future__ import annotations

import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

import db
import offers
from clients.recommendation_client import RecommendationClient, RecommendationServiceError
from clients.search_client import SearchClient
from schemas import EditCreatedResponse, EditRequest

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="edit-service")

DESTINATION_CITY = "Berlin"  # generation is Berlin-only for now (recommendation-service's prompt is Berlin-specific)


@app.get("/health")
def health():
    try:
        db.check_connection()
    except Exception as exc:
        return JSONResponse(status_code=503, content={"status": "error", "database": str(exc)})
    return {"status": "ok", "database": "connected"}


@app.post("/api/v1/travels/{travel_id}/edit", status_code=202, response_model=EditCreatedResponse)
def edit_travel(travel_id: str, request: EditRequest):
    changes = request.changes
    if not any(
        [changes.groups, changes.user_preferences, changes.travel_pace,
         changes.start_date, changes.end_date, changes.instruction]
    ):
        raise HTTPException(status_code=422, detail="changes is empty - nothing to edit")

    # read current version + prior input/result
    try:
        with db.get_connection() as conn:
            cur = conn.cursor()
            ctx = db.load_current_version_context(cur, travel_id)
            travel_start, travel_end = db.get_travel_dates(cur, travel_id)
            cur.close()
    except db.EditDataError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    prior = ctx["prior_request"]
    groups = (
        _merge_groups(prior.get("groups", []), [g.model_dump() for g in changes.groups])
        if changes.groups is not None
        else prior.get("groups", [])
    )
    user_preferences = changes.user_preferences if changes.user_preferences is not None else prior.get("user_preferences", "")
    travel_pace = changes.travel_pace or prior.get("travel_pace", "moderate")

    # offers: reuse, or re-search when dates change
    dates_changed = bool(changes.start_date or changes.end_date)
    if dates_changed:
        start_date = changes.start_date or travel_start
        end_date = changes.end_date or travel_end
        if not start_date or not end_date:
            raise HTTPException(status_code=422, detail="both start_date and end_date required to change dates")
        flight_offers, hotel_offers = _research_offers(travel_id, prior, groups, start_date, end_date)
    else:
        start_date = end_date = None
        flight_offers = prior.get("flight_offers", [])
        hotel_offers = prior.get("hotel_offers", [])

    # create the next version (and persist new dates)
    description = (changes.instruction or "parameters updated")[:250]
    with db.get_connection() as conn:
        cur = conn.cursor()
        new_version = db.create_next_version(cur, travel_id, request.requested_by, description)
        if dates_changed:
            db.update_travel_dates(cur, travel_id, start_date, end_date)
        cur.close()

    # hand off to recommendation-service (edit-aware generation)
    try:
        job_id = RecommendationClient().start_generation(
            travel_version_id=new_version["version_id"],
            requested_by=request.requested_by,
            groups=groups,
            user_preferences=user_preferences,
            travel_pace=travel_pace,
            flight_offers=flight_offers,
            hotel_offers=hotel_offers,
            previous_itinerary=ctx["previous_proposal"],
            edit_instruction=changes.instruction,
        )
    except RecommendationServiceError as exc:
        # The new version row exists but generation never started - surface it
        # plainly so the caller can retry rather than silently leaving a blank
        # version.
        logger.error("Edit for travel %s: generation failed to start: %s", travel_id, exc)
        raise HTTPException(status_code=502, detail=f"generation failed to start: {exc}") from exc

    return EditCreatedResponse(
        job_id=job_id,
        travel_version_id=new_version["version_id"],
        version_number=new_version["version_number"],
    )


@app.get("/api/v1/edits/{job_id}")
def get_edit(job_id: str):
    """Proxies recommendation-service's job status - same shape create's poll
    returns (status + per-tier results once done)."""
    try:
        status = RecommendationClient().get_status(job_id)
    except RecommendationServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if status is None:
        raise HTTPException(status_code=404, detail="job not found")
    return status


def _merge_groups(prior_groups: list[dict], changed_groups: list[dict]) -> list[dict]:
    """Patch groups by group_id: each supplied group replaces the prior one with
    the same group_id; groups not mentioned are kept as-is; a new group_id is
    appended. So editing one group no longer requires resending the others.
    """
    by_id = {g.get("group_id"): g for g in prior_groups}
    order = [g.get("group_id") for g in prior_groups]
    for g in changed_groups:
        gid = g.get("group_id")
        if gid not in by_id:
            order.append(gid)
        by_id[gid] = g
    return [by_id[gid] for gid in order]


def _research_offers(travel_id: str, prior: dict, groups: list[dict], start_date: str, end_date: str):
    """Re-search flights + hotels for changed dates. Origin city is resolved
    from the prior flight offers' departure airport (IATA -> city)."""
    prior_flights = prior.get("flight_offers", [])
    origin_iata = next((o.get("origin_airport") for o in prior_flights if o.get("origin_airport")), None)
    origin_city = None
    if origin_iata:
        with db.get_connection() as conn:
            cur = conn.cursor()
            origin_city = db.city_name_for_iata(cur, origin_iata)
            cur.close()
    if not origin_city:
        raise HTTPException(
            status_code=422,
            detail="cannot re-search flights for new dates: origin city could not be resolved from the "
                   "previous plan. Omit the date change, or ensure the previous flight offers carry a "
                   "known departure airport.",
        )
    try:
        return offers.research(SearchClient(), origin_city, DESTINATION_CITY, start_date, end_date, groups)
    except offers.OfferResearchError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
