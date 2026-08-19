package com.travelproject.group.dto;

import java.util.UUID;

public record GroupMemberView(UUID userId, String login, String roleCode, String status) {}