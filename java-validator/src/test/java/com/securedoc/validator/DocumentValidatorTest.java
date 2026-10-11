package com.securedoc.validator;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;

class DocumentValidatorTest {

    private static final long MAX_BYTES = 1024L;
    private final DocumentValidator validator = new DocumentValidator(MAX_BYTES);

    @Test
    void acceptsValidPdf() {
        ValidationResponse response = validator.validate(
                new ValidationRequest("report.pdf", "application/pdf", 512));

        assertTrue(response.valid());
        assertNull(response.reason());
        assertTrue(response.checks().values().stream().allMatch(Boolean::booleanValue));
    }

    @Test
    void acceptsTxtAsPlainText() {
        ValidationResponse response = validator.validate(
                new ValidationRequest("notes.txt", "text/plain; charset=utf-8", 10));

        assertTrue(response.valid());
    }

    @Test
    void rejectsUnsupportedExtension() {
        ValidationResponse response = validator.validate(
                new ValidationRequest("malware.exe", "application/octet-stream", 10));

        assertFalse(response.valid());
        assertFalse(response.checks().get("file_extension"));
    }

    @Test
    void rejectsPathTraversal() {
        ValidationResponse response = validator.validate(
                new ValidationRequest("../../etc/passwd.txt", "text/plain", 10));

        assertFalse(response.valid());
        assertFalse(response.checks().get("file_extension"));
    }

    @Test
    void rejectsEmptyFile() {
        ValidationResponse response = validator.validate(
                new ValidationRequest("empty.txt", "text/plain", 0));

        assertFalse(response.valid());
        assertFalse(response.checks().get("not_empty"));
    }

    @Test
    void rejectsOversizeFile() {
        ValidationResponse response = validator.validate(
                new ValidationRequest("big.pdf", "application/pdf", MAX_BYTES + 1));

        assertFalse(response.valid());
        assertFalse(response.checks().get("size_limit"));
    }

    @Test
    void rejectsContentTypeMismatch() {
        ValidationResponse response = validator.validate(
                new ValidationRequest("image.pdf", "image/png", 100));

        assertFalse(response.valid());
        assertFalse(response.checks().get("content_type"));
    }

    @Test
    void rejectsBlankFilename() {
        ValidationResponse response = validator.validate(
                new ValidationRequest("  ", "text/plain", 10));

        assertFalse(response.valid());
        assertFalse(response.checks().get("file_extension"));
    }

    @Test
    void reasonDescribesFirstFailureInOrder() {
        ValidationResponse response = validator.validate(
                new ValidationRequest("a.txt", "application/pdf", MAX_BYTES + 1));

        assertEquals(false, response.valid());
        assertTrue(response.reason().contains("content type"));
    }
}
