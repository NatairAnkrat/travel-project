package com.travelproject.travel.controller;

import com.travelproject.travel.client.RecommendationServiceClient;
import com.travelproject.travel.dto.CreateTravelRequest;
import com.travelproject.travel.dto.CreateTravelResponse;
import com.travelproject.travel.repository.AuditLogRepository;
import com.travelproject.travel.repository.TravelRepository;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import java.util.*;

@RestController
@RequestMapping("/api/v1/travels")
public class TravelController {

    private final TravelRepository travelRepository;
    private final RecommendationServiceClient recommendationClient;
    private final AuditLogRepository auditLogRepository;

    public TravelController(TravelRepository travelRepository, RecommendationServiceClient recommendationClient,
                             AuditLogRepository auditLogRepository) {
        this.travelRepository = travelRepository;
        this.recommendationClient = recommendationClient;
        this.auditLogRepository = auditLogRepository;
    }

    @PostMapping
    public ResponseEntity<?> createTravel(@RequestBody CreateTravelRequest req, HttpServletRequest http) {
        if (!travelRepository.isGroupMember(req.groupId(), req.createdBy())) {
            return ResponseEntity.status(HttpStatus.FORBIDDEN).body(Map.of("error", "not a member of this group"));
        }

        UUID[] ids = travelRepository.createTravelWithFirstVersion(req);
        UUID travelId = ids[0];
        UUID versionId = ids[1];

        auditLogRepository.log(req.createdBy(), "travels", travelId, "CREATE",
                "{\"title\":\"" + req.title() + "\"}", http.getRemoteAddr());

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