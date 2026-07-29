package org.projecta.semanticcore;

import java.net.URI;
import java.util.Map;

/** Validated runtime configuration. */
public record SemanticCoreConfiguration(URI fusekiDatasetUrl, int port) {
    private static final String FUSEKI_BASE_URL = "FUSEKI_BASE_URL";
    private static final String PORT = "SEMANTIC_CORE_PORT";

    public static SemanticCoreConfiguration fromEnvironment(Map<String, String> environment) {
        var rawFusekiUrl = environment.get(FUSEKI_BASE_URL);
        if (rawFusekiUrl == null || rawFusekiUrl.isBlank()) {
            throw new IllegalArgumentException(FUSEKI_BASE_URL + " is required");
        }

        var fusekiUrl = URI.create(rawFusekiUrl);
        if (!("http".equals(fusekiUrl.getScheme()) || "https".equals(fusekiUrl.getScheme()))
                || fusekiUrl.getHost() == null) {
            throw new IllegalArgumentException(FUSEKI_BASE_URL + " must be an absolute HTTP(S) URL");
        }

        var rawPort = environment.getOrDefault(PORT, "8080");
        try {
            var port = Integer.parseInt(rawPort);
            if (port < 1 || port > 65535) {
                throw new IllegalArgumentException(PORT + " must be between 1 and 65535");
            }
            return new SemanticCoreConfiguration(fusekiUrl, port);
        } catch (NumberFormatException exception) {
            throw new IllegalArgumentException(PORT + " must be an integer", exception);
        }
    }

    public URI fusekiPingUrl() {
        return URI.create(fusekiDatasetUrl.getScheme() + "://" + fusekiDatasetUrl.getAuthority() + "/$/ping");
    }
}
