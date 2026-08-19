package com.travelproject.auth.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.UUID;

public record RegisterRequest(
        String login,
        String password,
        String email,
        String phone,
        @JsonProperty("first_name") String firstName,
        @JsonProperty("last_name") String lastName,
        @JsonProperty("language_id") UUID languageId,   // FK на languages — фронт передаёт готовый UUID справочника
        @JsonProperty("currency_id") UUID currencyId,    // FK на currencies
        String timezone
) {}