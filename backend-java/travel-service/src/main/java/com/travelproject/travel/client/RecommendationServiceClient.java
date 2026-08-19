package com.travelproject.travel.client;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestTemplate;
import java.util.Map;

@Component
public class RecommendationServiceClient {

    private final RestTemplate restTemplate;
    private final String baseUrl;

    public RecommendationServiceClient(RestTemplate restTemplate,
                                        @Value("${services.recommendation.url}") String baseUrl) {
        this.restTemplate = restTemplate;
        this.baseUrl = baseUrl;
    }

    @SuppressWarnings("unchecked")
    public String startGeneration(Map<String, Object> payload) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        ResponseEntity<Map> response = restTemplate.postForEntity(
                baseUrl + "/api/v1/recommendations", new HttpEntity<>(payload, headers), Map.class
        );
        Map<String, Object> body = (Map<String, Object>) response.getBody();
        return body != null ? String.valueOf(body.get("job_id")) : null;
    }

    public Map<String, Object> getStatus(String jobId) {
        return restTemplate.getForObject(baseUrl + "/api/v1/recommendations/" + jobId, Map.class);
    }
}