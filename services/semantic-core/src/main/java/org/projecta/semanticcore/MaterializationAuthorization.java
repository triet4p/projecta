package org.projecta.semanticcore;

/** Explicit gate for the approved-assertion materialization boundary. */
public record MaterializationAuthorization(boolean enabled, boolean semanticOwnerReviewed) {
    public static MaterializationAuthorization disabled() {
        return new MaterializationAuthorization(false, false);
    }

    /** Test-only opt-in; production composition must supply an owner-reviewed decision. */
    public static MaterializationAuthorization enabledForTest() {
        return new MaterializationAuthorization(true, true);
    }

    public void requireEnabled() {
        if (!enabled || !semanticOwnerReviewed) {
            throw new IllegalStateException("approved assertion materialization is not owner-authorized");
        }
    }
}
