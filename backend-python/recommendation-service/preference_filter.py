"""Cheap pre-filter for free-text user preferences, run once before the
expensive multi-tier itinerary generation (recommendation_stage.run()
calls this first, before building the TripPlanningRequest that goes to
the main tool-loop model).

Why this exists: a request like "vegetarian food, love museums, and I
want the hostel bathroom to smell like lavender with pink toilet paper"
mixes preferences a real search tool can actually check (cuisine, place
category) with ones no data source exposes at all (bathroom decor/scent).
Left unfiltered, the expensive main model would burn several of its
tool-use rounds trying to somehow satisfy the unsatisfiable part before
giving up. This filter separates the two BEFORE that loop starts, using a
small, fast model with a single forced-tool call - no research tools, one
round trip, a fraction of the cost of even one extra round inside the
main generation.

This is deliberately a SEPARATE call rather than an instruction folded
into the main system prompt: baking it into the main prompt doesn't save
anything, because the model still has to work it out live, inside the
same expensive loop, one way or another.
"""
from __future__ import annotations

import os

import anthropic
from pydantic import BaseModel, Field

FILTER_MODEL = "claude-haiku-4-5-20251001"

FILTER_SYSTEM_PROMPT = """You separate a traveler's free-text preferences into
two buckets:

1. ACTIONABLE - anything a real search tool could actually check against
   real data: cuisine type, dietary restriction, price level, wheelchair/
   step-free access, travel pace, interest categories (museums,
   nightlife, nature, shopping), a specific named place they want
   included, opening-hours constraints. Rewrite each as a short, clear
   phrase a search query could be built from.

2. NOT GROUNDABLE - anything no available data source (Google Places,
   Google Hotels) exposes as a real, checkable attribute: hyper-specific
   sensory or aesthetic details (bathroom decor, exact scent, wall
   color), requests with no real yes/no answer in listing data, or text
   that isn't actually about trip planning at all.

Be generous with ACTIONABLE - most ordinary preferences belong there.
Only route something to NOT GROUNDABLE if no real tool call could ever
confirm it either way. For each dropped item, give a one-sentence reason,
written for the traveler to read (not technical jargon).
"""


class DroppedPreference(BaseModel):
    text: str
    reason: str


class FilteredPreferences(BaseModel):
    actionable: list[str] = Field(
        description="Cleaned, checkable preferences - what actually gets used for trip planning"
    )
    dropped: list[DroppedPreference] = Field(
        default_factory=list,
        description="Preferences no real search tool could verify, each with a plain-language reason",
    )


SUBMIT_TOOL = {
    "name": "submit_filtered_preferences",
    "description": "Submit the preferences split into actionable and not-groundable buckets",
    "input_schema": FilteredPreferences.model_json_schema(),
}


def filter_preferences(raw_text: str, api_key: str | None = None) -> FilteredPreferences:
    """Single, cheap round trip - no tools, no research, forced structured
    output. Falls back to passing the raw text through unfiltered on any
    error, since a filtering hiccup should never be the reason a trip
    fails to generate.
    """
    if not raw_text or not raw_text.strip():
        return FilteredPreferences(actionable=[], dropped=[])

    try:
        client = anthropic.Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))
        response = client.messages.create(
            model=FILTER_MODEL,
            max_tokens=1024,
            system=FILTER_SYSTEM_PROMPT,
            tools=[SUBMIT_TOOL],
            tool_choice={"type": "tool", "name": "submit_filtered_preferences"},
            messages=[{"role": "user", "content": raw_text}],
        )
    except Exception:
        return FilteredPreferences(actionable=[raw_text], dropped=[])

    for block in response.content:
        if block.type == "tool_use" and block.name == "submit_filtered_preferences":
            try:
                return FilteredPreferences.model_validate(block.input)
            except Exception:
                break

    # Forced tool_choice should always return the tool call above - this
    # is a last-resort guard, not the expected path.
    return FilteredPreferences(actionable=[raw_text], dropped=[])


def apply_filter_for_prompt(filtered: FilteredPreferences, original_text: str) -> str:
    """Turns the filtered result into the plain string that gets passed
    along as user_preferences to the main generation. Falls back to the
    original text if filtering produced nothing usable - better to pass
    the person's own words through than silently drop everything they wrote.
    """
    if filtered.actionable:
        return "; ".join(filtered.actionable)
    return original_text
