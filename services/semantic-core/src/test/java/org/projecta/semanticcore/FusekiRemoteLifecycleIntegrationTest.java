package org.projecta.semanticcore;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.file.Path;
import java.time.LocalDate;
import java.util.UUID;
import java.util.concurrent.Executors;
import org.junit.jupiter.api.Assumptions;
import org.junit.jupiter.api.Test;

class FusekiRemoteLifecycleIntegrationTest {
    private static final String PROJECT = "ecommerce-checkout";

    @Test
    void atomicallyCapturesProjectScopedSourceCandidatesAndProvenance() {
        var endpoint = System.getenv("FUSEKI_BASE_URL");
        Assumptions.assumeTrue(
                endpoint != null && !endpoint.isBlank(), "remote Fuseki is only required in the system suite");
        var router = new GraphIriRouter();
        var project = new ProjectId("capture-" + UUID.randomUUID().toString().substring(0, 8));
        var gateway = new FusekiGateway(HttpClient.newHttpClient(), URI.create(endpoint));
        var validation = new RemoteCandidateValidationService(gateway, router, Path.of("/ontology/shapes"));
        var service = new QuickNoteCaptureService(gateway, router, validation::validateCapture);
        var raw = "Confirm address. Tax timeout.";
        var request = new QuickNoteCaptureService.CaptureRequest(
                raw,
                java.util.List.of(
                        new QuickNoteCaptureService.Segment("requirement", 0, 16, "Confirm address."),
                        new QuickNoteCaptureService.Segment("risk", 17, 29, "Tax timeout.")));

        var capture = service.capture(project, "le", "capture-01", request);

        assertFalse(capture.replayed());
        assertTrue(capture.noteId().startsWith("note-"));
        assertFalse(capture.noteId().contains("capture-01"));
        assertEquals(2, capture.candidates().size());
        assertTrue(
                gateway.ask(
                        "ASK { GRAPH <" + router.route(project, GraphRole.SOURCES)
                                + "> { ?note <https://w3id.org/projecta/ontology/rawText> \"Confirm address. Tax timeout.\" ; <https://w3id.org/projecta/ontology/hasNoteItem> ?item . ?item <https://w3id.org/projecta/ontology/evidenceStartOffset> \"0\"^^<http://www.w3.org/2001/XMLSchema#nonNegativeInteger> } }"));
        assertTrue(
                gateway.ask(
                        "ASK { GRAPH <" + router.route(project, GraphRole.CANDIDATES)
                                + "> { ?candidate a <https://w3id.org/projecta/ontology/Candidate> ; <https://w3id.org/projecta/ontology/candidateStatus> <https://w3id.org/projecta/ontology/extracted> . } }"));
        assertTrue(
                gateway.ask(
                        "ASK { GRAPH <" + router.route(project, GraphRole.PROVENANCE)
                                + "> { ?activity a <http://www.w3.org/ns/prov#Activity> ; <http://www.w3.org/ns/prov#generated> ?candidate . } }"));
        assertFalse(gateway.ask("ASK { GRAPH <" + router.route(project, GraphRole.ASSERTED) + "> { ?s ?p ?o } }"));
        assertFalse(gateway.ask("ASK { GRAPH <" + router.route(project, GraphRole.INFERRED) + "> { ?s ?p ?o } }"));

        var replay = service.capture(project, "le", "capture-01", request);
        assertTrue(replay.replayed());
        assertEquals(capture.noteId(), replay.noteId());
        assertEquals(capture.candidates(), replay.candidates());

        var malformed = new QuickNoteCaptureService.CaptureRequest(
                raw, java.util.List.of(new QuickNoteCaptureService.Segment("unknown", 0, 16, "Confirm address.")));
        assertThrows(IllegalArgumentException.class, () -> service.capture(project, "le", "capture-bad", malformed));
        assertFalse(gateway.ask("ASK { GRAPH <" + router.route(project, GraphRole.PROVENANCE)
                + "> { <https://w3id.org/projecta/data/project/" + project.value()
                + "/capture-idempotency/capture-bad> ?p ?o } }"));

        var otherProject =
                new ProjectId("capture-" + UUID.randomUUID().toString().substring(0, 8));
        var isolated = service.capture(otherProject, "le", "capture-01", request);
        assertFalse(isolated.replayed());
        assertTrue(gateway.ask("ASK { GRAPH <" + router.route(otherProject, GraphRole.SOURCES)
                + "> { ?s a <https://w3id.org/projecta/ontology/Note> } }"));
        assertFalse(gateway.ask("ASK { GRAPH <" + router.route(otherProject, GraphRole.CANDIDATES)
                + "> { ?s <https://w3id.org/projecta/ontology/belongsToProject> <https://w3id.org/projecta/data/project/"
                + project.value() + "> } }"));
    }

