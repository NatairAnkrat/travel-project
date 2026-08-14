"""Request/response models for edit-service.

An edit takes an existing travel, applies a partial change to its planning
parameters (and/or a free-text instruction), creates a NEW travel_version, and
regenerates the itinerary with the previous plan as context - so the model
revises rather than replans. See main.py for the flow.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class GroupChange(BaseModel):
    """One traveller sub-group. Mirrors recommendation-service's GroupInput.
    Groups supplied on an edit are merged by `group_id`: each one replaces the
    prior group with the same id, groups you don't mention are kept unchanged,
    and a new group_id is added. So you only send the group(s) you're changing.
    """
    group_id: int
    adults: int
    children: int = 0
    budget_max: Optional[float] = None
    wheelchair_accessible: bool = False
    preferences: str = ""


class EditChanges(BaseModel):
    """Only the fields the user wants to change. Anything left None is carried
    forward from the current version. At least one field (or `instruction`)
    should be set, otherwise the edit is a no-op re-run.
    """
    groups: Optional[list[GroupChange]] = None
    user_preferences: Optional[str] = None
    travel_pace: Optional[str] = None
    start_date: Optional[str] = Field(default=None, description="YYYY-MM-DD; changing dates triggers a flight/hotel re-search")
    end_date: Optional[str] = Field(default=None, description="YYYY-MM-DD")
    instruction: Optional[str] = Field(
        default=None,
        description="Free-text change, e.g. 'swap the Italian place on day 2 for Thai, make day 3 cheaper'",
    )


class EditRequest(BaseModel):
    requested_by: str = Field(description="User UUID performing the edit (FK to users)")
    changes: EditChanges


class EditCreatedResponse(BaseModel):
    job_id: str = Field(description="recommendation-service job id - poll GET /api/v1/edits/{job_id}")
    travel_version_id: str = Field(description="The new travel_version created for this edit")
    version_number: int
