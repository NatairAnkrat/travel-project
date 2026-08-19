package com.travelproject.auth.repository;

import com.travelproject.auth.dto.RegisterRequest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;
import java.time.OffsetDateTime;
import java.util.Optional;
import java.util.UUID;

@Repository
public class UserRepository {

    private final JdbcTemplate jdbc;

    public UserRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public UUID createUser(RegisterRequest req, String passwordHash) {
        UUID userId = UUID.randomUUID();
        OffsetDateTime now = OffsetDateTime.now();

        jdbc.update(
                """
                INSERT INTO users (id, login, password_hash, email, phone, is_active, email_verified, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, true, false, ?, ?)
                """,
                userId, req.login(), passwordHash, req.email(), req.phone(), now, now
        );

        jdbc.update(
                """
                INSERT INTO user_profile (id, user_id, first_name, last_name, language_id, timezone, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                UUID.randomUUID(), userId, req.firstName(), req.lastName(), req.languageId(), req.timezone(), now, now
        );

        jdbc.update(
                """
                INSERT INTO user_settings (id, user_id, currency_id, language_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                UUID.randomUUID(), userId, req.currencyId(), req.languageId(), now, now
        );

        return userId;
    }

    /** Возвращает [id, password_hash] или пусто, если логина нет. */
    public Optional<Object[]> findForLogin(String login) {
        var rows = jdbc.query(
                "SELECT id, password_hash FROM users WHERE login = ? AND is_active = true",
                (rs, i) -> new Object[]{UUID.fromString(rs.getString("id")), rs.getString("password_hash")},
                login
        );
        return rows.stream().findFirst();
    }

    public void updateLastLogin(UUID userId) {
        jdbc.update("UPDATE users SET last_login = ? WHERE id = ?", OffsetDateTime.now(), userId);
    }
}