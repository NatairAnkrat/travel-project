package com.travelproject.backend.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;

public record GroupInput(
        @JsonProperty("group_id") int groupId,
        int adults,
        int children,
        @JsonProperty("budget_max") Double budgetMax,
        @JsonProperty("wheelchair_accessible") boolean wheelchairAccessible,
        String preferences
) {}