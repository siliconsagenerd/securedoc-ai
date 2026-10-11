package com.securedoc.validator;

import java.util.Map;

/**
 * Structured validation outcome.
 *
 * @param valid   true only when every check passed
 * @param reason  human-readable reason for the first failed check, or null
 * @param checks  individual check results keyed by check name
 */
public record ValidationResponse(boolean valid, String reason, Map<String, Boolean> checks) {
}
