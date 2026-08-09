package org.projecta.semanticcore;

import io.javalin.http.Context;
import java.util.logging.Logger;

/** Emits correlation-safe operation events without paths, bodies, or semantic payloads. */
public final class OperationEventLogger {
    private static final Logger LOGGER = Logger.getLogger("projecta.semantic-core.operations");

    private OperationEventLogger() {}

    public static void started(Context context) {
        log("operation.started", context, null, null, null);
    }

    public static void completed(Context context) {
        int status = context.status().getCode();
        if (!shouldComplete(status)) return;
        log("operation.completed", context, status, "success", null);
    }

    public static void failed(Context context, int status, String outcome, String code) {
        log("operation.failed", context, status, outcome, code);
    }

    public static String routeClass(String method, String path) {
        if (path == null) return "unknown";
        if (path.equals("/health/live")) return "health.live";
        if (path.equals("/health/ready")) return "health.ready";
        if (path.contains("/quick-notes")) return "note.capture";
        if (path.contains("/validations")) return "candidate.validation";
        if (path.contains("/confirmations")) return "candidate.confirmation";
        if (path.contains("/rejections")) return "candidate.rejection";
        if (path.contains("/history")) return "candidate.history";
        if (path.contains("/evidence")) return "knowledge.evidence";
        if (path.contains("/knowledge-items")) return "knowledge.query";
        if (path.contains("/project-context/inference")) return "inference.rebuild";
        if (path.contains("/project-context")) return "project.context";
        if (path.contains("/entities")) return "graph.projection";
        if (path.contains("/graph")) return "graph.projection";
        if (path.contains("/projects")) return "project.catalog";
        if ("POST".equals(method) && path.contains("/inference")) return "inference.rebuild";
        return "unknown";
    }

    static boolean shouldComplete(int status) {
        return status >= 200 && status < 400;
    }

    private static void log(String event, Context context, Integer status, String outcome, String code) {
        var operation = routeClass(context.method().name(), context.path());
        var message = String.format(
                "event=%s service=semantic-core boundary=semantic-core requestId=%s operationId=%s operation=%s attempt=1 status=%s outcome=%s errorClass=%s",
                event,
                safe(context.header("X-Request-Id"), "req-unknown"),
                safe(context.header("X-Operation-Id"), "op-unknown"),
                operation,
                status == null ? "null" : status,
                outcome == null ? "null" : outcome,
                code == null ? "null" : code);
        LOGGER.info(message);
    }

    private static String safe(String value, String fallback) {
        return value == null || value.isBlank() || value.length() > 128 ? fallback : value;
    }
}
