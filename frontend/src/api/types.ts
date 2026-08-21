// Mirrors docs/openapi/*.yaml. Keep these in sync with the specs, not the
// other way around — the specs describe what's actually deployed.

// ---- auth-service ----

export interface RegisterRequest {
  login: string
  password: string
  email: string
  phone?: string | null
  first_name: string
  last_name: string
  /** FK to languages — no lookup endpoint exists yet, see README "Known gaps". */
  language_id: string
  /** FK to currencies — no lookup endpoint exists yet, see README "Known gaps". */
  currency_id: string
  timezone: string
}

export interface LoginRequest {
  login: string
  password: string
  device?: string
}

export interface AuthResponse {
  userId: string
  accessToken: string
  refreshToken: string
  expiresInSeconds: number
}

// ---- group-service ----

export interface CreateGroupRequest {
  name: string
  description?: string | null
  created_by: string
}

export interface InviteRequest {
  email: string
  created_by: string
}

export interface GroupMemberView {
  userId: string
  login: string
  roleCode: string
  status: string
}

// ---- travel-service ----

export interface GroupInput {
  group_id: number
  adults: number
  children: number
  budget_max?: number | null
  wheelchair_accessible: boolean
  preferences: string
}

export interface CreateTravelRequest {
  group_id: string
  created_by: string
  title: string
  description?: string | null
  destination_city_id: string
  start_date: string
  end_date: string
  groups: GroupInput[]
  user_preferences: string
  travel_pace: string
  flight_offers: unknown[]
  hotel_offers: unknown[]
}

export interface CreateTravelResponse {
  travelId: string
  travelVersionId: string
  jobId: string
}

export type ScheduleItemType = 'transport' | 'meal' | 'activity' | 'check_in' | 'check_out' | 'flight'
export type TransportMode = 'walking' | 'transit' | 'driving' | 'cycling'

export interface ScheduleItem {
  time: string
  type: ScheduleItemType
  title: string
  description: string
  location: string
  latitude: number | null
  longitude: number | null
  duration_minutes: number
  transport_mode: TransportMode | null
  cost_eur: number
  notes: string
  url: string | null
  applies_to_group_ids: number[]
}

export interface ItineraryOption {
  option_id: number
  summary: string
  flight_selections: Array<{
    group_id: number
    airline_summary: string
    price_eur: number
    booking_url: string
    baggage_info: string | null
  }>
  hotel_selections: Array<{
    group_id: number
    hotel_name: string
    address: string
    latitude: number
    longitude: number
    price_eur: number
    booking_url: string
  }>
  days: Array<{ day_number: number; date: string; items: ScheduleItem[] }>
  price_breakdown: Array<{
    group_id: number
    flights_cost: number
    hotel_cost: number
    activities_cost: number
    meals_cost: number
    local_transport_cost: number
    total_cost: number
    budget_max: number | null
    within_budget: boolean
  }>
  final_recommendation: string
}

export interface GenerationStatus {
  status: 'processing' | 'done' | 'failed'
  started_at: string | null
  finished_at: string | null
  results: Array<{ version: number; summary: string | null; option: ItineraryOption }>
}

export interface EditRequest {
  requested_by: string
  changes: {
    groups?: GroupInput[]
    user_preferences?: string
    travel_pace?: string
    start_date?: string
    end_date?: string
    instruction?: string
  }
}

export interface EditCreatedResponse {
  job_id: string
  travel_version_id: string
  version_number: number
}

// ---- search-service (proxied via travel-service) ----

export interface FlightSearchRequest {
  origin_city: string
  destination_city: string
  base_departure_date: string
  trip_length_nights: number
  date_range_days?: number
  top_n_outbound?: number
  groups: Array<GroupInput & { children_ages: number[] }>
}

export interface FlightOffer {
  group_id: number
  group_composition: string
  group_size: number
  outbound_date: string
  return_date: string
  price: number | null
  currency: string
  booking_url: string
  booking_token: string
  status: string
  note: string
  [key: string]: unknown
}

export interface FlightSearchResponse {
  resolved_origin: string
  resolved_destination: string
  offers: FlightOffer[]
}

export interface HotelSearchRequest {
  location?: string
  stay_date_ranges: Array<[string, string]>
  groups: Array<GroupInput & { children_ages: number[] }>
}

export interface HotelOffer {
  group_id: number
  property_name: string
  property_token: string
  total_price: number | null
  currency: string
  location: string
  status: string
  note: string
  [key: string]: unknown
}

export interface HotelSearchResponse {
  offers: HotelOffer[]
}
