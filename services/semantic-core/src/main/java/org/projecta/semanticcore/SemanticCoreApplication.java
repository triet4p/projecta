package org.projecta.semanticcore;

import io.javalin.Javalin;
import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.net.http.HttpClient;
import java.nio.charset.StandardCharsets;
import java.time.LocalDate;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.logging.Level;
import java.util.logging.Logger;

/**
 * Semantic Core composition root.
 *
 * <p>HTTP endpoints are introduced only by their corresponding Sprint 3 tasks. This temporary
 * server lifecycle is the container smoke-test baseline; S3-10 adds validated configuration and
 * health endpoints.
 */
public final class SemanticCoreApplication {
    private static final Logger LOGGER = Logger.getLogger(SemanticCoreApplication.class.getName());

    private SemanticCoreApplication() {}

    /** Starts the HTTP boundary after composing the Fuseki-backed runtime dependencies. */
    public static void main(String[] args) {
        var configuration = SemanticCoreConfiguration.fromEnvironment(System.getenv());
        var readiness = new FusekiReadiness(HttpClient.newHttpClient(), configuration);
        var gateway = new FusekiGateway(HttpClient.newHttpClient(), configuration.fusekiDatasetUrl());
        var router = new GraphIriRouter();
        var validation = new RemoteCandidateValidationService(gateway, router, configuration.shapesDirectory());
        var lifecycle = new FusekiLifecycleService(gateway, router, validation);
        var capture = new QuickNoteCaptureService(gateway, router, validation::validateCapture);
        var extraction = new LlmCandidateIngestionService(gateway, router, validation);
        var queries = new FusekiQueryService(gateway, router, validation);
        var m4 = new M4SemanticService(gateway, router, new M4QueryTemplateRegistry());
        var workspace = new ProjectWorkspaceQueryService(gateway, router);
        var portableExport = new PortableProjectExportService(gateway, router);
        var portableImport = new PortableProjectImportService(gateway, router, validation);
        var projectDelete = new ProjectDataDeleteService(gateway, router);
        var application = Javalin.create(config -> {
            config.routes.before(context ->
                    gateway.setCorrelation(context.header("X-Request-Id"), context.header("X-Operation-Id")));
            config.routes.before(OperationEventLogger::started);
            config.routes.after(OperationEventLogger::completed);
            config.routes.exception(RuntimeException.class, (exception, context) -> writeProblem(context, exception));
            config.routes
                    .get("/health/live", context -> context.status(200).json(new HealthResponse("live")))
                    .get("/health/ready", context -> {
                        if (readiness.isReady()) {
                            context.status(200).json(new HealthResponse("ready"));
                        } else {
                            context.status(503).json(new HealthResponse("not-ready"));
                        }
                    })
                    .get("/v1/projects/catalog", context -> {
                        trustedActorContext(context);
                        var rawProjects = context.header("X-Projecta-Visible-Projects");
                        if (rawProjects == null || rawProjects.isBlank()) {
                            throw new IllegalArgumentException("visible project catalog is not configured");
                        }
                        var projects = Arrays.stream(rawProjects.split(",", -1))
                                .map(String::trim)
                                .filter(value -> !value.isBlank())
                                .map(ProjectId::new)
                                .distinct()
                                .toList();
                        var limit = boundedLimit(context.queryParam("limit"));
                        var result = workspace.catalog(projects, limit);
                        context.json(Map.of(
                                "requestId", requestId(context),
                                "catalogRevision", result.catalogRevision(),
                                "projects", result.projects()));
                    })
                    .get("/v1/projects/{projectId}/overview", context -> {
                        var trusted = trustedContext(context);
                        var requested = new ProjectId(context.pathParam("projectId"));
                        if (!requested.equals(trusted.projectId())) {
                            throw new io.javalin.http.NotFoundResponse(
                                    "project is not visible in the trusted project context");
                        }
                        var result = workspace.overview(requested, boundedLimit(context.queryParam("limit")));
                        context.json(Map.of(
                                "requestId", requestId(context),
                                "project", result.project(),
                                "currentRequirements", result.currentRequirements(),
                                "openQuestions", result.openQuestions(),
                                "tasks", result.tasks(),
                                "blockers", result.blockers(),
                                "risks", result.risks(),
                                "recentNotes", result.recentNotes(),
                                "pendingCandidates", result.pendingCandidates(),
                                "evidenceCoverage", result.evidenceCoverage()));
                    })
                    .get("/v1/projects/{projectId}/portable-export", context -> {
                        var trusted = trustedContext(context);
                        requireProjectPath(context, trusted);
                        try {
                            portableExport.writeTriG(
                                    trusted.projectId(),
                                    context.res().getOutputStream(),
                                    tripleCount -> {
                                        context.contentType("application/trig");
                                        context.header(
                                                "X-Projecta-Graph-Triple-Count", Long.toString(tripleCount));
                                        context.header(
                                                "X-Projecta-Java-Runtime",
                                                PortableProjectExportService.javaRuntimeVersion());
                                        context.header(
                                                "X-Projecta-Fuseki-Version",
                                                PortableProjectExportService.fusekiVersion());
                                        context.header(
                                                "X-Projecta-Semantic-Core-Javalin",
                                                PortableProjectExportService.javalinVersion());
                                        context.header(
                                                "X-Projecta-Semantic-Core-Jena",
                                                PortableProjectExportService.jenaVersion());
                                    });
                        } catch (PortableProjectExportService.ExportTooLargeException exception) {
                            context.status(413).json(Map.of(
                                    "code", "EXPORT_TOO_LARGE",
                                    "detail", "The selected project exceeds the supported triple limit."));
                        }
                    })
                    .post("/v1/projects/{projectId}/portable-import/validate", context -> {
                        var trusted = trustedContext(context);
                        requireProjectPath(context, trusted);
                        context.json(portableImport.validate(
                                trusted.projectId(),
                                requiredQueryParameter(context, "placeholderName"),
                                requiredQueryParameter(context, "projectName"),
                                context.bodyInputStream()));
                    })
                    .post("/v1/projects/{projectId}/portable-import/apply", context -> {
                        var trusted = trustedContext(context);
                        requireProjectPath(context, trusted);
                        context.json(portableImport.apply(
                                trusted.projectId(),
                                requiredQueryParameter(context, "placeholderName"),
                                requiredQueryParameter(context, "projectName"),
                                booleanQueryParameter(context, "adoptPlaceholder"),
                                context.bodyInputStream()));
                    })
                    .post("/v1/projects/{projectId}/portable-import/rollback", context -> {
                        var trusted = trustedContext(context);
                        requireProjectPath(context, trusted);
                        portableImport.rollback(
                                trusted.projectId(),
                                requiredQueryParameter(context, "placeholderName"),
                                requiredQueryParameter(context, "projectName"),
                                booleanQueryParameter(context, "restorePlaceholder"),
                                context.bodyInputStream());
                        context.status(204);
                    })
                    .get("/v1/projects/{projectId}/project-data/counts", context -> {
                        var trusted = trustedContext(context);
                        requireProjectPath(context, trusted);
                        context.json(projectDelete.counts(trusted.projectId()));
                    })
                    .post("/v1/projects/{projectId}/project-data/delete", context -> {
                        var trusted = trustedContext(context);
                        requireProjectPath(context, trusted);
                        context.json(projectDelete.delete(trusted.projectId()));
                    })
                    .get("/v1/projects/{projectId}/notes", context -> {
                        var trusted = trustedContext(context);
                        requireProjectPath(context, trusted);
                        context.json(queries.notes(
                                trusted.projectId(), boundedGraphLimit(context.queryParam("limit"), 1, 100, 50)));
                    })
                    .get("/v1/projects/{projectId}/notes/{noteHandle}", context -> {
                        var trusted = trustedContext(context);
                        requireProjectPath(context, trusted);
                        context.json(queries.note(trusted.projectId(), context.pathParam("noteHandle")));
                    })
                    .get("/v1/projects/{projectId}/graph", context -> {
                        var trusted = trustedContext(context);
                        requireProjectPath(context, trusted);
                        validateGraphFilters(context);
                        context.json(queries.graph(
                                trusted.projectId(),
                                boundedGraphLimit(context.queryParam("nodeLimit"), 1, 100, 50),
                                boundedGraphLimit(context.queryParam("edgeLimit"), 1, 200, 100)));
                    })
                    .get("/v1/projects/{projectId}/graph/neighborhood/{nodeHandle}", context -> {
                        var trusted = trustedContext(context);
                        requireProjectPath(context, trusted);
                        context.json(queries.neighborhood(
                                trusted.projectId(),
                                context.pathParam("nodeHandle"),
                                boundedGraphLimit(context.queryParam("edgeLimit"), 1, 100, 100)));
                    })
                    .get("/v1/projects/{projectId}/graph/nodes/{nodeHandle}", context -> {
                        var trusted = trustedContext(context);
                        requireProjectPath(context, trusted);
                        context.json(queries.nodeDetail(trusted.projectId(), context.pathParam("nodeHandle")));
                    })
                    .get("/v1/projects/{projectId}/graph/nodes/{nodeHandle}/evidence", context -> {
                        var trusted = trustedContext(context);
                        requireProjectPath(context, trusted);
                        context.json(
                                queries.graphLinks(trusted.projectId(), context.pathParam("nodeHandle"), "evidence"));
                    })
                    .get("/v1/projects/{projectId}/graph/nodes/{nodeHandle}/lifecycle", context -> {
                        var trusted = trustedContext(context);
                        requireProjectPath(context, trusted);
                        context.json(
                                queries.graphLinks(trusted.projectId(), context.pathParam("nodeHandle"), "lifecycle"));
                    })
                    .get("/v1/projects/{projectId}/candidates", context -> {
                        var trusted = trustedContext(context);
                        requireProjectPath(context, trusted);
                        context.json(queries.candidates(
                                trusted.projectId(), boundedGraphLimit(context.queryParam("limit"), 1, 100, 50)));
                    })
                    .get("/v1/projects/{projectId}/candidates/{candidateHandle}/source-context", context -> {
                        var trusted = trustedContext(context);
                        requireProjectPath(context, trusted);
                        var candidateId = queries.resolveCandidateHandle(
                                trusted.projectId(), context.pathParam("candidateHandle"));
                        context.json(queries.manualCaptureSourceContext(trusted.projectId(), candidateId));
                    })
                    .get("/v1/projects/{projectId}/knowledge", context -> {
                        var trusted = trustedContext(context);
                        requireProjectPath(context, trusted);
                        context.json(queries.knowledge(
                                trusted.projectId(), boundedGraphLimit(context.queryParam("limit"), 1, 100, 50)));
                    })
                    .get("/v1/projects/{projectId}/knowledge/{itemHandle}", context -> {
                        var trusted = trustedContext(context);
                        requireProjectPath(context, trusted);
                        var itemId =
                                queries.resolveKnowledgeHandle(trusted.projectId(), context.pathParam("itemHandle"));
                        var item = queries.current(trusted.projectId(), "Requirement").stream()
                                .filter(row -> itemId.equals(opaqueIdentifier(row.get("item"))))
                                .findFirst()
                                .orElseThrow(() -> new ProjectScopedQueryService.ResourceNotFoundException(
                                        "knowledge handle is not visible in this project"));
                        context.json(item);
                    })
                    .get("/v1/projects/{projectId}/knowledge/{itemHandle}/evidence", context -> {
                        var trusted = trustedContext(context);
                        requireProjectPath(context, trusted);
                        var itemId =
                                queries.resolveKnowledgeHandle(trusted.projectId(), context.pathParam("itemHandle"));
                        context.json(Map.of("items", queries.evidence(trusted.projectId(), itemId)));
                    })
                    .post("/v1/projects/{projectId}/candidates/{candidateHandle}/validations", context -> {
                        var trusted = trustedContext(context);
                        requireProjectPath(context, trusted);
                        var candidateId = queries.resolveCandidateHandle(
                                trusted.projectId(), context.pathParam("candidateHandle"));
                        var result =
                                queries.validateAndMarkValidated(trusted.projectId(), candidateId, trusted.actorId());
                        if (!result.conforms()) throw new CandidateInvalidException(result);
                        context.json(Map.of(
                                "requestId", requestId(context),
                                "candidateId", candidateId,
                                "conforms", true,
                                "violations", result.violations(),
                                "validatedAt", java.time.OffsetDateTime.now().toString()));
                    })
                    .post("/v1/projects/{projectId}/candidates/{candidateHandle}/confirmations", context -> {
                        var trusted = trustedContext(context);
                        requireProjectPath(context, trusted);
                        var key = context.header("Idempotency-Key");
                        var body = context.bodyAsClass(ConfirmationRequest.class);
                        if (body.assertion() == null
                                || !"Requirement".equals(body.assertion().type())) {
                            throw new IllegalArgumentException("assertion type is not allowlisted");
                        }
                        var candidateId = queries.resolveCandidateHandle(
                                trusted.projectId(), context.pathParam("candidateHandle"));
                        var decision = lifecycle.confirmDecision(
                                trusted.projectId(),
                                candidateId,
                                trusted.actorId(),
                                key,
                                body.assertion().label(),
                                LocalDate.parse(body.assertion().validFrom()));
                        context.status(decision.replayed() ? 200 : 201)
                                .json(Map.of(
                                        "requestId",
                                        requestId(context),
                                        "candidateId",
                                        candidateId,
                                        "decision",
                                        "confirmed",
                                        "assertedItemId",
                                        opaqueIdentifier(decision.itemIri())));
                    })
                    .post("/v1/projects/{projectId}/candidates/{candidateHandle}/rejections", context -> {
                        var trusted = trustedContext(context);
                        requireProjectPath(context, trusted);
                        var key = context.header("Idempotency-Key");
                        var body = context.bodyAsClass(RejectionRequest.class);
                        var candidateId = queries.resolveCandidateHandle(
                                trusted.projectId(), context.pathParam("candidateHandle"));
                        var result = lifecycle.reject(
                                trusted.projectId(), candidateId, trusted.actorId(), key, body.reason());
                        context.status(result.replayed() ? 200 : 201)
                                .json(Map.of(
                                        "requestId",
                                        requestId(context),
                                        "candidateId",
                                        candidateId,
                                        "decision",
                                        "rejected",
                                        "reason",
                                        result.reason()));
                    })
                    .post("/v1/quick-notes/captures", context -> {
                        var trusted = trustedContext(context);
                        var result = capture.capture(
                                trusted.projectId(),
                                trusted.actorId(),
                                context.header("Idempotency-Key"),
                                context.bodyAsClass(QuickNoteCaptureService.CaptureRequest.class));
                        context.status(result.replayed() ? 200 : 201)
                                .json(Map.of(
                                        "note",
                                        Map.of("id", result.noteId(), "recordedAt", result.recordedAt()),
                                        "candidates",
                                        result.candidates().stream()
                                                .map(candidate -> Map.of(
                                                        "id",
                                                        candidate.id(),
                                                        "sourceItemId",
                                                        candidate.sourceItemId(),
                                                        "status",
                                                        candidate.status(),
                                                        "handle",
                                                        queries.candidateHandle(
                                                                trusted.projectId(), candidate.id())))
                                                .toList()));
                    })
                    .post("/v1/quick-notes/extractions", context -> {
                        var trusted = trustedContext(context);
                        var result = extraction.ingest(
                                trusted.projectId(),
                                trusted.actorId(),
                                context.header("Idempotency-Key"),
                                context.bodyAsClass(LlmCandidateIngestionService.IngestionRequest.class));
                        context.status(result.replayed() ? 200 : 201)
                                .json(Map.of(
                                        "requestId", requestId(context),
                                        "note", Map.of("id", result.noteId()),
                                        "candidates", result.candidates()));
                    })
                    .post("/v1/candidates/{candidateId}/confirmations", context -> {
                        var trusted = trustedContext(context);
                        var key = context.header("Idempotency-Key");
                        var body = context.bodyAsClass(ConfirmationRequest.class);
                        if (body.assertion() == null
                                || !"Requirement".equals(body.assertion().type())) {
                            throw new IllegalArgumentException("assertion type is not allowlisted");
                        }
                        var decision = lifecycle.confirmDecision(
                                trusted.projectId(),
                                context.pathParam("candidateId"),
                                trusted.actorId(),
                                key,
                                body.assertion().label(),
                                LocalDate.parse(body.assertion().validFrom()));
                        context.status(decision.replayed() ? 200 : 201)
                                .json(Map.of(
                                        "requestId",
                                        requestId(context),
                                        "candidateId",
                                        context.pathParam("candidateId"),
                                        "decision",
                                        "confirmed",
                                        "assertedItemId",
                                        opaqueIdentifier(decision.itemIri())));
                    })
                    .post("/v1/candidates/{candidateId}/validations", context -> {
                        var trusted = trustedContext(context);
                        var result = queries.validateAndMarkValidated(
                                trusted.projectId(), context.pathParam("candidateId"), trusted.actorId());
                        if (!result.conforms()) {
                            throw new CandidateInvalidException(result);
                        }
                        context.json(Map.of(
                                "requestId",
                                requestId(context),
                                "candidateId",
                                context.pathParam("candidateId"),
                                "conforms",
                                true,
                                "violations",
                                result.violations(),
                                "validatedAt",
                                java.time.OffsetDateTime.now().toString()));
                    })
                    .post("/v1/candidates/{candidateId}/rejections", context -> {
                        var trusted = trustedContext(context);
                        var key = context.header("Idempotency-Key");
                        var body = context.bodyAsClass(RejectionRequest.class);
                        var result = lifecycle.reject(
                                trusted.projectId(),
                                context.pathParam("candidateId"),
                                trusted.actorId(),
                                key,
                                body.reason());
                        context.status(result.replayed() ? 200 : 201)
                                .json(Map.of(
                                        "requestId",
                                        requestId(context),
                                        "candidateId",
                                        result.candidateId(),
                                        "decision",
                                        "rejected",
                                        "reason",
                                        result.reason()));
                    })
                    .get("/v1/knowledge-items/current", context -> {
                        var trusted = trustedContext(context);
                        context.json(Map.of(
                                "requestId",
                                requestId(context),
                                "items",
                                queries.current(trusted.projectId(), context.queryParam("type"))));
                    })
                    .get("/v1/retrieval/current-requirements", context -> {
                        var trusted = trustedContext(context);
                        int limit = boundedLimit(context.queryParam("limit"));
                        context.json(m4.retrieve(trusted.projectId(), "current-requirements", Map.of("limit", limit)));
                    })
                    .get("/v1/retrieval/requirement-history", context -> {
                        var trusted = trustedContext(context);
                        var requirementId = context.queryParam("requirementId");
                        int limit = boundedLimit(context.queryParam("limit"));
                        context.json(m4.retrieve(
                                trusted.projectId(),
                                "requirement-history",
                                Map.of("limit", limit, "requirementId", requirementId == null ? "" : requirementId)));
                    })
                    .get("/v1/retrieval/unresolved-blockers", context -> {
                        var trusted = trustedContext(context);
                        int limit = boundedLimit(context.queryParam("limit"));
                        context.json(m4.retrieve(trusted.projectId(), "unresolved-blockers", Map.of("limit", limit)));
                    })
                    .post("/v1/inference/rebuild", context -> {
                        var trusted = trustedContext(context);
                        context.json(m4.rebuildInference(trusted.projectId()));
                    })
                    .get("/v1/entities/link-context", context -> {
                        var trusted = trustedContext(context);
                        var rawLimit = context.queryParam("limit");
                        var limit = rawLimit == null ? 50 : Integer.parseInt(rawLimit);
                        context.json(Map.of(
                                "requestId", requestId(context),
                                "entities", queries.entityLinkContext(trusted.projectId(), limit)));
                    })
                    .get("/v1/candidates/{candidateId}/history", context -> {
                        var trusted = trustedContext(context);
                        context.json(Map.of(
                                "requestId",
                                requestId(context),
                                "items",
                                queries.history(trusted.projectId(), context.pathParam("candidateId"))));
                    })
                    .get("/v1/knowledge-items/{itemId}/evidence", context -> {
                        var trusted = trustedContext(context);
                        context.json(Map.of(
                                "requestId",
                                requestId(context),
                                "items",
                                queries.evidence(trusted.projectId(), context.pathParam("itemId"))));
                    });
        });
        var stopped = new java.util.concurrent.atomic.AtomicBoolean();
        Runnable stop = () -> {
            if (stopped.compareAndSet(false, true)) {
                application.stop();
            }
        };
        Runtime.getRuntime().addShutdownHook(new Thread(stop, "projecta-semantic-core-shutdown"));
        application.start(configuration.host(), configuration.port());
        if ("1".equals(System.getenv("PROJECTA_LOCAL_CONTROL_PIPE"))) {
            awaitLocalStop(stop);
        }
    }

