package com.travelproject.auth.repository;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;
import java.time.OffsetDateTime;
import java.util.UUID;
import java.util.Optional;

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

    public record RefreshTokenRecord(UUID id, UUID userId, UUID sessionId, OffsetDateTime expiresAt, boolean revoked) {}

    public Optional<RefreshTokenRecord> findRefreshToken(String token) {
        var rows = jdbc.query(
                "SELECT id, user_id, session_id, expires_at, revoked FROM refresh_tokens WHERE token = ?",
                (rs, i) -> new RefreshTokenRecord(
                        UUID.fromString(rs.getString("id")),
                        UUID.fromString(rs.getString("user_id")),
                        UUID.fromString(rs.getString("session_id")),
                        rs.getObject("expires_at", OffsetDateTime.class),
                        rs.getBoolean("revoked")
                ),
                token
        );
        return rows.stream().findFirst();
    }

    public void revokeRefreshToken(UUID id) {
        jdbc.update("UPDATE refresh_tokens SET revoked = true WHERE id = ?", id);
    }

    public void updateSessionToken(UUID sessionId, String newAccessToken, long ttlSeconds) {
        jdbc.update(
                "UPDATE user_sessions SET access_token = ?, expires_at = ? WHERE id = ?",
                newAccessToken, OffsetDateTime.now().plusSeconds(ttlSeconds), sessionId
        );
    }

}