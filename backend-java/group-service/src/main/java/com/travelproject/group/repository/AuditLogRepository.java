package com.travelproject.group.repository;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;
import java.util.UUID;

@Repository
public class AuditLogRepository {

    private final JdbcTemplate jdbc;

    public AuditLogRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    /** newValueJson — уже сериализованный JSON-текст, или null. */
    public void log(UUID userId, String entityName, UUID entityId, String action, String newValueJson, String ipAddress) {
        jdbc.update(
                """
                INSERT INTO audit_log (id, user_id, entity_name, entity_id, action, new_value, ip_address, created_at)
                VALUES (?, ?, ?, ?, ?, ?::json, ?, now())
                """,
                UUID.randomUUID(), userId, entityName, entityId, action, newValueJson, ipAddress
        );
    }
}