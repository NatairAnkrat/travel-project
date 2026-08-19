package com.travelproject.group.repository;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;
import java.time.OffsetDateTime;
import java.util.Optional;
import java.util.UUID;

@Repository
public class InvitationRepository {

    private final JdbcTemplate jdbc;

    public InvitationRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public UUID createInvitation(UUID groupId, String email, UUID createdBy) {
        UUID id = UUID.randomUUID();
        UUID token = UUID.randomUUID();
        OffsetDateTime now = OffsetDateTime.now();
        jdbc.update(
                """
                INSERT INTO invitations (id, group_id, email, token, status, created_by, expires_at, created_at)
                VALUES (?, ?, ?, ?, 'pending', ?, ?, ?)
                """,
                id, groupId, email, token, createdBy, now.plusDays(7), now
        );
        return token;
    }

    public record InvitationRecord(UUID id, UUID groupId, String email, String status, OffsetDateTime expiresAt) {}

    public Optional<InvitationRecord> findByToken(UUID token) {
        var rows = jdbc.query(
                "SELECT id, group_id, email, status, expires_at FROM invitations WHERE token = ?",
                (rs, i) -> new InvitationRecord(
                        UUID.fromString(rs.getString("id")),
                        UUID.fromString(rs.getString("group_id")),
                        rs.getString("email"),
                        rs.getString("status"),
                        rs.getObject("expires_at", OffsetDateTime.class)
                ),
                token
        );
        return rows.stream().findFirst();
    }

    public void updateStatus(UUID id, String status) {
        jdbc.update("UPDATE invitations SET status = ? WHERE id = ?", status, id);
    }
}