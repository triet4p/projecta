package org.projecta.semanticcore;

import io.javalin.Javalin;
import java.net.http.HttpClient;
import java.nio.file.Path;
import java.time.LocalDate;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Semantic Core composition root.
 *
 * <p>HTTP endpoints are introduced only by their corresponding Sprint 3 tasks. This temporary
 * server lifecycle is the container smoke-test baseline; S3-10 adds validated configuration and
 * health endpoints.
 */
public final class SemanticCoreApplication {
    private SemanticCoreApplication() {}

    public static void main(String[] args) {
        var configuration = SemanticCoreConfiguration.fromEnvironment(System.getenv());
        var readiness = new FusekiReadiness(HttpClient.newHttpClient(), configuration);
        var gateway = new FusekiGateway(HttpClient.newHttpClient(), configuration.fusekiDatasetUrl());
        var router = new GraphIriRouter();
        var validation = new RemoteCandidateValidationService(gateway, router, Path.of("/ontology/shapes"));
        var lifecycle = new FusekiLifecycleService(gateway, router, validation);
        var queries = new FusekiQueryService(gateway, router, validation);
        var application = Javalin.create(config -> {
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
                                        decision.itemIri()));
                    })
                    .post("/v1/candidates/{candidateId}/validations", context -> {
                        var trusted = trustedContext(context);
                        var result = queries.validate(trusted.projectId(), context.pathParam("candidateId"));
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
        Runtime.getRuntime().addShutdownHook(new Thread(application::stop));
        application.start(configuration.port());
    }

    public static String serviceName() {
        return "semantic-core";
    }

    private record HealthResponse(String status) {}

    private static String requestId(io.javalin.http.Context context) {
        return context.header("X-Request-Id") == null ? "unknown" : context.header("X-Request-Id");
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
        if (exception instanceof CandidateInvalidException invalid) {
            body.put("violations", invalid.result().violations());
        }
        context.status(problem.status()).json(body).contentType("application/problem+json");
    }

    private static TrustedProjectContext trustedContext(io.javalin.http.Context context) {
        try {
            return TrustedProjectContext.fromEnvironment(System.getenv());
        } catch (IllegalStateException exception) {
            throw new io.javalin.http.UnauthorizedResponse("trusted project context is required");
        }
    }

    private record ConfirmationRequest(Assertion assertion) {}

    private record Assertion(String type, String label, String validFrom) {}

    private record RejectionRequest(String reason) {}
}
