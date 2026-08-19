package com.travelproject.group.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.UUID;

public record AcceptInviteRequest(@JsonProperty("user_id") UUID userId) {}