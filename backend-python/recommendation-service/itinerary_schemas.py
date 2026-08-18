"""Data models for the itinerary-planning stage.

Two directions:
  - Input models describe what flight_stage/hotel_stage hand off to this
    stage, plus the user's own preferences/constraints.
  - Output models describe the exact JSON shape Claude must return. They
    double as the tool's input_schema (via .model_json_schema()) AND as
    the validator for whatever Claude actually sends back - if Claude's
    output doesn't fit these models, Pydantic raises instead of silently
    passing malformed data downstream.
"""
from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator


# Input: what this stage receives from earlier stages + the user

class GroupInput(BaseModel):
    group_id: int
    adults: int
    children: int
    budget_max: Optional[float] = None  # total budget for this group: flights + hotel + activities + food + local transport
    wheelchair_accessible: bool = False
    preferences: str = ""  # this group's own food/interest preferences - meals/activities are shared, so
                            # these get weighed together with every other group's when picking a shared option


class TripPlanningRequest(BaseModel):
    groups: list[GroupInput]
    user_preferences: str  # free text: food preferences, interests, must-see places, etc.
    travel_pace: str # e.g. "relaxed", "moderate", "packed"
    flight_offers: list[dict] # raw offers from flight_stage, one list per group already filtered by budget
    hotel_offers: list[dict] # raw offers from hotel_stage, already filtered by budget

# Output: the exact structure Claude must fill in

class ScheduleItemType(str, Enum):
    TRANSPORT = "transport"
    MEAL = "meal"
    ACTIVITY = "activity"
    CHECK_IN = "check_in"
    CHECK_OUT = "check_out"
    FLIGHT = "flight"


class ScheduleItem(BaseModel):
    time: str = Field(description="START time of this item (local, e.g. '14:30') - not a range. The item runs from "
                                   "`time` for `duration_minutes`; the next item for this group must start at "
                                   "time + duration_minutes. If nothing is scheduled in between (genuine free time, "
                                   "rest at the hotel), that time must still be accounted for - either fold it into "
                                   "this item's duration_minutes or say so explicitly in notes ('includes 2h free "
                                   "time before dinner'). Do not leave an unexplained numeric gap.")
    type: ScheduleItemType
    title: str = Field(description="Short name, e.g. 'Taxi to hotel', 'Lunch at Curry 36', 'Pergamon Museum'")
    description: str = Field(description="What this is, why it fits the user's preferences, what to expect")
    location: str = Field(description="Address or place name")
    latitude: Optional[float] = Field(default=None, description="Required for meal/activity items - use the exact coordinates returned by search_nearby_places, not a guess")
    longitude: Optional[float] = Field(default=None, description="Required for meal/activity items - use the exact coordinates returned by search_nearby_places, not a guess")
    duration_minutes: int = Field(
        description="REQUIRED for every item, and it means something different per type: "
                     "for meal/activity - the actual allotted/free time (e.g. 90 for a sit-down lunch, "
                     "120 for a museum visit) - a real planning decision, not padding; "
                     "for transport - MUST exactly equal the duration_minutes get_directions returned for the "
                     "transport_mode you used, no rounding 'to make the schedule look nice'; "
                     "for check_in/check_out - a short realistic process time (e.g. 15); "
                     "for flight - the flight's actual scheduled duration."
    )
    transport_mode: Optional[Literal["walking", "transit", "driving", "cycling"]] = Field(
        default=None,
        description="REQUIRED when type=transport: the travel mode this item's duration/distance actually came "
                     "from - must match the `mode` argument used in the get_directions call for this leg. "
                     "Must be null for every other item type.",
    )
    cost_eur: float = Field(description="0 if free/walking")
    notes: str = Field(default="", description="Accessibility notes, booking tips, pace-related notes")
    url: Optional[str] = Field(
        default=None,
        description="For meal/activity items: copy the maps_url field from the matching search_nearby_places "
                     "result, unchanged. Null for other item types.",
    )
    applies_to_group_ids: list[int] = Field(
        default_factory=list,
        description="Which groups this item is for. Empty list means ALL groups do this together.",
    )

    @model_validator(mode="after")
    def _transport_mode_matches_type(self) -> "ScheduleItem":
        if self.type == ScheduleItemType.TRANSPORT and self.transport_mode is None:
            raise ValueError("transport_mode is required when type='transport'")
        if self.type != ScheduleItemType.TRANSPORT and self.transport_mode is not None:
            raise ValueError(f"transport_mode must be null for type='{self.type.value}'")
        return self


class DayPlan(BaseModel):
    day_number: int
    date: str  # YYYY-MM-DD
    items: list[ScheduleItem] = Field(description="Chronologically ordered: transport, meals, activities, check-in/out")


class GroupPriceBreakdown(BaseModel):
    """NOTE: after Claude returns this, the backend recalculates every
    field from the actual costed schedule items (meals_cost/activities_cost/
    local_transport_cost = sum of cost_eur across that group's meal/
    activity/transport items) plus the chosen flight/hotel offers - see
    recommendation_stage._compute_price_breakdowns. Claude's own numbers
    here are a first draft, not the final source of truth; what matters is
    that every priced item's cost_eur is set correctly and attributed to
    the right group(s), since that is what actually gets summed.
    """
    group_id: int
    flights_cost: float
    hotel_cost: float
    activities_cost: float = Field(description="Sum of cost_eur across this group's 'activity' schedule items")
    meals_cost: float = Field(description="Sum of cost_eur across this group's 'meal' schedule items")
    local_transport_cost: float = Field(description="Sum of cost_eur across this group's 'transport' schedule items "
                                                      "(fare products, taxis - put the cost on the schedule item "
                                                      "itself, e.g. the item where a day ticket is purchased)")
    total_cost: float = Field(description="flights_cost + hotel_cost + activities_cost + meals_cost + local_transport_cost")
    budget_max: Optional[float]
    within_budget: bool = Field(description="true only if budget_max is null or total_cost <= budget_max")


class FlightSelection(BaseModel):
    group_id: int
    airline_summary: str = Field(description="Airline(s), dates, price - which flight offer from the input this group uses")
    price_eur: float
    booking_url: str = Field(default="", description="Copy the booking_url field from the matching flight_offers entry, unchanged")
    baggage_info: Optional[str] = Field(
        default=None,
        description="Leave this null - the backend fills it in after generation with a live baggage-price lookup",
    )


class HotelSelection(BaseModel):
    group_id: int
    hotel_name: str
    address: str = Field(description="Best-effort address from context - the backend overwrites this after "
                                       "generation with a real address from a property-details lookup")
    latitude: float
    longitude: float
    price_eur: float = Field(description="Total price for this group's stay")
    booking_url: str = Field(default="", description="Copy the booking_url field from the matching hotel_offers entry, unchanged")


class ItineraryOption(BaseModel):
    option_id: int
    summary: str = Field(description="One or two sentences describing this option's character, e.g. 'budget-focused, hostel-based, heavy on free walking tours'")
    flight_selections: list[FlightSelection] = Field(description="One entry per group - each group may fly on a different offer")
    hotel_selections: list[HotelSelection] = Field(description="One entry per group - hotels MUST be close to each other, see system rules")
    days: list[DayPlan]
    price_breakdown: list[GroupPriceBreakdown]
    final_recommendation: str = Field(description="Closing advice for the traveler(s): what to book first, what's flexible, what to watch out for")


class ItineraryProposal(BaseModel):
    options: list[ItineraryOption]
