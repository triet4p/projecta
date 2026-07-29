package org.projecta.semanticcore;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import org.apache.jena.rdf.model.Model;
import org.apache.jena.rdf.model.ModelFactory;
import org.apache.jena.riot.Lang;
import org.apache.jena.riot.RDFParser;

/** Executes only service-authored, project-scoped SPARQL against the configured Fuseki dataset. */
public final class FusekiGateway {
    private final HttpClient client;
    private final URI datasetUrl;

    public FusekiGateway(HttpClient client, URI datasetUrl) {
        this.client = client;
        this.datasetUrl = datasetUrl;
    }

    public boolean ask(String query) {
        var response = send("query", "application/sparql-query", query);
        return response.matches("(?s).*\"boolean\"\\s*:\\s*true.*") || response.contains("<boolean>true</boolean>");
    }

    public String select(String query) {
        return send("query", "application/sparql-query", query);
    }

    public void update(String update) {
        send("update", "application/sparql-update", update);
    }

    /** Retrieves one named graph through Fuseki's Graph Store endpoint. */
    public Model graph(String graphIri) {
        var separator = datasetUrl.toString().contains("?") ? "&" : "?";
        var endpoint = URI.create(datasetUrl.toString().replaceAll("/$", "") + "/data" + separator + "graph="
                + java.net.URLEncoder.encode(graphIri, StandardCharsets.UTF_8));
        var request = HttpRequest.newBuilder(endpoint)
                .header("Accept", "text/turtle")
                .GET()
                .build();
        try {
            var response = client.send(request, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
            if (response.statusCode() < 200 || response.statusCode() >= 300) {
                throw new IllegalStateException("semantic store graph request failed");
            }
            var result = ModelFactory.createDefaultModel();
            RDFParser.create().fromString(response.body()).lang(Lang.TTL).parse(result);
            return result;
        } catch (IOException exception) {
            throw new IllegalStateException("semantic store graph request failed", exception);
        } catch (InterruptedException exception) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("semantic store graph request interrupted", exception);
        }
    }

    private String send(String path, String contentType, String body) {
        var endpoint = URI.create(datasetUrl.toString().replaceAll("/$", "") + "/" + path);
        var request = HttpRequest.newBuilder(endpoint)
                .header("Content-Type", contentType + "; charset=utf-8")
                .header("Accept", "application/sparql-results+json")
                .POST(HttpRequest.BodyPublishers.ofString(body, StandardCharsets.UTF_8))
                .build();
        try {
            var response = client.send(request, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
            if (response.statusCode() < 200 || response.statusCode() >= 300) {
                throw new IllegalStateException("semantic store request failed");
            }
            return response.body();
        } catch (IOException exception) {
            throw new IllegalStateException("semantic store request failed", exception);
        } catch (InterruptedException exception) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("semantic store request interrupted", exception);
        }
    }
}
