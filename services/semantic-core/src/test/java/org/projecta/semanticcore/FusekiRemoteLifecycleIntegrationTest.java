package org.projecta.semanticcore;

import static org.junit.jupiter.api.Assertions.assertTrue;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.file.Path;
import java.time.LocalDate;
import java.util.concurrent.Executors;
import org.junit.jupiter.api.Assumptions;
import org.junit.jupiter.api.Test;

class FusekiRemoteLifecycleIntegrationTest {
    private static final String PROJECT = "ecommerce-checkout";

    @Test
    void executesConfirmationAndRejectionAgainstRemoteFuseki() {
        var endpoint = System.getenv("FUSEKI_BASE_URL");
        Assumptions.assumeTrue(
                endpoint != null && !endpoint.isBlank(), "remote Fuseki is only required in the system suite");
        var router = new GraphIriRouter();
        var project = new ProjectId(PROJECT);
        var gateway = new FusekiGateway(HttpClient.newHttpClient(), URI.create(endpoint));
        var candidate = "https://w3id.org/projecta/data/project/" + PROJECT + "/candidate/remote-candidate";
        gateway.update(
                """
                INSERT DATA { GRAPH <%s> {
                  <https://w3id.org/projecta/data/project/%s> a <https://w3id.org/projecta/ontology/Project> .
                  <%s> a <https://w3id.org/projecta/ontology/Candidate> ;
                    <https://w3id.org/projecta/ontology/candidateStatus> <https://w3id.org/projecta/ontology/validated> ;
                    <http://www.w3.org/ns/prov#wasDerivedFrom> <https://w3id.org/projecta/data/project/%s/note-item/source-1> ;
                    <http://www.w3.org/ns/prov#wasGeneratedBy> <https://w3id.org/projecta/data/project/%s/activity/extract-1> ;
                    <http://www.w3.org/ns/prov#generatedAtTime> "2026-07-29T10:00:00Z"^^<http://www.w3.org/2001/XMLSchema#dateTime> ;
                    <https://w3id.org/projecta/ontology/generator> "test-generator" ;
                    <https://w3id.org/projecta/ontology/proposedOntologyVersion> "0.2.0" ;
                    <https://w3id.org/projecta/ontology/belongsToProject> <https://w3id.org/projecta/data/project/%s> .
                } }
                """
                        .formatted(
                                router.route(project, GraphRole.CANDIDATES),
                                PROJECT,
                                candidate,
                                PROJECT,
                                PROJECT,
                                PROJECT));

        var service = lifecycle(gateway, router);
        var item = service.confirm(
                project,
                "remote-candidate",
                "le",
                "remote-confirm-01",
                "Remote requirement",
                LocalDate.of(2026, 7, 29));

        assertTrue(gateway.ask("ASK { GRAPH <" + router.route(project, GraphRole.ASSERTED) + "> { <" + item
                + "> <http://www.w3.org/2000/01/rdf-schema#label> \"Remote requirement\" } }"));
        assertTrue(
                gateway.ask(
                        "ASK { GRAPH <" + router.route(project, GraphRole.CANDIDATES) + "> { <" + candidate
                                + "> <https://w3id.org/projecta/ontology/candidateStatus> <https://w3id.org/projecta/ontology/asserted> } }"));
        assertTrue(
                gateway.ask("ASK { GRAPH <" + router.route(project, GraphRole.INFERRED) + "> { ?s ?p ?o } }") == false);

        var replay = lifecycle(new FusekiGateway(HttpClient.newHttpClient(), URI.create(endpoint)), router)
                .confirm(
                        project,
                        "remote-candidate",
                        "le",
                        "remote-confirm-01",
                        "Remote requirement",
                        LocalDate.of(2026, 7, 29));
        assertTrue(item.equals(replay));
    }

