package org.projecta.semanticcore;

import java.util.List;

/** Deterministic SHACL conformance result for a candidate graph. */
public record CandidateValidationResult(boolean conforms, List<Violation> violations) {
    public record Violation(String shape, String path, String message) {
        public Violation(String message) {
            this(null, null, message);
        }
    }
}
