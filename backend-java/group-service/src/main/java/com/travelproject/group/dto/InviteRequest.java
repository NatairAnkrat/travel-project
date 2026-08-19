package com.travelproject.group.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.UUID;

public record InviteRequest(String email, @JsonProperty("created_by") UUID createdBy) {}