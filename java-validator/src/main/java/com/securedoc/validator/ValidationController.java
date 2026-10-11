package com.securedoc.validator;

import java.util.Map;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

/** HTTP surface for the validation service. */
@RestController
public class ValidationController {

    private final DocumentValidator validator;

    public ValidationController(DocumentValidator validator) {
        this.validator = validator;
    }

    @GetMapping("/health")
    public Map<String, String> health() {
        return Map.of("status", "ok", "service", "java-validator");
    }

    @PostMapping("/api/v1/validate")
    public ValidationResponse validate(@RequestBody ValidationRequest request) {
        return validator.validate(request);
    }
}
