"""Request/response models for the search-service API.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class FlightGroupInput(BaseModel):
    group_id: int
    adults: int
    children: int = 0
    children_ages: list[int] = Field(
        default_factory=list,
        description=(
            "Age of each child (0-17), one entry per child. Google Flights has no "
            "direct age input - each age is routed into the bucket it actually "
            "searches as: under 2 = infant on lap, 2-11 = child, 12+ = adult."
        ),
    )
    budget_max: Optional[float] = Field(
        default=None, description="Total round-trip budget for this group, EUR. Null = no limit."
    )


class FlightSearchRequest(BaseModel):
    origin_city: str = Field(description="Free-text origin city, e.g. 'Paris'")
    destination_city: str = Field(description="Free-text destination city, e.g. 'Berlin'")
    base_departure_date: str = Field(description="YYYY-MM-DD")
    trip_length_nights: int
    date_range_days: int = Field(default=2, description="Search base date +- this many days")
    top_n_outbound: int = Field(default=1, description="How many cheapest outbound legs get a return-leg lookup")
    groups: list[FlightGroupInput]


class FlightOffer(BaseModel):
    group_id: int
    group_composition: str #label of the group
    group_size: int
    outbound_date: str
    return_date: str
    airline_outbound: str = "" # name of the airline one-way
    airline_return: str = "" # name of the airline backwards
    price: Optional[float] = None
    currency: str = ""
    outbound_departure_time: str = ""
    outbound_arrival_time: str = ""
    return_departure_time: str = ""
    return_arrival_time: str = ""
    origin_airport: str = ""
    destination_airport: str = ""
    origin_latitude: Optional[float] = None
    origin_longitude: Optional[float] = None
    destination_latitude: Optional[float] = None
    destination_longitude: Optional[float] = None
    outbound_stops: Optional[int] = None
    return_stops: Optional[int] = None
    booking_url: str = Field(default="", description="Link to search/view this route on Google Flights")
    booking_token: str = Field(default="", description="Opaque SerpApi token for this exact itinerary - "
                                                         "required to look up baggage pricing via /search/flights/baggage-price")
    status: str
    note: str = ""


class FlightSearchResponse(BaseModel):
    resolved_origin: str
    resolved_destination: str
    offers: list[FlightOffer]


class BaggagePriceRequest(BaseModel):
    origin: str
    destination: str
    departure_date: str
    booking_token: str = Field(description="From the matching FlightOffer.booking_token")
    return_date: Optional[str] = Field(default=None, description="Omit for one-way offers")


class BaggagePriceResponse(BaseModel):
    baggage_info: str


class HotelGroupInput(BaseModel):
    group_id: int
    adults: int
    children: int = 0
    children_ages: list[int] = Field(default_factory=list)
    budget_max: Optional[float] = Field(default=None, description="Total stay budget for this group, EUR")
    wheelchair_accessible: bool = False


class HotelSearchRequest(BaseModel):
    location: str = Field(default="Berlin, Germany")
    stay_date_ranges: list[list[str]] = Field(
        description=(
            "[check_in, check_out] date pairs to search hotels for. The flight search already "
            "explored base_departure_date +- date_range_days and returned an offer (status=ok) "
            "only for the pairs where flights actually exist - the caller runs /search/flights "
            "first and passes in the outbound_date/return_date of whichever FlightOffers it wants "
            "hotel prices for, so we never search hotels for a date pair with no flight"
        )
    )
    groups: list[HotelGroupInput]


class HotelOffer(BaseModel):
    group_id: int
    group_composition: str
    group_size: int
    wheelchair_accessible: bool
    check_in_date: str
    check_out_date: str
    location: str = Field(default="", description="Free-text location this offer was searched under - "
                                                    "required to look up property details via /search/hotels/property-details")
    property_name: str = ""
    property_type: str = ""
    property_token: str = Field(default="", description="Google's own property id - stable key for later detail lookups")
    total_price: Optional[float] = None
    currency: str = ""
    rate_per_night: Optional[float] = None
    overall_rating: Optional[float] = None
    hotel_class: Optional[int] = Field(default=None, description="Official star rating, 1-5. Null for properties Google doesn't classify (e.g. many vacation rentals)")
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    address: str = ""
    amenities_summary: str = ""
    booking_url: str = Field(default="", description="Link to view/book this property")
    status: str
    note: str = ""


class HotelSearchResponse(BaseModel):
    offers: list[HotelOffer]


class PropertyDetailsRequest(BaseModel):
    property_token: str = Field(description="From the matching HotelOffer.property_token")
    location: str
    check_in_date: str
    check_out_date: str
    adults: int = 1
    children: int = 0


class WebSearchRequest(BaseModel):
    query: str
    max_results: int = Field(default=5, description="How many organic results to return")


class WebSearchResult(BaseModel):
    title: str
    snippet: str
    link: str


class WebSearchResponse(BaseModel):
    results: list[WebSearchResult]


class PropertyDetailsResponse(BaseModel):
    address: str