    @Test
    void allowsOnlyOneConcurrentTerminalDecisionOnRemoteFuseki() throws Exception {
        var endpoint = System.getenv("FUSEKI_BASE_URL");
        Assumptions.assumeTrue(
                endpoint != null && !endpoint.isBlank(), "remote Fuseki is only required in the system suite");
        var router = new GraphIriRouter();
        var project = new ProjectId(PROJECT);
        var gateway = new FusekiGateway(HttpClient.newHttpClient(), URI.create(endpoint));
        seedCandidate(gateway, router, project, "concurrent-candidate");
        var confirmationService =
                lifecycle(new FusekiGateway(HttpClient.newHttpClient(), URI.create(endpoint)), router);
        var rejectionService = lifecycle(new FusekiGateway(HttpClient.newHttpClient(), URI.create(endpoint)), router);
        var executor = Executors.newFixedThreadPool(2);
        try {
            var confirmation = executor.submit(() -> {
                try {
                    confirmationService.confirm(
                            project,
                            "concurrent-candidate",
                            "le",
                            "concurrent-confirm",
                            "Concurrent requirement",
                            LocalDate.of(2026, 7, 29));
                    return true;
                } catch (RuntimeException exception) {
                    return false;
                }
            });
            var rejection = executor.submit(() -> {
                try {
                    rejectionService.reject(
                            project, "concurrent-candidate", "le", "concurrent-reject", "Conflicting review.");
                    return true;
                } catch (RuntimeException exception) {
                    return false;
                }
            });
            assertTrue(confirmation.get() ^ rejection.get());
        } finally {
            executor.shutdownNow();
        }
    }

    @Test
    void executesLifecycleThroughTheRuntimeHttpApi() throws Exception {
        var endpoint = System.getenv("FUSEKI_BASE_URL");
        var coreUrl = System.getenv("SEMANTIC_CORE_HTTP_URL");
        Assumptions.assumeTrue(
                endpoint != null && coreUrl != null, "HTTP runtime is only required in the system suite");
        var router = new GraphIriRouter();
        var project = new ProjectId(PROJECT);
        seedCandidate(
                new FusekiGateway(HttpClient.newHttpClient(), URI.create(endpoint)), router, project, "http-candidate");
        var request = HttpRequest.newBuilder(URI.create(coreUrl + "/v1/candidates/http-candidate/confirmations"))
                .header("Content-Type", "application/json")
                .header("Idempotency-Key", "http-confirm-01")
                .header("X-Request-Id", "http-request-01")
                .POST(
                        HttpRequest.BodyPublishers.ofString(
                                "{\"assertion\":{\"type\":\"Requirement\",\"label\":\"HTTP requirement\",\"validFrom\":\"2026-07-29\"}}"))
                .build();
        var client = HttpClient.newHttpClient();
        HttpResponse<String> response = null;
        for (var attempt = 0; attempt < 20; attempt++) {
            try {
                response = client.send(request, HttpResponse.BodyHandlers.ofString());
                if (response.statusCode() != 503) break;
            } catch (java.io.IOException ignored) {
                Thread.sleep(250);
            }
            Thread.sleep(250);
        }
        assertTrue(response != null && response.statusCode() == 201, "confirmation HTTP endpoint must return 201");
        var replay = client.send(request, HttpResponse.BodyHandlers.ofString());
        assertTrue(replay.statusCode() == 200, "confirmation idempotent replay must return 200");
        var current = client.send(
                HttpRequest.newBuilder(URI.create(coreUrl + "/v1/knowledge-items/current?type=Requirement"))
                        .GET()
                        .build(),
                HttpResponse.BodyHandlers.ofString());
        assertTrue(current.statusCode() == 200 && current.body().contains("HTTP requirement"));
    }

