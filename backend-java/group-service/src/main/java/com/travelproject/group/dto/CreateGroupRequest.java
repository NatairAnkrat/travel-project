package com.travelproject.group.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.UUID;

public record CreateGroupRequest(
        String name,
        String description,
        @JsonProperty("created_by") UUID createdBy
) {}