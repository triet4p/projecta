package org.projecta.semanticcore;

/** Raised when released SHACL shapes reject the requested candidate. */
public final class CandidateInvalidException extends RuntimeException {
    private final CandidateValidationResult result;

    public CandidateInvalidException(CandidateValidationResult result) {
        super("candidate does not conform to released SHACL shapes");
        this.result = result;
    }

    public CandidateValidationResult result() {
        return result;
    }
}
