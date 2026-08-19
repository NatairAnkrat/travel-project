package com.travelproject.group.repository;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;
import java.time.OffsetDateTime;
import java.util.Optional;
import java.util.UUID;

@Repository
public class GroupRepository {

    private final JdbcTemplate jdbc;

    public GroupRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public UUID createGroup(String name, String description) {
        UUID groupId = UUID.randomUUID();
        OffsetDateTime now = OffsetDateTime.now();
        jdbc.update(
                "INSERT INTO travel_groups (id, name, description, status, created_at, updated_at) VALUES (?, ?, ?, 'active', ?, ?)",
                groupId, name, description, now, now
        );
        return groupId;
    }

    public void addMember(UUID groupId, UUID userId, UUID roleId, String status) {
        jdbc.update(
                "INSERT INTO group_members (id, group_id, user_id, role_id, joined_at, status) VALUES (?, ?, ?, ?, ?, ?)",
                UUID.randomUUID(), groupId, userId, roleId, OffsetDateTime.now(), status
        );
    }

    public Optional<UUID> findRoleIdByCode(String code) {
        var rows = jdbc.query(
                "SELECT id FROM group_roles WHERE code = ?",
                (rs, i) -> UUID.fromString(rs.getString("id")),
                code
        );
        return rows.stream().findFirst();
    }

    public boolean isMember(UUID groupId, UUID userId) {
        Integer count = jdbc.queryForObject(
                "SELECT COUNT(*) FROM group_members WHERE group_id = ? AND user_id = ?",
                Integer.class, groupId, userId
        );
        return count != null && count > 0;
    }
}