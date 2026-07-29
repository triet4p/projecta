package org.projecta.semanticcore;

import java.util.Map;

/** Server-established context; no project or actor identity is accepted from HTTP clients. */
public record TrustedProjectContext(ProjectId projectId, String actorId) {
    public static TrustedProjectContext fromEnvironment(Map<String, String> environment) {
        var project = environment.get("SEMANTIC_CORE_TRUSTED_PROJECT_ID");
        var actor = environment.get("SEMANTIC_CORE_TRUSTED_ACTOR_ID");
        if (project == null || actor == null || actor.isBlank()) {
            throw new IllegalStateException("trusted project context is not configured");
        }
        return new TrustedProjectContext(new ProjectId(project), actor);
    }
}
