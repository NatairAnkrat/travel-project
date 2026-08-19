package com.travelproject.backend.repository;

import com.travelproject.backend.dto.CreateTravelRequest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;
import java.sql.Date;
import java.time.OffsetDateTime;
import java.util.UUID;

@Repository
public class TravelRepository {

    private final JdbcTemplate jdbc;

    public TravelRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public UUID[] createTravelWithFirstVersion(CreateTravelRequest req) {
        UUID travelId = UUID.randomUUID();
        UUID versionId = UUID.randomUUID();
        OffsetDateTime now = OffsetDateTime.now();

        jdbc.update(
                """
                INSERT INTO travels
                    (id, group_id, title, description, destination_city_id, start_date, end_date, status, created_by, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'planned', ?, ?, ?)
                """,
                travelId, req.groupId(), req.title(), req.description(), req.destinationCityId(),
                Date.valueOf(req.startDate()), Date.valueOf(req.endDate()), req.createdBy(), now, now
        );

        jdbc.update(
                """
                INSERT INTO travel_versions
                    (id, travel_id, version_number, description, created_by, is_current, created_at)
                VALUES (?, ?, 1, 'initial version', ?, true, ?)
                """,
                versionId, travelId, req.createdBy(), now
        );

        return new UUID[]{travelId, versionId};
    }
}