    private static void awaitLocalStop(Runnable stop) {
        try (var input = new BufferedReader(new InputStreamReader(System.in, StandardCharsets.UTF_8))) {
            String command;
            while ((command = input.readLine()) != null && !command.equals("stop")) {
                // Ignore anything except the launcher's private shutdown command.
            }
        } catch (IOException ignored) {
            // Loss of the launcher's pipe must stop this local service.
        } finally {
            stop.run();
        }
    }

    public static String serviceName() {
        return "semantic-core";
    }

    private record HealthResponse(String status) {}

    private static String requestId(io.javalin.http.Context context) {
        return context.header("X-Request-Id") == null ? "unknown" : context.header("X-Request-Id");
    }

    private static String operationId(io.javalin.http.Context context) {
        return context.header("X-Operation-Id") == null ? "op-unknown" : context.header("X-Operation-Id");
    }

    private static String opaqueIdentifier(String iri) {
        return iri.substring(iri.lastIndexOf('/') + 1);
    }

    private static void writeProblem(io.javalin.http.Context context, RuntimeException exception) {
        var problem = new ApiErrorTranslator().translate(requestId(context), exception);
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("type", problem.type());
        body.put("title", problem.title());
        body.put("status", problem.status());
        body.put("code", problem.code());
        body.put("detail", problem.detail());
        body.put("requestId", problem.requestId());
        body.put("operationId", operationId(context));
        context.header("X-Request-Id", problem.requestId());
        context.header("X-Operation-Id", operationId(context));
        if (exception instanceof CandidateInvalidException invalid) {
            body.put("violations", invalid.result().violations());
        }
        var outcome = problem.status() >= 500 ? "failed" : "rejected";
        OperationEventLogger.failed(context, problem.status(), outcome, problem.code());
        LOGGER.log(
                Level.WARNING,
                "projecta.semantic_core event=operation.failed requestId={0} operationId={1} status={2} code={3} outcome={4}",
                new Object[] {problem.requestId(), operationId(context), problem.status(), problem.code(), outcome});
        context.status(problem.status()).json(body).contentType("application/problem+json");
    }

