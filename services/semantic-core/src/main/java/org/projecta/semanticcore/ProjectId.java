package org.projecta.semanticcore;

import java.util.regex.Pattern;

/** Project identifier safe for the canonical graph-IRI path segment. */
public record ProjectId(String value) {
    private static final Pattern VALID_ID = Pattern.compile("[a-z0-9][a-z0-9-]{0,62}");

    public ProjectId {
        if (value == null || !VALID_ID.matcher(value).matches()) {
            throw new IllegalArgumentException("project ID must be a lowercase kebab-case identifier");
        }
    }
}
