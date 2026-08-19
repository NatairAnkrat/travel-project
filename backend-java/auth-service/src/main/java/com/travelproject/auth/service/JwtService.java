package com.travelproject.auth.service;

import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import javax.crypto.SecretKey;
import java.time.Instant;
import java.util.Date;
import java.util.UUID;

@Service
public class JwtService {

    private final SecretKey signingKey;
    private final long accessTtlMinutes;

    public JwtService(@Value("${auth.jwt.secret}") String secret,
                       @Value("${auth.jwt.access-ttl-minutes}") long accessTtlMinutes) {
        if (secret == null || secret.isBlank()) {
            // Явный отказ при старте вместо тихой уязвимости — без секрета JWT нельзя подписывать
            throw new IllegalStateException("JWT_SECRET is not set");
        }
        this.signingKey = Keys.hmacShaKeyFor(secret.getBytes());
        this.accessTtlMinutes = accessTtlMinutes;
    }

    public String generateAccessToken(UUID userId) {
        Instant now = Instant.now();
        return Jwts.builder()
                .subject(userId.toString())
                .issuedAt(Date.from(now))
                .expiration(Date.from(now.plusSeconds(accessTtlMinutes * 60)))
                .signWith(signingKey)
                .compact();
    }

    public long accessTtlSeconds() {
        return accessTtlMinutes * 60;
    }
}