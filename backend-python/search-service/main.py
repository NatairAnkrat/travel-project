import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from clients.google_flights_client import GoogleFlightsClient, SerpApiFlightsError

load_dotenv()
from clients.google_hotels_client import GoogleHotelsClient, SerpApiHotelsError
from clients.google_search_client import GoogleSearchClient, SerpApiSearchError
from domain import flight_search, hotel_search
from schemas import (
    BaggagePriceRequest, BaggagePriceResponse, FlightSearchRequest, FlightSearchResponse,
    HotelSearchRequest, HotelSearchResponse, PropertyDetailsRequest, PropertyDetailsResponse,
    WebSearchRequest, WebSearchResponse,
)

logging.basicConfig(level=logging.INFO)
app = FastAPI(title="search-service")

SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY", "")


@app.get("/health")
def health():
    if not SERPAPI_API_KEY:
        return JSONResponse(status_code=503, content={"status": "error", "detail": "SERPAPI_API_KEY is not set"})
    return {"status": "ok"}


@app.post("/api/v1/search/flights", response_model=FlightSearchResponse)
def search_flights(request: FlightSearchRequest):
    client = GoogleFlightsClient(api_key=SERPAPI_API_KEY)
    try:
        resolved_origin, resolved_destination, offers = flight_search.search(client, request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except SerpApiFlightsError as exc:
        raise HTTPException(status_code=502, detail=f"SerpApi error: {exc}") from exc

    return FlightSearchResponse(resolved_origin=resolved_origin, resolved_destination=resolved_destination, offers=offers)


@app.post("/api/v1/search/flights/baggage-price", response_model=BaggagePriceResponse)
def get_baggage_price(request: BaggagePriceRequest):
    client = GoogleFlightsClient(api_key=SERPAPI_API_KEY)
    baggage_info = client.fetch_baggage_price(
        origin=request.origin, destination=request.destination,
        departure_date=request.departure_date, booking_token=request.booking_token,
        return_date=request.return_date,
    )
    return BaggagePriceResponse(baggage_info=baggage_info)


@app.post("/api/v1/search/hotels", response_model=HotelSearchResponse)
def search_hotels(request: HotelSearchRequest):
    client = GoogleHotelsClient(api_key=SERPAPI_API_KEY)
    try:
        offers = hotel_search.search(client, request)
    except SerpApiHotelsError as exc:
        raise HTTPException(status_code=502, detail=f"SerpApi error: {exc}") from exc

    return HotelSearchResponse(offers=offers)


@app.post("/api/v1/search/hotels/property-details", response_model=PropertyDetailsResponse)
def get_hotel_property_details(request: PropertyDetailsRequest):
    client = GoogleHotelsClient(api_key=SERPAPI_API_KEY)
    details = client.get_property_details(
        request.property_token, request.location, request.check_in_date, request.check_out_date,
        adults=request.adults, children=request.children,
    )
    return PropertyDetailsResponse(address=details.get("address", ""))


@app.post("/api/v1/search/web", response_model=WebSearchResponse)
def search_web(request: WebSearchRequest):
    client = GoogleSearchClient(api_key=SERPAPI_API_KEY)
    try:
        results = client.search(request.query, max_results=request.max_results)
    except SerpApiSearchError as exc:
        raise HTTPException(status_code=502, detail=f"SerpApi error: {exc}") from exc

    return WebSearchResponse(results=results)
