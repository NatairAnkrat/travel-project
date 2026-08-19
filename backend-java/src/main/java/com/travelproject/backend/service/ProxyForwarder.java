package com.travelproject.backend.service;

import org.springframework.http.*;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestTemplate;
import java.util.Map;

@Component
public class ProxyForwarder {

    private final RestTemplate restTemplate;

    public ProxyForwarder(RestTemplate restTemplate) {
        this.restTemplate = restTemplate;
    }

    public ResponseEntity<Object> forward(String baseUrl, String path, HttpMethod method, Object body) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        try {
            return restTemplate.exchange(baseUrl + path, method, new HttpEntity<>(body, headers), Object.class);
        } catch (org.springframework.web.client.HttpStatusCodeException ex) {
            return ResponseEntity.status(ex.getStatusCode())
                    .body(Map.of("detail", ex.getResponseBodyAsString()));
        }
    }
}