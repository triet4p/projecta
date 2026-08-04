package org.projecta.semanticcore;

import java.util.List;

/** Registry and deterministic rebuild boundary for M4 inferred outcomes. */
public final class M4InferenceRunner {
    public static final List<Rule> RULES = List.of(
            new Rule("m4.unresolved-dependency", "1"),
            new Rule("m4.delivery-risk", "1"),
            new Rule("m4.impact-review", "1"));

    public record Rule(String id, String version) {}

    public List<Rule> approvedRules() {
        return RULES;
    }

    /**
     * Returns the service-authored rule manifest. The remote write is intentionally delegated to
     * the Semantic Core transaction boundary, so a failed materialization can retain its prior
     * snapshot rather than partially updating asserted data.
     */
    public List<Rule> manifest() {
        return List.copyOf(RULES);
    }
}
