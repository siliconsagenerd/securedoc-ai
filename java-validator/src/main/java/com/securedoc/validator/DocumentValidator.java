package com.securedoc.validator;

import java.util.HashMap;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

/**
 * Decides whether uploaded document metadata is acceptable. Pure in-memory logic
 * with no I/O, so it is cheap to call on every request and trivial to unit test.
 */
@Component
public class DocumentValidator {

    private static final Map<String, String> EXTENSION_CONTENT_TYPE = Map.of(
            ".txt", "text/plain",
            ".md", "text/markdown",
            ".pdf", "application/pdf",
            ".docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document");

    /** Text formats that browsers or tools commonly report as plain text. */
    private static final Set<String> PLAIN_TEXT_ALIASES = Set.of("text/plain", "text/markdown");

    private final long maxFileSizeBytes;

    public DocumentValidator(@Value("${validator.max-file-size-bytes:5242880}") long maxFileSizeBytes) {
        this.maxFileSizeBytes = maxFileSizeBytes;
    }

    public ValidationResponse validate(ValidationRequest request) {
        String filename = request.filename() == null ? "" : request.filename().trim();
        String extension = extensionOf(filename);

        boolean extensionOk = isSafeFilename(filename)
                && EXTENSION_CONTENT_TYPE.containsKey(extension);
        boolean contentTypeOk = extensionOk && contentTypeMatches(extension, request.contentType());
        boolean sizeOk = request.sizeBytes() <= maxFileSizeBytes;
        boolean notEmpty = request.sizeBytes() > 0;

        Map<String, Boolean> checks = new HashMap<>();
        checks.put("file_extension", extensionOk);
        checks.put("content_type", contentTypeOk);
        checks.put("size_limit", sizeOk);
        checks.put("not_empty", notEmpty);

        String reason = null;
        if (!extensionOk) {
            reason = "unsupported or unsafe filename: must be one of " + EXTENSION_CONTENT_TYPE.keySet();
        } else if (!contentTypeOk) {
            reason = "content type does not match extension " + extension;
        } else if (!sizeOk) {
            reason = "file exceeds the " + maxFileSizeBytes + " byte limit";
        } else if (!notEmpty) {
            reason = "file is empty";
        }

        return new ValidationResponse(reason == null, reason, checks);
    }

    private static String extensionOf(String filename) {
        int dot = filename.lastIndexOf('.');
        return dot < 0 ? "" : filename.substring(dot).toLowerCase(Locale.ROOT);
    }

    /** Rejects path separators and traversal so a filename cannot escape a directory. */
    private static boolean isSafeFilename(String filename) {
        return !filename.isEmpty()
                && !filename.contains("/")
                && !filename.contains("\\")
                && !filename.contains("..")
                && !filename.startsWith(".");
    }

    private static boolean contentTypeMatches(String extension, String contentType) {
        if (contentType == null || contentType.isBlank()) {
            return false;
        }
        String normalized = contentType.split(";")[0].trim().toLowerCase(Locale.ROOT);
        return EXTENSION_CONTENT_TYPE.getOrDefault(extension, "").equals(normalized)
                || (PLAIN_TEXT_ALIASES.contains(normalized) && PLAIN_TEXT_ALIASES.contains(EXTENSION_CONTENT_TYPE.get(extension)));
    }
}
