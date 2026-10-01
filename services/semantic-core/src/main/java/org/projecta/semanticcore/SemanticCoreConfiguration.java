package org.projecta.semanticcore;

import java.net.URI;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Map;

/** Validated runtime configuration. */
public record SemanticCoreConfiguration(URI fusekiDatasetUrl, String host, int port, Path shapesDirectory) {
    private static final String FUSEKI_BASE_URL = "FUSEKI_BASE_URL";
    private static final String HOST = "SEMANTIC_CORE_HOST";
    private static final String PORT = "SEMANTIC_CORE_PORT";
    private static final String SHAPES_DIRECTORY = "PROJECTA_SHAPES_DIRECTORY";
    private static final String DEFAULT_SHAPES_DIRECTORY = "/ontology/shapes";

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

        var rawHost = environment.getOrDefault(HOST, "0.0.0.0").trim();
        if (!rawHost.equals("0.0.0.0") && !rawHost.equals("127.0.0.1")) {
            throw new IllegalArgumentException(HOST + " must be 0.0.0.0 or 127.0.0.1");
        }
        var rawPort = environment.getOrDefault(PORT, "8080");
        var rawShapes = environment.getOrDefault(SHAPES_DIRECTORY, DEFAULT_SHAPES_DIRECTORY).trim();
        if (rawShapes.isBlank()) {
            throw new IllegalArgumentException(SHAPES_DIRECTORY + " must not be blank");
        }
        try {
            var port = Integer.parseInt(rawPort);
            if (port < 1 || port > 65535) {
                throw new IllegalArgumentException(PORT + " must be between 1 and 65535");
            }
            return new SemanticCoreConfiguration(fusekiUrl, rawHost, port, Paths.get(rawShapes));
        } catch (NumberFormatException exception) {
            throw new IllegalArgumentException(PORT + " must be an integer", exception);
        }
    }

    public URI fusekiReadinessUrl() {
        return URI.create(fusekiDatasetUrl + "/query?query=ASK%7B%7D");
    }
}