    private static TrustedProjectContext trustedContext(io.javalin.http.Context context) {
        try {
            return TrustedProjectContext.fromPrivateHeadersOrEnvironment(
                    context.header("X-Projecta-Project-Id"),
                    context.header("X-Projecta-Actor-Id"),
                    context.header("X-Operation-Id"),
                    System.getenv());
        } catch (IllegalStateException exception) {
            throw new io.javalin.http.UnauthorizedResponse("trusted project context is required");
        }
    }

    private static TrustedActorContext trustedActorContext(io.javalin.http.Context context) {
        var actor = context.header("X-Projecta-Actor-Id");
        if (actor == null || actor.isBlank()) {
            throw new io.javalin.http.UnauthorizedResponse("trusted actor context is required");
        }
        return new TrustedActorContext(actor, operationId(context));
    }

 
    private static String requiredQueryParameter(io.javalin.http.Context context, String name) {
        var value = context.queryParam(name);
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException("required import parameter is missing");
        }
        return value;
    }

    private static boolean booleanQueryParameter(io.javalin.http.Context context, String name) {
        var value = requiredQueryParameter(context, name);
        if (!"true".equals(value) && !"false".equals(value)) {
            throw new IllegalArgumentException("import boolean parameter is invalid");
        }
        return Boolean.parseBoolean(value);
    }

    private record ConfirmationRequest(Assertion assertion) {}

    private record Assertion(String type, String label, String validFrom) {}

    private record RejectionRequest(String reason) {}

    private static int boundedLimit(String raw) {
        try {
            int limit = raw == null ? 50 : Integer.parseInt(raw);
            if (limit < 1 || limit > 100) throw new IllegalArgumentException("query limit must be between 1 and 100");
            return limit;
        } catch (NumberFormatException exception) {
            throw new IllegalArgumentException("query limit must be an integer", exception);
        }
    }

    private static int boundedGraphLimit(String raw, int minimum, int maximum, int fallback) {
        try {
            int limit = raw == null ? fallback : Integer.parseInt(raw);
            if (limit < minimum || limit > maximum) {
                throw new IllegalArgumentException("graph limit is outside the released bounds");
            }
            return limit;
        } catch (NumberFormatException exception) {
            throw new IllegalArgumentException("graph limit must be an integer", exception);
        }
    }

    private static void requireProjectPath(io.javalin.http.Context context, TrustedProjectContext trusted) {
        if (!trusted.projectId().value().equals(context.pathParam("projectId"))) {
            throw new io.javalin.http.NotFoundResponse("project is not visible in the trusted project context");
        }
    }

    private static void validateGraphFilters(io.javalin.http.Context context) {
        allowlistedCsv(
                context.queryParam("semanticTypes"),
                java.util.Set.of(
                        "Project",
                        "Note",
                        "NoteItem",
                        "Requirement",
                        "Decision",
                        "Question",
                        "Task",
                        "Risk",
                        "Assumption",
                        "Constraint",
                        "ProgressClaim",
                        "ResearchFinding",
                        "Person",
                        "Candidate",
                        "SourceArtifact"));
        allowlistedCsv(
                context.queryParam("relationTypes"),
                java.util.Set.of(
                        "implements",
                        "blocks",
                        "dependsOn",
                        "supports",
                        "answers",
                        "resolves",
                        "constrainedBy",
                        "supersedes",
                        "derivedFrom",
                        "hasNoteItem",
                        "belongsToProject",
                        "evidenceFor",
                        "provenanceFor"));
        allowlistedCsv(
                context.queryParam("verificationStates"),
                java.util.Set.of("candidate", "asserted", "inferred", "unverified"));
        allowlistedCsv(
                context.queryParam("lifecycleStates"),
                java.util.Set.of(
                        "current", "pending-review", "confirmed", "rejected", "superseded", "retracted", "stale"));
        allowlistedCsv(
                context.queryParam("provenanceStates"),
                java.util.Set.of("source-backed", "human-confirmed", "rule-derived", "candidate-proposed"));
        var evidence = context.queryParam("evidence");
        if (evidence != null
                && !java.util.Set.of("any", "with-evidence", "without-evidence").contains(evidence)) {
            throw new IllegalArgumentException("graph evidence filter is not allowlisted");
        }
        var revision = context.queryParam("projectionRevision");
        if (revision != null && !revision.matches("[a-zA-Z0-9._-]{1,128}")) {
            throw new IllegalArgumentException("graph projection revision is invalid");
        }
    }

    private static void allowlistedCsv(String raw, java.util.Set<String> allowed) {
        if (raw == null || raw.isBlank()) return;
        for (var value : raw.split(",", -1)) {
            if (!allowed.contains(value)) throw new IllegalArgumentException("graph filter is not allowlisted");
        }
    }
}