    @Test
    void returnsContractProblemsForMissingAndInvalidRequestedCandidates() throws Exception {
        var endpoint = System.getenv("FUSEKI_BASE_URL");
        var coreUrl = System.getenv("SEMANTIC_CORE_HTTP_URL");
        Assumptions.assumeTrue(
                endpoint != null && coreUrl != null, "HTTP runtime is only required in the system suite");
        var router = new GraphIriRouter();
        var project = new ProjectId(PROJECT);
        var gateway = new FusekiGateway(HttpClient.newHttpClient(), URI.create(endpoint));
        seedCandidate(gateway, router, project, "valid-alongside-invalid");
        gateway.update("INSERT DATA { GRAPH <" + router.route(project, GraphRole.CANDIDATES)
                + "> { <https://w3id.org/projecta/data/project/" + PROJECT
                + "> a <https://w3id.org/projecta/ontology/Project> . <https://w3id.org/projecta/data/project/"
                + PROJECT
                + "/candidate/invalid-candidate> a <https://w3id.org/projecta/ontology/Candidate> ; <https://w3id.org/projecta/ontology/candidateStatus> <https://w3id.org/projecta/ontology/validated> ; <https://w3id.org/projecta/ontology/belongsToProject> <https://w3id.org/projecta/data/project/"
                + PROJECT + "> . } }");
        var client = HttpClient.newHttpClient();
        var missing = client.send(
                HttpRequest.newBuilder(URI.create(coreUrl + "/v1/candidates/missing-candidate/validations"))
                        .header("X-Request-Id", "missing-request")
                        .POST(HttpRequest.BodyPublishers.noBody())
                        .build(),
                HttpResponse.BodyHandlers.ofString());
        assertTrue(
                missing.statusCode() == 404
                        && missing.headers()
                                .firstValue("Content-Type")
                                .orElse("")
                                .contains("application/problem+json")
                        && missing.body().contains("CANDIDATE_NOT_FOUND"),
                () -> "missing response: " + missing.statusCode() + " " + missing.headers() + " " + missing.body());
        var invalid = client.send(
                HttpRequest.newBuilder(URI.create(coreUrl + "/v1/candidates/invalid-candidate/validations"))
                        .header("X-Request-Id", "invalid-request")
                        .POST(HttpRequest.BodyPublishers.noBody())
                        .build(),
                HttpResponse.BodyHandlers.ofString());
        assertTrue(invalid.statusCode() == 422
                && invalid.headers().firstValue("Content-Type").orElse("").contains("application/problem+json")
                && invalid.body().contains("violations"));
        var valid = client.send(
                HttpRequest.newBuilder(URI.create(coreUrl + "/v1/candidates/valid-alongside-invalid/validations"))
                        .header("X-Request-Id", "valid-request")
                        .POST(HttpRequest.BodyPublishers.noBody())
                        .build(),
                HttpResponse.BodyHandlers.ofString());
        assertTrue(valid.statusCode() == 200 && valid.body().contains("\"conforms\":true"));
    }

    private static void seedCandidate(FusekiGateway gateway, GraphIriRouter router, ProjectId project, String id) {
        var candidate = "https://w3id.org/projecta/data/project/" + PROJECT + "/candidate/" + id;
        gateway.update(
                """
                INSERT DATA { GRAPH <%s> { <https://w3id.org/projecta/data/project/%s> a <https://w3id.org/projecta/ontology/Project> . <%s> a <https://w3id.org/projecta/ontology/Candidate> ; <https://w3id.org/projecta/ontology/candidateStatus> <https://w3id.org/projecta/ontology/validated> ; <http://www.w3.org/ns/prov#wasDerivedFrom> <https://w3id.org/projecta/data/project/%s/note-item/source-%s> ; <http://www.w3.org/ns/prov#wasGeneratedBy> <https://w3id.org/projecta/data/project/%s/activity/extract-%s> ; <http://www.w3.org/ns/prov#generatedAtTime> "2026-07-29T10:00:00Z"^^<http://www.w3.org/2001/XMLSchema#dateTime> ; <https://w3id.org/projecta/ontology/generator> "test-generator" ; <https://w3id.org/projecta/ontology/proposedOntologyVersion> "0.2.0" ; <https://w3id.org/projecta/ontology/belongsToProject> <https://w3id.org/projecta/data/project/%s> . } }
                """
                        .formatted(
                                router.route(project, GraphRole.CANDIDATES),
                                PROJECT,
                                candidate,
                                PROJECT,
                                id,
                                PROJECT,
                                id,
                                PROJECT));
    }

    private static FusekiLifecycleService lifecycle(FusekiGateway gateway, GraphIriRouter router) {
        return new FusekiLifecycleService(
                gateway, router, new RemoteCandidateValidationService(gateway, router, Path.of("/ontology/shapes")));
    }
}