    @Test
    void executesConfirmationAndRejectionAgainstRemoteFuseki() {
        var endpoint = System.getenv("FUSEKI_BASE_URL");
        Assumptions.assumeTrue(
                endpoint != null && !endpoint.isBlank(), "remote Fuseki is only required in the system suite");
        var router = new GraphIriRouter();
        var project = new ProjectId(PROJECT);
        var gateway = new FusekiGateway(HttpClient.newHttpClient(), URI.create(endpoint));
        var candidate = "https://w3id.org/projecta/data/project/" + PROJECT + "/candidate/remote-candidate";
        gateway.update("""
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
                } GRAPH <%s> {
                  <https://w3id.org/projecta/data/project/%s/note-item/source-1>
                    a <https://w3id.org/projecta/ontology/NoteItem> ;
                    <https://w3id.org/projecta/ontology/hasItemType> <https://w3id.org/projecta/ontology/requirement> .
                } }
                """.formatted(
                        router.route(project, GraphRole.CANDIDATES),
                        PROJECT,
                        candidate,
                        PROJECT,
                        PROJECT,
                        PROJECT,
                        router.route(project, GraphRole.SOURCES),
                        PROJECT));
        seedLegacyV02Source(gateway, router, project, "1");

        var validation = new RemoteCandidateValidationService(gateway, router, Path.of("/ontology/shapes"));
        assertTrue(validation.conforms(project, "remote-candidate"));
        var service = new FusekiLifecycleService(gateway, router, validation);
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
    void rejectsMalformedLegacyVersionWithoutEvidenceFields() {
        var endpoint = System.getenv("FUSEKI_BASE_URL");
        Assumptions.assumeTrue(
                endpoint != null && !endpoint.isBlank(), "remote Fuseki is only required in the system suite");
        var router = new GraphIriRouter();
        var project = new ProjectId(PROJECT);
        var gateway = new FusekiGateway(HttpClient.newHttpClient(), URI.create(endpoint));
        seedCandidate(gateway, router, project, "malformed-version", "0.2.invalid", true);

        var validation = new RemoteCandidateValidationService(gateway, router, Path.of("/ontology/shapes"));
        var result = validation.validate(project, "malformed-version");

        assertFalse(result.conforms());
        assertTrue(result.violations().stream()
                .anyMatch(violation -> violation.message().contains("rawText")
                        || violation.message().contains("evidence")));
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
        var suffix = UUID.randomUUID().toString().substring(0, 8);
        var candidateId = "http-candidate-" + suffix;
        var confirmationKey = "http-confirm-" + suffix;
        seedCandidate(
                new FusekiGateway(HttpClient.newHttpClient(), URI.create(endpoint)), router, project, candidateId);
        var request = HttpRequest.newBuilder(URI.create(coreUrl + "/v1/candidates/" + candidateId + "/confirmations"))
                .header("Content-Type", "application/json")
                .header("Idempotency-Key", confirmationKey)
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
        seedCandidate(gateway, router, project, id, "0.2.0", false);
    }

    private static void seedCandidate(
            FusekiGateway gateway,
            GraphIriRouter router,
            ProjectId project,
            String id,
            String version,
            boolean legacySource) {
        var candidate = "https://w3id.org/projecta/data/project/" + PROJECT + "/candidate/" + id;
        gateway.update("""
                INSERT DATA { GRAPH <%s> { <https://w3id.org/projecta/data/project/%s> a <https://w3id.org/projecta/ontology/Project> . <%s> a <https://w3id.org/projecta/ontology/Candidate> ; <https://w3id.org/projecta/ontology/candidateStatus> <https://w3id.org/projecta/ontology/validated> ; <http://www.w3.org/ns/prov#wasDerivedFrom> <https://w3id.org/projecta/data/project/%s/note-item/source-%s> ; <http://www.w3.org/ns/prov#wasGeneratedBy> <https://w3id.org/projecta/data/project/%s/activity/extract-%s> ; <http://www.w3.org/ns/prov#generatedAtTime> "2026-07-29T10:00:00Z"^^<http://www.w3.org/2001/XMLSchema#dateTime> ; <https://w3id.org/projecta/ontology/generator> "test-generator" ; <https://w3id.org/projecta/ontology/proposedOntologyVersion> "%s" ; <https://w3id.org/projecta/ontology/belongsToProject> <https://w3id.org/projecta/data/project/%s> . } GRAPH <%s> { <https://w3id.org/projecta/data/project/%s/note-item/source-%s> <https://w3id.org/projecta/ontology/hasItemType> <https://w3id.org/projecta/ontology/requirement> . } }
                """.formatted(
                        router.route(project, GraphRole.CANDIDATES),
                        PROJECT,
                        candidate,
                        PROJECT,
                        id,
                        PROJECT,
                        id,
                        version,
                        PROJECT,
                        router.route(project, GraphRole.SOURCES),
                        PROJECT,
                        id));
        if (legacySource) {
            seedLegacyV02Source(gateway, router, project, id);
        } else {
            seedSource(gateway, router, project, id);
        }
    }

    private static void seedSource(FusekiGateway gateway, GraphIriRouter router, ProjectId project, String id) {
        gateway.update("""
                INSERT DATA { GRAPH <%s> {
                  <https://w3id.org/projecta/data/project/%s> a <https://w3id.org/projecta/ontology/Project> .
                  <https://w3id.org/projecta/data/project/%s/person/le> a <https://w3id.org/projecta/ontology/Person> .
                  <https://w3id.org/projecta/data/project/%s/note/source-%s>
                    a <https://w3id.org/projecta/ontology/Note> ;
                    <https://w3id.org/projecta/ontology/rawText> "A" ;
                    <https://w3id.org/projecta/ontology/name> "Seed note" ;
                    <https://w3id.org/projecta/ontology/belongsToProject>
                      <https://w3id.org/projecta/data/project/%s> ;
                    <https://w3id.org/projecta/ontology/authoredBy>
                      <https://w3id.org/projecta/data/project/%s/person/le> ;
                    <https://w3id.org/projecta/ontology/recordedAt>
                      "2026-07-29T10:00:00Z"^^<http://www.w3.org/2001/XMLSchema#dateTime> .
                  <https://w3id.org/projecta/data/project/%s/note-item/source-%s>
                    a <https://w3id.org/projecta/ontology/NoteItem> ;
                    <https://w3id.org/projecta/ontology/isItemOf>
                      <https://w3id.org/projecta/data/project/%s/note/source-%s> ;
                    <https://w3id.org/projecta/ontology/hasItemType>
                      <https://w3id.org/projecta/ontology/requirement> ;
                    <https://w3id.org/projecta/ontology/contentText> "A" ;
                    <https://w3id.org/projecta/ontology/evidenceStartOffset>
                      "0"^^<http://www.w3.org/2001/XMLSchema#nonNegativeInteger> ;
                    <https://w3id.org/projecta/ontology/evidenceEndOffset>
                      "1"^^<http://www.w3.org/2001/XMLSchema#positiveInteger> .
                } }
                """.formatted(
                        router.route(project, GraphRole.SOURCES),
                        PROJECT,
                        PROJECT,
                        PROJECT,
                        id,
                        PROJECT,
                        PROJECT,
                        PROJECT,
                        id,
                        PROJECT,
                        id));
    }

    private static void seedLegacyV02Source(
            FusekiGateway gateway, GraphIriRouter router, ProjectId project, String id) {
        gateway.update("""
                INSERT DATA { GRAPH <%s> {
                  <https://w3id.org/projecta/data/project/%s> a <https://w3id.org/projecta/ontology/Project> .
                  <https://w3id.org/projecta/data/project/%s/person/le> a <https://w3id.org/projecta/ontology/Person> .
                  <https://w3id.org/projecta/data/project/%s/note/source-%s>
                    a <https://w3id.org/projecta/ontology/Note> ;
                    <https://w3id.org/projecta/ontology/name> "Legacy v0.2 note" ;
                    <https://w3id.org/projecta/ontology/belongsToProject>
                      <https://w3id.org/projecta/data/project/%s> ;
                    <https://w3id.org/projecta/ontology/authoredBy>
                      <https://w3id.org/projecta/data/project/%s/person/le> ;
                    <https://w3id.org/projecta/ontology/recordedAt>
                      "2026-07-29T10:00:00Z"^^<http://www.w3.org/2001/XMLSchema#dateTime> .
                  <https://w3id.org/projecta/data/project/%s/note-item/source-%s>
                    a <https://w3id.org/projecta/ontology/NoteItem> ;
                    <https://w3id.org/projecta/ontology/isItemOf>
                      <https://w3id.org/projecta/data/project/%s/note/source-%s> ;
                    <https://w3id.org/projecta/ontology/hasItemType>
                      <https://w3id.org/projecta/ontology/requirement> ;
                    <https://w3id.org/projecta/ontology/contentText> "Legacy requirement" .
                } }
                """.formatted(
                        router.route(project, GraphRole.SOURCES),
                        PROJECT,
                        PROJECT,
                        PROJECT,
                        id,
                        PROJECT,
                        PROJECT,
                        PROJECT,
                        id,
                        PROJECT,
                        id));
    }

    private static FusekiLifecycleService lifecycle(FusekiGateway gateway, GraphIriRouter router) {
        return new FusekiLifecycleService(
                gateway, router, new RemoteCandidateValidationService(gateway, router, Path.of("/ontology/shapes")));
    }
}
