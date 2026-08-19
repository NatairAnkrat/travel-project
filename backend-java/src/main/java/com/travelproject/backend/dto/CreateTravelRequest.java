package com.travelproject.backend.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;
import java.util.Map;
import java.util.UUID;

public record CreateTravelRequest(
        @JsonProperty("group_id") UUID groupId,
        @JsonProperty("created_by") UUID createdBy,
        String title,
        String description,
        @JsonProperty("destination_city_id") UUID destinationCityId,
        @JsonProperty("start_date") String startDate,           // YYYY-MM-DD
        @JsonProperty("end_date") String endDate,
        List<GroupInput> groups,
        @JsonProperty("user_preferences") String userPreferences,
        @JsonProperty("travel_pace") String travelPace,
        @JsonProperty("flight_offers") List<Map<String, Object>> flightOffers,
        @JsonProperty("hotel_offers") List<Map<String, Object>> hotelOffers
) {}