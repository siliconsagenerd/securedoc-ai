package com.securedoc.validator;

import com.fasterxml.jackson.annotation.JsonProperty;

/**
 * Incoming document metadata. Field names follow the API contract (snake_case)
 * and contain no document content — only enough to make a validation decision.
 */
public record ValidationRequest(
        @JsonProperty("filename") String filename,
        @JsonProperty("content_type") String contentType,
        @JsonProperty("size_bytes") long sizeBytes) {
}
