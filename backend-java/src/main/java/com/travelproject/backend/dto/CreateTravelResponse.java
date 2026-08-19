package com.travelproject.backend.dto;

import java.util.UUID;

public record CreateTravelResponse(UUID travelId, UUID travelVersionId, String jobId) {}