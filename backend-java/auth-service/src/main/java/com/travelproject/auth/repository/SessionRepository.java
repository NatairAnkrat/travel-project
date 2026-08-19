package com.travelproject.auth.repository;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;
import java.time.OffsetDateTime;
import java.util.UUID;

@Repository
public class SessionRepository {

    private final JdbcTemplate jdbc;

    public SessionRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public UUID createSession(UUID userId, String accessToken, String device, String ipAddress, long ttlSeconds) {
        UUID sessionId = UUID.randomUUID();
        OffsetDateTime now = OffsetDateTime.now();
        jdbc.update(
                """
                INSERT INTO user_sessions (id, user_id, access_token, device, ip_address, expires_at, created_at)
                VALUES (?, ?, ?, ?, ?::inet, ?, ?)
                """,
                sessionId, userId, accessToken, device, ipAddress, now.plusSeconds(ttlSeconds), now
        );
        return sessionId;
    }

    public String createRefreshToken(UUID userId, UUID sessionId, long ttlDays) {
        String token = UUID.randomUUID().toString();
        OffsetDateTime now = OffsetDateTime.now();
        jdbc.update(
                """
                INSERT INTO refresh_tokens (id, user_id, session_id, token, expires_at, revoked, created_at)
                VALUES (?, ?, ?, ?, ?, false, ?)
                """,
                UUID.randomUUID(), userId, sessionId, token, now.plusSeconds(ttlDays * 86400), now
        );
        return token;
    }
}