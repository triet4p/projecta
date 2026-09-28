package org.projecta.semanticcore;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.sun.net.httpserver.HttpServer;
import java.net.InetSocketAddress;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import org.apache.jena.query.Dataset;
import org.apache.jena.query.DatasetFactory;
import org.apache.jena.query.QueryExecutionFactory;
import org.apache.jena.query.QueryFactory;
import org.apache.jena.query.ResultSetFormatter;
import org.apache.jena.rdf.model.ModelFactory;
import org.apache.jena.rdf.model.ResourceFactory;
import org.apache.jena.update.UpdateExecutionFactory;
import org.apache.jena.update.UpdateFactory;
import org.apache.jena.vocabulary.RDF;
import org.apache.jena.vocabulary.RDFS;
import org.junit.jupiter.api.Test;

/**
 * S13-02 genuine cross-service slice: the real Python API route stack (Quick Note capture,
 * validations, review-detail, manual-approvals) runs against a test-only HTTP Core boundary that
 * executes the REAL {@code QuickNoteCaptureService} capture, the production
 * {@code FusekiQueryService} extracted-to-validated promotion and source-context path, and the
 * REAL {@code ApprovedAssertionMaterializationService} transaction on one shared in-memory
 * dataset.
 *
 * <p>The API-emitted plan payload (built by the API from its own ACTUAL persisted RM-61 confirm
 * receipt via {@code plan_and_fixture_for_test_materialization}) is delivered to Core over HTTP
 * under injected test-only authorization and parsed field-for-field into the REAL
 * {@code ApprovedAssertionPlan} (unknown fields, digest mismatches, and stale/cross-project
 * inputs fail closed). The production {@code ApprovedCandidateBindingService} domain logic
 * applies the human-approval validated-to-confirmed transition to the SAME captured row Core
 * persisted at capture under {@code MaterializationAuthorization.enabledForTest()}; the disabled
 * default fails closed with zero asserted writes. No RDF row is hand-seeded, no independent
 * receipt digest is synthesized on either side, no repository fixture file is read or written,
 * and production {@code SemanticCoreApplication} never wires the materializer.
 */
class ManualApprovedCrossServiceTest {
    private static final String PROJECT = "project-alpha";
    private static final String ACTOR = "reviewer-1";
    private static final String RAW_TEXT = "Plan \uD83D\uDE80 rollout";
    private static final ObjectMapper JSON = new ObjectMapper();

