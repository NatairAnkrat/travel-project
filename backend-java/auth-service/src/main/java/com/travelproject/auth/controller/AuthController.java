package com.travelproject.auth.controller;

import com.travelproject.auth.dto.*;
import com.travelproject.auth.repository.AuditLogRepository;
import com.travelproject.auth.repository.SessionRepository;
import com.travelproject.auth.repository.UserRepository;
import com.travelproject.auth.service.JwtService;
import com.travelproject.auth.service.PasswordService;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;

@RestController
@RequestMapping("/api/v1/auth")
public class AuthController {

    private final UserRepository userRepository;
    private final SessionRepository sessionRepository;
    private final AuditLogRepository auditLogRepository;
    private final PasswordService passwordService;
    private final JwtService jwtService;

    public AuthController(UserRepository userRepository, SessionRepository sessionRepository,
                           AuditLogRepository auditLogRepository, PasswordService passwordService,
                           JwtService jwtService) {
        this.userRepository = userRepository;
        this.sessionRepository = sessionRepository;
        this.auditLogRepository = auditLogRepository;
        this.passwordService = passwordService;
        this.jwtService = jwtService;
    }

    @PostMapping("/register")
    public ResponseEntity<Map<String, UUID>> register(@RequestBody RegisterRequest req, HttpServletRequest http) {
        String hash = passwordService.hash(req.password());
        UUID userId = userRepository.createUser(req, hash);

        auditLogRepository.log(userId, "users", userId, "CREATE",
                "{\"login\":\"" + req.login() + "\",\"email\":\"" + req.email() + "\"}",
                http.getRemoteAddr());

        return ResponseEntity.status(HttpStatus.CREATED).body(Map.of("user_id", userId));
    }

    @PostMapping("/login")
    public ResponseEntity<AuthResponse> login(@RequestBody LoginRequest req, HttpServletRequest http) {
        Optional<Object[]> found = userRepository.findForLogin(req.login());
        if (found.isEmpty()) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).build();
        }
        UUID userId = (UUID) found.get()[0];
        String storedHash = (String) found.get()[1];

        if (!passwordService.matches(req.password(), storedHash)) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).build();
        }

        String accessToken = jwtService.generateAccessToken(userId);
        long ttl = jwtService.accessTtlSeconds();
        UUID sessionId = sessionRepository.createSession(userId, accessToken, req.device(), http.getRemoteAddr(), ttl);
        String refreshToken = sessionRepository.createRefreshToken(userId, sessionId, 30);

        userRepository.updateLastLogin(userId);
        auditLogRepository.log(userId, "users", userId, "LOGIN", null, http.getRemoteAddr());

        return ResponseEntity.ok(new AuthResponse(userId, accessToken, refreshToken, ttl));
    }
}