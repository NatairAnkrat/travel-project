package com.travelproject.backend.controller;

import com.travelproject.backend.client.RecommendationServiceClient;
import com.travelproject.backend.dto.CreateTravelRequest;
import com.travelproject.backend.dto.CreateTravelResponse;
import com.travelproject.backend.repository.TravelRepository;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import java.util.*;

@RestController
@RequestMapping("/api/v1/travels")
public class TravelController {

    private final TravelRepository travelRepository;
    private final RecommendationServiceClient recommendationClient;

    public TravelController(TravelRepository travelRepository, RecommendationServiceClient recommendationClient) {
        this.travelRepository = travelRepository;
        this.recommendationClient = recommendationClient;
    }

    @PostMapping
    public ResponseEntity<CreateTravelResponse> createTravel(@RequestBody CreateTravelRequest req) {
        UUID[] ids = travelRepository.createTravelWithFirstVersion(req);
        UUID travelId = ids[0];
        UUID versionId = ids[1];

        Map<String, Object> payload = new HashMap<>();
        payload.put("travel_version_id", versionId.toString());
        payload.put("requested_by", req.createdBy().toString());
        payload.put("groups", req.groups());
        payload.put("user_preferences", req.userPreferences());
        payload.put("travel_pace", req.travelPace());
        payload.put("flight_offers", req.flightOffers());
        payload.put("hotel_offers", req.hotelOffers());

        String jobId = recommendationClient.startGeneration(payload);

        return ResponseEntity.status(HttpStatus.CREATED)
                .body(new CreateTravelResponse(travelId, versionId, jobId));
    }

    @GetMapping("/generation/{jobId}")
    public ResponseEntity<Map<String, Object>> getGenerationStatus(@PathVariable String jobId) {
        return ResponseEntity.ok(recommendationClient.getStatus(jobId));
    }
}