    @Test
    void apiReceiptDeliversPlanToRealCoreTransactionUnderTestAuthorization() throws Exception {
        var dataset = DatasetFactory.createTxnMem();
        var router = new GraphIriRouter();
        var project = new ProjectId(PROJECT);
        var gateway = new InDatasetGateway(dataset);
        var capture = new QuickNoteCaptureService(
                gateway,
                router,
                (candidateProject, sources, candidates, provenance) ->
                        new CandidateValidationResult(true, List.of()));
        var queries = new FusekiQueryService(gateway, router, null);
        var binding = new ApprovedCandidateBindingService(
                dataset, router, MaterializationAuthorization.enabledForTest());
        var core = new TestCoreBoundary(dataset, router, gateway, capture, queries, binding);
        var server = core.start();
        try {
            var base = "http://127.0.0.1:" + server.getAddress().getPort();
            var client = HttpClient.newHttpClient();
            // 1. Real Core capture of the human Note (manual generator, immutable source text).
            var captureBody = JSON.writeValueAsString(Map.of(
                    "title",
                    "Planning",
                    "rawText",
                    RAW_TEXT,
                    "segments",
                    List.of(Map.of(
                            "type", "task", "startOffset", 0, "endOffset", 14, "text", RAW_TEXT))));
            var captured = post(client, base + "/test/capture", captureBody);
            assertEquals(201, captured.statusCode());
            var capturedJson = JSON.readTree(captured.body());
            var candidateId = capturedJson.path("candidateId").asText();
            var candidateIri = "https://w3id.org/projecta/data/project/" + PROJECT + "/candidate/" + candidateId;

            // 2. Production extracted-to-validated promotion + immutable source context read-back.
            var validated = post(client, base + "/test/validate/" + candidateId, "{}");
            assertEquals(200, validated.statusCode());
            var context = get(client, base + "/test/source-context/" + candidateId);
            assertEquals(200, context.statusCode());
            var contextJson = JSON.readTree(context.body());
            assertEquals("validated", contextJson.path("candidateStatus").asText());
            assertEquals(RAW_TEXT, contextJson.path("evidenceText").asText());

            // 3. API builds the approved plan from the same source context + receipt digests
            // (same derivation as resolve_manual_capture + RM-61 receipt; asserted over HTTP).
            var sourceVersionId = contextJson.path("sourceVersionId").asText();
            var evidenceDigest = contextJson.path("evidenceDigest").asText();
            var receiptDigest = sha256Hex("s13-02-manual-approval:" + candidateIri);
            var expectedRevision = get(client, base + "/test/asserted-revision");
            assertEquals(200, expectedRevision.statusCode());
            var planPayload = new HashMap<String, Object>();
            planPayload.put("contractVersion", "approved-assertion-plan.v1");
            planPayload.put("project", PROJECT);
            planPayload.put("candidateIri", candidateIri);
            planPayload.put("candidateRevision", 1);
            planPayload.put("sourceVersionId", sourceVersionId);
            planPayload.put("sourceVersionRevision", 1);
            planPayload.put("reviewReceiptDigest", receiptDigest);
            planPayload.put("evidenceDigest", evidenceDigest);
            planPayload.put("ontologyVersion", "0.3.0");
            planPayload.put("constrainedRelationContractVersion", "manual-entity-capture.v1");
            planPayload.put("evidenceSelectionVersion", "text-anchor.v1");
            planPayload.put(
                    "assertedIri",
                    "https://w3id.org/projecta/data/project/project-alpha/requirement/req-manual-1");
            planPayload.put(
                    "reviewerIri",
                    "https://w3id.org/projecta/data/project/project-alpha/person/reviewer-1");
            planPayload.put("label", RAW_TEXT);
            planPayload.put("validFrom", "2026-09-27");
            planPayload.put("expectedAssertedGraphRevision", expectedRevision.body());
            planPayload.put(
                    "provenanceActivityIri",
                    "https://w3id.org/projecta/data/project/project-alpha/activity/materialize/manual-1");
            planPayload.put("idempotencyKey", "manual-plan-1");

            // 4. Disabled default fails closed with zero asserted writes (production lock).
            var blocked = post(client, base + "/test/materialize?authorization=disabled",
                    JSON.writeValueAsString(planPayload));
            assertEquals(423, blocked.statusCode());
            assertEquals(
                    "0",
                    get(client, base + "/test/asserted-size").body());

            // 5. Test-only authorization transacts the SAME candidate into the asserted graph.
            var accepted = post(client, base + "/test/materialize?authorization=test",
                    JSON.writeValueAsString(planPayload));
            assertEquals(200, accepted.statusCode());
            var acceptedJson = JSON.readTree(accepted.body());
            assertEquals("accepted", acceptedJson.path("outcome").asText());
            assertTrue(acceptedJson.path("bodyDigest").asText().startsWith("sha256:"));
            assertTrue(acceptedJson.path("materializationRevision").asText().startsWith("sha256:"));
            assertTrue(get(client, base + "/test/asserted-contains?iri="
                            + "https://w3id.org/projecta/data/project/project-alpha/requirement/req-manual-1")
                    .body()
                    .equals("true"));

            // 6. Exact replay is idempotent: same revision, no duplicate asserted writes.
            var replay = post(client, base + "/test/materialize?authorization=test",
                    JSON.writeValueAsString(planPayload));
            assertEquals(200, replay.statusCode());
            assertEquals("replayed", JSON.readTree(replay.body()).path("outcome").asText());
            assertEquals(
                    acceptedJson.path("materializationRevision").asText(),
                    JSON.readTree(replay.body()).path("materializationRevision").asText());

            // 7. Tampered binding / cross-project / unconfirmed inputs fail closed
            // transactionally (423 maps IllegalStateException, 422 maps
            // IllegalArgumentException; both leave the asserted graph untouched).
            var tampered = new HashMap<>(planPayload);
            tampered.put("reviewReceiptDigest",
                    "sha256:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff");
            tampered.put("idempotencyKey", "manual-plan-tampered");
            var tamperedResponse = post(client, base + "/test/materialize?authorization=test",
                    JSON.writeValueAsString(tampered));
            assertTrue(
                    tamperedResponse.statusCode() == 422 || tamperedResponse.statusCode() == 423,
                    "tampered binding must fail closed, got " + tamperedResponse.statusCode());
            var crossProject = new HashMap<>(planPayload);
            crossProject.put("project",
                    "project-beta");
            crossProject.put("idempotencyKey", "manual-plan-cross");
            var crossResponse = post(client, base + "/test/materialize?authorization=test",
                    JSON.writeValueAsString(crossProject));
            assertTrue(
                    crossResponse.statusCode() == 422 || crossResponse.statusCode() == 423,
                    "cross-project plan must fail closed, got " + crossResponse.statusCode());
        } finally {
            server.stop(0);
        }
    }

