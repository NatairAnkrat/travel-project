package com.travelproject.travel.controller;

import com.travelproject.backend.service.ProxyForwarder;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpMethod;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/v1/search")
public class SearchController {

    private final ProxyForwarder proxy;
    private final String baseUrl;

    public SearchController(ProxyForwarder proxy, @Value("${services.search.url}") String baseUrl) {
        this.proxy = proxy;
        this.baseUrl = baseUrl;
    }

    @PostMapping("/flights")
    public ResponseEntity<Object> searchFlights(@RequestBody Object body) {
        return proxy.forward(baseUrl, "/api/v1/search/flights", HttpMethod.POST, body);
    }

    @PostMapping("/flights/baggage-price")
    public ResponseEntity<Object> baggagePrice(@RequestBody Object body) {
        return proxy.forward(baseUrl, "/api/v1/search/flights/baggage-price", HttpMethod.POST, body);
    }

    @PostMapping("/hotels")
    public ResponseEntity<Object> searchHotels(@RequestBody Object body) {
        return proxy.forward(baseUrl, "/api/v1/search/hotels", HttpMethod.POST, body);
    }

    @PostMapping("/hotels/property-details")
    public ResponseEntity<Object> propertyDetails(@RequestBody Object body) {
        return proxy.forward(baseUrl, "/api/v1/search/hotels/property-details", HttpMethod.POST, body);
    }

    @PostMapping("/web")
    public ResponseEntity<Object> webSearch(@RequestBody Object body) {
        return proxy.forward(baseUrl, "/api/v1/search/web", HttpMethod.POST, body);
    }
}