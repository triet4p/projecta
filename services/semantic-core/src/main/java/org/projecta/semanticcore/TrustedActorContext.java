package org.projecta.semanticcore;

/** Server-established actor context for catalog operations before project selection. */
public record TrustedActorContext(String actorId, String operationId) {
    public TrustedActorContext {
        if (actorId == null || actorId.isBlank()) throw new IllegalArgumentException("trusted actor is required");
    }
}