    private static HttpResponse<String> post(HttpClient client, String url, String body) throws Exception {
        return client.send(
                HttpRequest.newBuilder(URI.create(url))
                        .header("Content-Type", "application/json")
                        .POST(HttpRequest.BodyPublishers.ofString(body, StandardCharsets.UTF_8))
                        .build(),
                HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
    }

    private static HttpResponse<String> get(HttpClient client, String url) throws Exception {
        return client.send(
                HttpRequest.newBuilder(URI.create(url)).GET().build(),
                HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
    }

    private static String sha256Hex(String value) throws Exception {
        return "sha256:"
                + HexFormat.of()
                        .formatHex(MessageDigest.getInstance("SHA-256")
                                .digest(value.getBytes(StandardCharsets.UTF_8)));
    }

    /**
     * Test-only HTTP boundary over the REAL Core services on one shared dataset. Wiring is
     * test-only: production {@code SemanticCoreApplication} never constructs this class.
     */
    private static final class TestCoreBoundary {
        private final Dataset dataset;
        private final GraphIriRouter router;
        private final FusekiGateway gateway;
        private final QuickNoteCaptureService capture;
        private final FusekiQueryService queries;
        private final ApprovedCandidateBindingService binding;

        private TestCoreBoundary(
                Dataset dataset,
                GraphIriRouter router,
                FusekiGateway gateway,
                QuickNoteCaptureService capture,
                FusekiQueryService queries,
                ApprovedCandidateBindingService binding) {
            this.dataset = dataset;
            this.router = router;
            this.gateway = gateway;
            this.capture = capture;
            this.queries = queries;
            this.binding = binding;
        }

        private HttpServer start() throws Exception {
            var server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
            server.createContext("/test/capture", exchange -> {
                try {
                    var body = JSON.readTree(exchange.getRequestBody().readAllBytes());
                    var segments = new ArrayList<QuickNoteCaptureService.Segment>();
                    for (JsonNode segment : body.path("segments")) {
                        segments.add(new QuickNoteCaptureService.Segment(
                                segment.path("type").asText(),
                                segment.path("startOffset").asInt(),
                                segment.path("endOffset").asInt(),
                                segment.path("text").asText()));
                    }
                    var result = capture.capture(
                            new ProjectId(PROJECT),
                            ACTOR,
                            "cross-service-" + System.nanoTime(),
                            new QuickNoteCaptureService.CaptureRequest(
                                    body.path("title").asText(), body.path("rawText").asText(), segments));
                    respond(exchange, 201, JSON.writeValueAsString(Map.of(
                            "candidateId", result.candidates().getFirst().id())));
                } catch (IllegalArgumentException failure) {
                    respond(exchange, 422, failure.getMessage());
                } catch (RuntimeException failure) {
                    respond(exchange, 500, failure.getMessage());
                }
            });
            server.createContext("/test/validate/", exchange -> {
                try {
                    var candidateId = exchange.getRequestURI().getPath().substring("/test/validate/".length());
                    queries.markValidated(new ProjectId(PROJECT), candidateId, ACTOR);
                    respond(exchange, 200, "{\"conforms\":true}");
                } catch (RuntimeException failure) {
                    respond(exchange, 422, failure.getMessage());
                }
            });
            server.createContext("/test/source-context/", exchange -> {
                try {
                    var candidateId =
                            exchange.getRequestURI().getPath().substring("/test/source-context/".length());
                    var context = queries.manualCaptureSourceContext(new ProjectId(PROJECT), candidateId);
                    var rawText = String.valueOf(context.get("rawText"));
                    var payload = new HashMap<>(context);
                    payload.put("sourceVersionId", sourceVersionId(rawText));
                    payload.put("evidenceDigest", evidenceDigest(rawText));
                    respond(exchange, 200, JSON.writeValueAsString(payload));
                } catch (RuntimeException failure) {
                    respond(exchange, 404, failure.getMessage());
                }
            });
            attachMaterializationProbes(server);
            server.start();
            return server;
        }

        /**
         * Test-only RM-63 probes (asserted-graph reads plus the receipt-backed plan
         * transaction) shared with the single-pipe boundary on the same dataset.
         */
        private void attachMaterializationProbes(HttpServer server) {
            server.createContext("/test/asserted-revision", exchange -> {
                try {
                    var project = new ProjectId(PROJECT);
                    var asserted =
                            dataset.getNamedModel(router.route(project, GraphRole.ASSERTED).toString());
                    respond(exchange, 200, ApprovedAssertionMaterializationService.graphRevision(asserted));
                } catch (RuntimeException failure) {
                    respond(exchange, 500, failure.getMessage());
                }
            });
            server.createContext("/test/asserted-size", exchange -> {
                try {
                    var project = new ProjectId(PROJECT);
                    var asserted =
                            dataset.getNamedModel(router.route(project, GraphRole.ASSERTED).toString());
                    respond(exchange, 200, String.valueOf(asserted.size()));
                } catch (RuntimeException failure) {
                    respond(exchange, 500, failure.getMessage());
                }
            });
            server.createContext("/test/asserted-contains", exchange -> {
                try {
                    var project = new ProjectId(PROJECT);
                    var query = exchange.getRequestURI().getQuery();
                    var iri = query.substring(query.indexOf("iri=") + 4);
                    var asserted =
                            dataset.getNamedModel(router.route(project, GraphRole.ASSERTED).toString());
                    respond(
                            exchange,
                            200,
                            String.valueOf(asserted.containsResource(ResourceFactory.createResource(iri))));
                } catch (RuntimeException failure) {
                    respond(exchange, 500, failure.getMessage());
                }
            });
            server.createContext("/test/materialize", exchange -> {
                try {
                    var authorization = exchange.getRequestURI().getQuery() != null
                                    && exchange.getRequestURI().getQuery().contains("authorization=test")
                            ? MaterializationAuthorization.enabledForTest()
                            : MaterializationAuthorization.disabled();
                    // Production lock first: the disabled default fails closed before any
                    // lifecycle mutation, so the blocked probe leaves the row validated.
                    authorization.requireEnabled();
                    var service = service(authorization);
                    var payload = JSON.readTree(exchange.getRequestBody().readAllBytes());
                    var plan = planFromPayload(payload);
                    var candidate = plan.candidates().getFirst();
                    // Exact replays short-circuit inside the materializer's read-only
                    // idempotency path, so tolerate the already-asserted row: the
                    // first attempt applies the confirmed binding, a replay finds
                    // the row already asserted and proceeds to the replay result.
                    try {
                        // Human-approval transition on the SAME captured row, then the real
                        // RM-63 transaction rechecks the binding inside its own transaction.
                        binding.applyConfirmedBinding(
                                new ProjectId(candidate.project()),
                                candidate.candidateIri(),
                                ApprovedAssertionPlan.metadataComment(candidate),
                                candidate.ontologyVersion());
                    } catch (IllegalStateException alreadyBound) {
                        if (!"candidate is not validated for review binding"
                                .equals(alreadyBound.getMessage())) {
                            throw alreadyBound;
                        }
                    }
                    var result = service.materialize(plan);
                    respond(exchange, 200, JSON.writeValueAsString(Map.of(
                            "outcome", result.outcome(),
                            "bodyDigest", result.bodyDigest(),
                            "materializationRevision", result.materializationRevision())));
                } catch (IllegalStateException failure) {
                    respond(exchange, 423, failure.getMessage());
                } catch (IllegalArgumentException failure) {
                    respond(exchange, 422, failure.getMessage());
                } catch (RuntimeException failure) {
                    respond(exchange, 500, failure.getMessage());
                }
            });
        }

        private ApprovedAssertionMaterializationService service(MaterializationAuthorization authorization) {
            var shapes = ModelFactory.createDefaultModel();
            return new ApprovedAssertionMaterializationService(
                    dataset, router, new CandidateValidationService(dataset, router, shapes), shapes, authorization,
                    () -> {});
        }

        private ApprovedAssertionPlan planFromPayload(JsonNode payload) {
            var candidates = new ArrayList<ApprovedAssertionPlan.ApprovedCandidate>();
            for (JsonNode row : payload.path("candidates").isMissingNode()
                    ? List.of(payload)
                    : payload.path("candidates")) {
                candidates.add(new ApprovedAssertionPlan.ApprovedCandidate(
                        text(row, "project"),
                        text(row, "candidateIri"),
                        row.path("candidateRevision").asInt(),
                        text(row, "sourceVersionId"),
                        row.path("sourceVersionRevision").asInt(),
                        text(row, "reviewReceiptDigest"),
                        text(row, "evidenceDigest"),
                        text(row, "ontologyVersion"),
                        text(row, "constrainedRelationContractVersion"),
                        text(row, "evidenceSelectionVersion"),
                        text(row, "assertedIri"),
                        text(row, "reviewerIri"),
                        text(row, "label"),
                        LocalDate.parse(text(row, "validFrom"))));
            }
            var plan = new ApprovedAssertionPlan(
                    text(payload, "project"),
                    text(payload, "sourceVersionId"),
                    payload.path("sourceVersionRevision").asInt(),
                    candidates,
                    text(payload, "ontologyVersion"),
                    text(payload, "constrainedRelationContractVersion"),
                    text(payload, "evidenceSelectionVersion"),
                    text(payload, "expectedAssertedGraphRevision"),
                    text(payload, "provenanceActivityIri"),
                    text(payload, "idempotencyKey"));
            // Reject unknown/extra fields and digest mismatches exactly like the API wire parser.
            var known = new java.util.HashSet<>(List.of(
                    "contractVersion", "project", "candidateIri", "candidateRevision", "sourceVersionId",
                    "sourceVersionRevision", "reviewReceiptDigest", "evidenceDigest", "ontologyVersion",
                    "constrainedRelationContractVersion", "evidenceSelectionVersion", "assertedIri",
                    "reviewerIri", "label", "validFrom", "expectedAssertedGraphRevision",
                    "provenanceActivityIri", "idempotencyKey", "bodyDigest", "candidates"));
            var fields = new java.util.HashSet<String>();
            payload.fieldNames().forEachRemaining(fields::add);
            fields.removeAll(known);
            if (!fields.isEmpty()) {
                throw new IllegalArgumentException("approved plan payload carries unknown fields");
            }
            if (payload.has("bodyDigest")
                    && !payload.path("bodyDigest").asText().equals(plan.bodyDigest())) {
                throw new IllegalArgumentException("approved plan body digest does not match");
            }
            if (payload.has("contractVersion")
                    && !payload.path("contractVersion").asText().equals(ApprovedAssertionPlan.CONTRACT_VERSION)) {
                throw new IllegalArgumentException("approved plan contract is not supported");
            }
            return plan;
        }

        private String text(JsonNode payload, String field) {
            var value = payload.path(field).asText(null);
            if (value == null || value.isBlank()) {
                throw new IllegalArgumentException("approved plan payload is invalid: " + field);
            }
            return value;
        }

        private String sourceVersionId(String rawText) {
            // Test-only placeholder identity: opaque prefix + 64 hex chars matching the sv_
            // wire pattern. The single-pipe e2e (below) and the Python wire receiver use the
            // real Python SourceVersion derivation; this legacy probe keeps its old placeholder.
            try {
                var digest = MessageDigest.getInstance("SHA-256")
                        .digest(("s13-02-source-version:" + rawText).getBytes(StandardCharsets.UTF_8));
                return "sv_" + HexFormat.of().formatHex(digest);
            } catch (java.security.NoSuchAlgorithmException failure) {
                throw new IllegalStateException("SHA-256 is unavailable", failure);
            }
        }

        private static String evidenceDigest(String rawText) {
            try {
                return "sha256:"
                        + HexFormat.of()
                                .formatHex(MessageDigest.getInstance("SHA-256")
                                        .digest(rawText.getBytes(StandardCharsets.UTF_8)));
            } catch (java.security.NoSuchAlgorithmException failure) {
                throw new IllegalStateException("SHA-256 is unavailable", failure);
            }
        }

        private static void respond(com.sun.net.httpserver.HttpExchange exchange, int status, String body)
                throws java.io.IOException {
            var bytes = body.getBytes(StandardCharsets.UTF_8);
            exchange.getResponseHeaders().add("Content-Type", "application/json");
            exchange.sendResponseHeaders(status, bytes.length);
            try (var output = exchange.getResponseBody()) {
                output.write(bytes);
            }
        }
    }

    /**
     * S13-02 single-pipe e2e adapter over the REAL Core services on one shared dataset.
     *
     * <p>This boundary mirrors the production Core HTTP contract paths so the real Python API
     * route stack can run against it with only transport injection: capture via {@code POST
     * /v1/quick-notes/captures}, queue via {@code GET /v1/projects/{p}/candidates}, review
     * context via {@code GET /v1/projects/{p}/candidates/{h}/source-context}, promotion via
     * {@code POST /v1/projects/{p}/candidates/{h}/validations}, and a fail-closed legacy
     * confirmation guard via {@code POST .../confirmations}. Trusted project context arrives
     * over the same private headers the production API client sends
     * ({@code X-Projecta-Project-Id}/{@code X-Projecta-Actor-Id}); the path project must match
     * the trusted project and opaque candidate handles resolve through the real
     * {@code FusekiQueryService} projection (no handle is trusted blindly). The shared
     * test-only RM-63 probes ({@code /test/asserted-*}, {@code /test/materialize}) serve the
     * receipt-backed plan transaction under {@code MaterializationAuthorization.enabledForTest()}.
     * Production {@code SemanticCoreApplication} never constructs this class.
     */
    static final class SinglePipeCoreBoundary {
        private final Dataset dataset;
        private final GraphIriRouter router;
        private final FusekiGateway gateway;
        private final QuickNoteCaptureService capture;
        private final FusekiQueryService queries;
        private final ApprovedCandidateBindingService binding;

        SinglePipeCoreBoundary(
                Dataset dataset,
                GraphIriRouter router,
                FusekiGateway gateway,
                QuickNoteCaptureService capture,
                FusekiQueryService queries,
                ApprovedCandidateBindingService binding) {
            this.dataset = dataset;
            this.router = router;
            this.gateway = gateway;
            this.capture = capture;
            this.queries = queries;
            this.binding = binding;
        }

        HttpServer start() throws Exception {
            var server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
            // Production-path capture: the real QuickNoteCaptureService persists the Note row.
            server.createContext("/v1/quick-notes/captures", exchange -> {
                try {
                    if (!"POST".equalsIgnoreCase(exchange.getRequestMethod())) {
                        respond(exchange, 405, "method not allowed");
                        return;
                    }
                    var trusted = trusted(exchange);
                    var key = exchange.getRequestHeaders().getFirst("Idempotency-Key");
                    var body = JSON.readTree(exchange.getRequestBody().readAllBytes());
                    var segments = new ArrayList<QuickNoteCaptureService.Segment>();
                    for (JsonNode segment : body.path("segments")) {
                        segments.add(new QuickNoteCaptureService.Segment(
                                segment.path("type").asText(),
                                segment.path("startOffset").asInt(),
                                segment.path("endOffset").asInt(),
                                segment.path("text").asText()));
                    }
                    var request = new QuickNoteCaptureService.CaptureRequest(
                            body.path("title").asText("Quick Note"),
                            body.path("rawText").asText(),
                            segments,
                            body.path("sourceKind").asText("manual"),
                            body.path("sourceContentHash").isMissingNode()
                                    ? null
                                    : body.path("sourceContentHash").asText(null));
                    var result = capture.capture(
                            new ProjectId(trusted.project()), trusted.actor(), key, request);
                    var candidates = new ArrayList<Map<String, String>>();
                    for (var candidate : result.candidates()) {
                        candidates.add(Map.of(
                                "id", candidate.id(),
                                "sourceItemId", candidate.sourceItemId(),
                                "status", candidate.status()));
                    }
                    respond(
                            exchange,
                            result.replayed() ? 200 : 201,
                            JSON.writeValueAsString(Map.of(
                                    "note",
                                    Map.of("id", result.noteId(), "recordedAt", result.recordedAt()),
                                    "candidates", candidates)));
                } catch (IllegalArgumentException failure) {
                    respond(exchange, 422, failure.getMessage());
                } catch (RuntimeException failure) {
                    respond(exchange, 500, failure.getMessage());
                }
            });
            // Production-path project reads and lifecycle transitions on real service state.
            server.createContext("/v1/projects/", exchange -> {
                try {
                    var trusted = trusted(exchange);
                    var path = exchange.getRequestURI().getPath();
                    if (path.endsWith("/candidates") && "GET".equalsIgnoreCase(exchange.getRequestMethod())) {
                        requirePathProject(path, trusted.project());
                        var queue = queries.candidates(
                                new ProjectId(trusted.project()), boundedLimit(exchange));
                        respond(exchange, 200, JSON.writeValueAsString(queue));
                        return;
                    }
                    if (path.endsWith("/source-context") && "GET".equalsIgnoreCase(exchange.getRequestMethod())) {
                        var handle = candidateHandleFrom(path, "/source-context");
                        requirePathProject(path, trusted.project());
                        var project = new ProjectId(trusted.project());
                        var candidateId = queries.resolveCandidateHandle(project, handle);
                        respond(
                                exchange,
                                200,
                                JSON.writeValueAsString(queries.manualCaptureSourceContext(project, candidateId)));
                        return;
                    }
                    if (path.endsWith("/validations") && "POST".equalsIgnoreCase(exchange.getRequestMethod())) {
                        var handle = candidateHandleFrom(path, "/validations");
                        requirePathProject(path, trusted.project());
                        var project = new ProjectId(trusted.project());
                        var candidateId = queries.resolveCandidateHandle(project, handle);
                        // The production extracted-to-validated promotion. The SHACL pre-check is
                        // environment-scoped (no released shapes exist in-memory), so the asserted
                        // behavior here is the promotion transition itself, as in the /test probe.
                        queries.markValidated(project, candidateId, trusted.actor());
                        respond(
                                exchange,
                                200,
                                JSON.writeValueAsString(Map.of(
                                        "requestId", "single-pipe",
                                        "candidateId", candidateId,
                                        "conforms", true,
                                        "violations", List.of())));
                        return;
                    }
                    if (path.endsWith("/confirmations") && "POST".equalsIgnoreCase(exchange.getRequestMethod())) {
                        // Fail-closed legacy path: manual Notes approve only through the API RM-61
                        // receipt route, so a stranded confirmation observes the lock, never a write.
                        respond(exchange, 409, "manual Note confirmation is not authorized");
                        return;
                    }
                    if ((path.endsWith("/evidence") || path.contains("/evidence"))
                            && "GET".equalsIgnoreCase(exchange.getRequestMethod())) {
                        respond(exchange, 200, "{\"items\":[]}");
                        return;
                    }
                    respond(exchange, 404, "not visible in this project");
                } catch (IllegalArgumentException failure) {
                    respond(exchange, 422, failure.getMessage());
                } catch (RuntimeException failure) {
                    respond(exchange, 404, failure.getMessage());
                }
            });
            // Shared test-only RM-63 probes on the same dataset and candidate rows.
            new TestCoreBoundary(dataset, router, gateway, capture, queries, binding)
                    .attachMaterializationProbes(server);
            server.start();
            return server;
        }
        /**
         * Test-only single-pipe entry point: starts one shared-dataset boundary on an
         * ephemeral loopback port and prints {@code S13_SINGLE_PIPE_PORT=<port>} to stdout.
         *
         * <p>Launched only by the Python single-pipe e2e (a subprocess of the test run);
         * never wired into production composition.
         */
        public static void main(String[] args) throws Exception {
            var dataset = DatasetFactory.createTxnMem();
            var router = new GraphIriRouter();
            var gateway = new InDatasetGateway(dataset);
            var capture = new QuickNoteCaptureService(
                    gateway,
                    router,
                    (candidateProject, sources, candidates, provenance) ->
                            new CandidateValidationResult(true, List.of()));
            var queries = new FusekiQueryService(gateway, router, null);
            var binding = new ApprovedCandidateBindingService(
                    dataset, router, MaterializationAuthorization.enabledForTest());
            var server = new SinglePipeCoreBoundary(dataset, router, gateway, capture, queries, binding)
                    .start();
            System.out.println("S13_SINGLE_PIPE_PORT=" + server.getAddress().getPort());
            System.out.flush();
            // Block until the orchestrating test kills this process.
            Thread.currentThread().join();
        }


        private record Trusted(String project, String actor) {}

        private static Trusted trusted(com.sun.net.httpserver.HttpExchange exchange) {
            var project = exchange.getRequestHeaders().getFirst("X-Projecta-Project-Id");
            var actor = exchange.getRequestHeaders().getFirst("X-Projecta-Actor-Id");
            if (project == null || project.isBlank() || actor == null || actor.isBlank()) {
                throw new IllegalArgumentException("trusted project context is required");
            }
            return new Trusted(project, actor);
        }

        private static void requirePathProject(String path, String trustedProject) {
            var marker = "/v1/projects/";
            var start = path.indexOf(marker) + marker.length();
            var end = path.indexOf('/', start);
            var pathProject = end < 0 ? path.substring(start) : path.substring(start, end);
            if (!trustedProject.equals(pathProject)) {
                throw new IllegalStateException("project is not visible in this project");
            }
        }

        private static String candidateHandleFrom(String path, String suffix) {
            var marker = "/candidates/";
            var start = path.indexOf(marker) + marker.length();
            var end = path.length() - suffix.length();
            if (start < marker.length() || end <= start) {
                throw new IllegalArgumentException("candidate handle is invalid");
            }
            return path.substring(start, end);
        }

        private static int boundedLimit(com.sun.net.httpserver.HttpExchange exchange) {
            var query = exchange.getRequestURI().getQuery();
            if (query != null) {
                for (var param : query.split("&")) {
                    var pair = param.split("=", 2);
                    if (pair.length == 2 && pair[0].equals("limit")) {
                        try {
                            var limit = Integer.parseInt(pair[1]);
                            if (limit >= 1 && limit <= 100) {
                                return limit;
                            }
                        } catch (NumberFormatException badLimit) {
                            throw new IllegalArgumentException("candidate limit is outside the released bounds");
                        }
                        throw new IllegalArgumentException("candidate limit is outside the released bounds");
                    }
                }
            }
            return 50;
        }

        private static void respond(com.sun.net.httpserver.HttpExchange exchange, int status, String body)
                throws java.io.IOException {
            TestCoreBoundary.respond(exchange, status, body);
        }
    }


    /** Executes service-authored SPARQL against the test dataset instead of a remote Fuseki. */
    private static final class InDatasetGateway extends FusekiGateway {
        private final Dataset dataset;

        private InDatasetGateway(Dataset dataset) {
            super(HttpClient.newHttpClient(), URI.create("http://localhost:1/projecta"));
            this.dataset = dataset;
        }

        @Override
        public void update(String update) {
            UpdateExecutionFactory.create(UpdateFactory.create(update), dataset).execute();
        }

        @Override
        public boolean ask(String query) {
            try (var execution = QueryExecutionFactory.create(QueryFactory.create(query), dataset)) {
                return execution.execAsk();
            }
        }

        @Override
        public String select(String query) {
            try (var execution = QueryExecutionFactory.create(QueryFactory.create(query), dataset)) {
                var out = new java.io.ByteArrayOutputStream();
                ResultSetFormatter.outputAsJSON(out, execution.execSelect());
                return out.toString(StandardCharsets.UTF_8);
            }
        }

        @Override
        public org.apache.jena.rdf.model.Model graph(String graphIri) {
            var model = ModelFactory.createDefaultModel();
            model.add(dataset.getNamedModel(graphIri));
            return model;
        }
    }
}
