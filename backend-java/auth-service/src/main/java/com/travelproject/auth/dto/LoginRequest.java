package com.travelproject.auth.dto;

public record LoginRequest(String login, String password, String device) {}