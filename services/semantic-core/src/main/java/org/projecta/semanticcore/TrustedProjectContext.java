package org.projecta.semanticcore;

import java.util.Map;

/** Server-established context; no project or actor identity is accepted from HTTP clients. */
public record TrustedProjectContext(ProjectId projectId, String actorId, String operationId) {
    public TrustedProjectContext(ProjectId projectId, String actorId) {
        this(projectId, actorId, "op-environment");
    }

    public static TrustedProjectContext fromEnvironment(Map<String, String> environment) {
        var project = environment.get("SEMANTIC_CORE_TRUSTED_PROJECT_ID");
        var actor = environment.get("SEMANTIC_CORE_TRUSTED_ACTOR_ID");
        if (project == null || actor == null || actor.isBlank()) {
            throw new IllegalStateException("trusted project context is not configured");
        }
        return new TrustedProjectContext(new ProjectId(project), actor, "op-environment");
    }

    /**
     * Resolves context injected by the private Application API boundary.
     *
     * <p>The Semantic Core is never exposed on the public network. During direct runtime tests the
     * server-established environment context remains available as a fallback.
     */
    public static TrustedProjectContext fromPrivateHeadersOrEnvironment(
            String project, String actor, Map<String, String> environment) {
        return fromPrivateHeadersOrEnvironment(project, actor, null, environment);
    }

    public static TrustedProjectContext fromPrivateHeadersOrEnvironment(
            String project, String actor, String operation, Map<String, String> environment) {
        if (project == null && actor == null) {
            return fromEnvironment(environment);
        }
        if (project == null || actor == null || actor.isBlank()) {
            throw new IllegalArgumentException("trusted project context is incomplete");
        }
        return new TrustedProjectContext(new ProjectId(project), actor, safeOperation(operation));
    }

    private static String safeOperation(String operation) {
        return operation == null || operation.isBlank() ? "op-unknown" : operation;
    }
}
