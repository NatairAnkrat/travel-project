import { travelApi } from '../lib/apiClient'
import type { FlightSearchRequest, FlightSearchResponse, HotelSearchRequest, HotelSearchResponse } from './types'

// All proxied verbatim by travel-service to search-service — see
// docs/openapi/travel-service.yaml.

export function searchFlights(req: FlightSearchRequest): Promise<FlightSearchResponse> {
  return travelApi('/api/v1/search/flights', { method: 'POST', body: req })
}

export function searchHotels(req: HotelSearchRequest): Promise<HotelSearchResponse> {
  return travelApi('/api/v1/search/hotels', { method: 'POST', body: req })
}
