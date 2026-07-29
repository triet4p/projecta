package org.projecta.semanticcore;

/** Canonical lifecycle graph roles. */
public enum GraphRole {
    SOURCES("sources"),
    CANDIDATES("candidates"),
    ASSERTED("asserted"),
    INFERRED("inferred"),
    PROVENANCE("provenance");

    private final String pathSegment;

    GraphRole(String pathSegment) {
        this.pathSegment = pathSegment;
    }

    public String pathSegment() {
        return pathSegment;
    }
}
