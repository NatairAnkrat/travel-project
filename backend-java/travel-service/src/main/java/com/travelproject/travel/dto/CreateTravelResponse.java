package com.travelproject.travel.dto;

import java.util.UUID;

public record CreateTravelResponse(UUID travelId, UUID travelVersionId, String jobId) {}