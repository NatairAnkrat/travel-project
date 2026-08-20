package com.travelproject.travel.controller;

import com.travelproject.travel.service.ProxyForwarder;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpMethod;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/v1")
public class EditController {

    private final ProxyForwarder proxy;
    private final String baseUrl;

    public EditController(ProxyForwarder proxy, @Value("${services.edit.url}") String baseUrl) {
        this.proxy = proxy;
        this.baseUrl = baseUrl;
    }

    @PostMapping("/travels/{travelId}/edit")
    public ResponseEntity<Object> editTravel(@PathVariable String travelId, @RequestBody Object body) {
        return proxy.forward(baseUrl, "/api/v1/travels/" + travelId + "/edit", HttpMethod.POST, body);
    }

    @GetMapping("/edits/{jobId}")
    public ResponseEntity<Object> getEdit(@PathVariable String jobId) {
        return proxy.forward(baseUrl, "/api/v1/edits/" + jobId, HttpMethod.GET, null);
    }
}