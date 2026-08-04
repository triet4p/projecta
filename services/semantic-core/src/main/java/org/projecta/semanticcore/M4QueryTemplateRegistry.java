package org.projecta.semanticcore;

import java.util.Map;
import java.util.Set;

/** Versioned allowlist for M4 queries; callers can never supply SPARQL or graph IRIs. */
public final class M4QueryTemplateRegistry {
    public static final String VERSION = "m4.v1";
    private static final Set<String> IDS = Set.of("current-requirements", "requirement-history", "unresolved-blockers");

    public String validate(String queryId, Map<String, ?> parameters) {
        if (!IDS.contains(queryId)) throw new IllegalArgumentException("query ID is not allowlisted");
        if (parameters == null) throw new IllegalArgumentException("query parameters are required");
        var allowed = queryId.equals("requirement-history") ? Set.of("limit", "requirementId") : Set.of("limit");
        for (var key : parameters.keySet()) {
            if (!allowed.contains(key)) throw new IllegalArgumentException("query parameter is not allowlisted");
        }
        Object limit = parameters.containsKey("limit") ? parameters.get("limit") : Integer.valueOf(50);
        if (!(limit instanceof Number number) || number.intValue() < 1 || number.intValue() > 100)
            throw new IllegalArgumentException("query limit must be between 1 and 100");
        if (queryId.equals("requirement-history")
                && !(parameters.get("requirementId") instanceof String id && id.matches("[a-z0-9][a-z0-9-]{0,62}")))
            throw new IllegalArgumentException("requirement ID is required");
        if (!queryId.equals("requirement-history") && parameters.containsKey("requirementId"))
            throw new IllegalArgumentException("requirement ID is not valid for this query");
        return queryId;
    }

    public Set<String> queryIds() {
        return IDS;
    }
}
