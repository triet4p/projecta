package org.projecta.semanticcore;

/** Explicit gate for rebuilding inferred projections. */
public record InferenceRebuildAuthorization(boolean enabled, boolean semanticOwnerReviewed) {
    public static InferenceRebuildAuthorization disabled() {
        return new InferenceRebuildAuthorization(false, false);
    }

    /** Test-only opt-in; this does not authorize production runtime enablement. */
    public static InferenceRebuildAuthorization enabledForTest() {
        return new InferenceRebuildAuthorization(true, true);
    }

    public void requireEnabled() {
        if (!enabled || !semanticOwnerReviewed) {
            throw new IllegalStateException("inference rebuild is not owner-authorized");
        }
    }
}
