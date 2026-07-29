package org.projecta.semanticcore;

import java.net.URI;

/** Produces only canonical, project-scoped graph IRIs. */
public final class GraphIriRouter {
    private static final String DATA_BASE = "https://w3id.org/projecta/data/project/";

    public URI route(ProjectId projectId, GraphRole role) {
        if (projectId == null || role == null) {
            throw new IllegalArgumentException("project ID and graph role are required");
        }
        return URI.create(DATA_BASE + projectId.value() + "/" + role.pathSegment() + "/");
    }
}
