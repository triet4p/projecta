package org.projecta.semanticcore;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.logging.Logger;
import org.apache.jena.rdf.model.Model;
import org.apache.jena.rdf.model.ModelFactory;
import org.apache.jena.riot.Lang;
import org.apache.jena.riot.RDFParser;

/** Executes only service-authored, project-scoped SPARQL against the configured Fuseki dataset. */
public class FusekiGateway {
    private static final Logger LOGGER = Logger.getLogger("projecta.fuseki-gateway");
    private static final ObjectMapper JSON = new ObjectMapper();
    private final HttpClient client;
    private final URI datasetUrl;
    private final ThreadLocal<Correlation> correlation =
            ThreadLocal.withInitial(() -> new Correlation("req-unknown", "op-unknown"));

    public FusekiGateway(HttpClient client, URI datasetUrl) {
        this.client = client;
        this.datasetUrl = datasetUrl;
    }

    /** Bind only safe request/operation identities for the current request thread. */
    public void setCorrelation(String requestId, String operationId) {
        correlation.set(new Correlation(safe(requestId, "req-unknown"), safe(operationId, "op-unknown")));
    }

    /** Executes a service-authored ASK query and returns its boolean result. */
    public boolean ask(String query) {
        var response = send("query", "application/sparql-query", query);
        return response.matches("(?s).*\"boolean\"\\s*:\\s*true.*") || response.contains("<boolean>true</boolean>");
    }

    /** Executes a service-authored SELECT query and returns its SPARQL JSON response. */
    public String select(String query) {
        return send("query", "application/sparql-query", query);
    }

    /** Executes one service-authored SPARQL Update request against the configured dataset. */
    public void update(String update) {
        send("update", "application/sparql-update", update);
    }

    /** Retrieves one named graph through Fuseki's Graph Store endpoint. */
    public Model graph(String graphIri) {
        var separator = datasetUrl.toString().contains("?") ? "&" : "?";
        var endpoint = URI.create(datasetUrl.toString().replaceAll("/$", "") + "/data" + separator + "graph="
                + java.net.URLEncoder.encode(graphIri, StandardCharsets.UTF_8));
        var started = System.nanoTime();
        log("dependency.started", "graph-read", null, null, null);
        var request = HttpRequest.newBuilder(endpoint)
                .header("Accept", "text/turtle")
                .timeout(Duration.ofSeconds(10))
                .GET()
                .build();
        try {
            var response = client.send(request, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
            if (response.statusCode() == 404) {
                // Fuseki does not materialize an empty named graph until its first write.
                // Treating that normal state as an empty graph is required for first capture
                // and for target-closure validation of projects with no asserted data yet.
                log("dependency.completed", "graph-read", 404, elapsed(started), 0L);
                return ModelFactory.createDefaultModel();
            }
            if (response.statusCode() < 200 || response.statusCode() >= 300) {
                log("dependency.failed", "graph-read", response.statusCode(), elapsed(started), null);
                throw new IllegalStateException("semantic store graph request failed");
            }
            var result = ModelFactory.createDefaultModel();
            RDFParser.create().fromString(response.body()).lang(Lang.TTL).parse(result);
            log("dependency.completed", "graph-read", response.statusCode(), elapsed(started), (long) result.size());
            return result;
        } catch (java.net.http.HttpTimeoutException exception) {
            log("dependency.failed", "graph-read", 504, elapsed(started), null);
            throw new IllegalStateException("semantic store graph request timed out", exception);
        } catch (IOException exception) {
            log("dependency.failed", "graph-read", 503, elapsed(started), null);
            throw new IllegalStateException("semantic store graph request failed", exception);
        } catch (InterruptedException exception) {
            Thread.currentThread().interrupt();
            log("dependency.failed", "graph-read", 503, elapsed(started), null);
            throw new IllegalStateException("semantic store graph request interrupted", exception);
        }
    }

    private String send(String path, String contentType, String body) {
        var endpoint = URI.create(datasetUrl.toString().replaceAll("/$", "") + "/" + path);
        var started = System.nanoTime();
        var operation = "update".equals(path) ? "sparql-update" : "sparql-query";
        log("dependency.started", operation, null, null, null);
        var request = HttpRequest.newBuilder(endpoint)
                .header("Content-Type", contentType + "; charset=utf-8")
                .header("Accept", "application/sparql-results+json")
                .timeout(Duration.ofSeconds(10))
                .POST(HttpRequest.BodyPublishers.ofString(body, StandardCharsets.UTF_8))
                .build();
        try {
            var response = client.send(request, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
            if (response.statusCode() < 200 || response.statusCode() >= 300) {
                log("dependency.failed", operation, response.statusCode(), elapsed(started), null);
                throw new IllegalStateException("semantic store request failed");
            }
            log(
                    "dependency.completed",
                    operation,
                    response.statusCode(),
                    elapsed(started),
                    cardinality(response.body()));
            return response.body();
        } catch (java.net.http.HttpTimeoutException exception) {
            log("dependency.failed", operation, 504, elapsed(started), null);
            throw new IllegalStateException("semantic store request timed out", exception);
        } catch (IOException exception) {
            log("dependency.failed", operation, 503, elapsed(started), null);
            throw new IllegalStateException("semantic store request failed", exception);
        } catch (InterruptedException exception) {
            Thread.currentThread().interrupt();
            log("dependency.failed", operation, 503, elapsed(started), null);
            throw new IllegalStateException("semantic store request interrupted", exception);
        }
    }

    private void log(String event, String operation, Integer status, Long latencyMs, Long cardinality) {
        var current = correlation.get();
        LOGGER.info(String.format(
                "event=%s service=fuseki-gateway dependency=fuseki requestId=%s operationId=%s operation=%s attempt=1 status=%s latencyMs=%s resultCardinality=%s",
                event,
                current.requestId(),
                current.operationId(),
                operation,
                status == null ? "null" : status,
                latencyMs == null ? "null" : latencyMs,
                cardinality == null ? "null" : cardinality));
    }

    private static long elapsed(long started) {
        return (System.nanoTime() - started) / 1_000_000;
    }

    private static long cardinality(String body) {
        try {
            var bindings = JSON.readTree(body).path("results").path("bindings");
            return bindings.isArray() ? bindings.size() : 0;
        } catch (Exception ignored) {
            return 0;
        }
    }

    private static String safe(String value, String fallback) {
        return value == null || value.isBlank() || value.length() > 128 ? fallback : value;
    }

    private record Correlation(String requestId, String operationId) {}
}
