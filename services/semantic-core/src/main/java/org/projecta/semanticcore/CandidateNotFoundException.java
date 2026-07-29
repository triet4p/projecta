package org.projecta.semanticcore;

/** A candidate is not visible in the trusted project's candidates graph. */
public final class CandidateNotFoundException extends RuntimeException {
    public CandidateNotFoundException() {
        super("candidate is not visible in the trusted project");
    }
}
