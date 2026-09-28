package org.projecta.semanticcore;

/** Finite causes that make an inferred projection non-current. */
public record InferenceInvalidation(
        String project, Cause cause, String expectedCurrentInferenceRevision, String idempotencyKey) {
    public enum Cause {
        CORRECTION,
        REJECTION,
        SOURCE_SUPERSESSION,
        ASSERTION_REVISION,
        RULE_CHANGE,
        ONTOLOGY_CHANGE
    }

    public InferenceInvalidation {
        new ProjectId(project);
        if (cause == null || expectedCurrentInferenceRevision == null || expectedCurrentInferenceRevision.isBlank()) {
            throw new IllegalArgumentException("invalidation cause and expected revision are required");
        }
        if (!"none".equals(expectedCurrentInferenceRevision)
                && !expectedCurrentInferenceRevision.matches("sha256:[0-9a-f]{64}")) {
            throw new IllegalArgumentException("expected inference revision is invalid");
        }
        if (idempotencyKey == null
                || idempotencyKey.isBlank()
                || idempotencyKey.length() > 128
                || idempotencyKey.indexOf('|') >= 0) {
            throw new IllegalArgumentException("idempotency key is invalid");
        }
    }

    public String bodyDigest() {
        return ApprovedAssertionPlan.digest("inference-invalidation.v1|" + project + "|" + cause + "|"
                + expectedCurrentInferenceRevision + "|" + idempotencyKey);
    }
}
