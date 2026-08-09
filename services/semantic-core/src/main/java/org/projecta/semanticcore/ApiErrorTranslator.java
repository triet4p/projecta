package org.projecta.semanticcore;

/** Maps domain failures to the finite HTTP problem contract. */
public final class ApiErrorTranslator {
    private static final String BASE = "https://w3id.org/projecta/problems/";

    public ApiProblem translate(String requestId, RuntimeException exception) {
        var message = exception.getMessage() == null ? "" : exception.getMessage();
        if (exception instanceof io.javalin.http.BadRequestResponse) {
            return problem(
                    requestId,
                    400,
                    "INVALID_REQUEST",
                    "Invalid request",
                    "The request does not meet the published contract.");
        }
        if (exception instanceof CandidateNotFoundException) {
            return problem(
                    requestId,
                    404,
                    "CANDIDATE_NOT_FOUND",
                    "Candidate not found",
                    "The candidate is not visible in this project.");
        }
        if (exception instanceof CandidateInvalidException) {
            return problem(
                    requestId,
                    422,
                    "CANDIDATE_INVALID",
                    "Candidate does not conform",
                    "The candidate violates released v0.2 shapes.");
        }
        if (exception instanceof io.javalin.http.UnauthorizedResponse) {
            return problem(
                    requestId,
                    401,
                    "PROJECT_CONTEXT_REQUIRED",
                    "Project context required",
                    "A trusted project context is required.");
        }
        if (exception instanceof ProjectScopedQueryService.ResourceNotFoundException) {
            return problem(
                    requestId,
                    404,
                    "RESOURCE_NOT_FOUND",
                    "Resource not found",
                    "The resource is not visible in this project.");
        }
        if (exception instanceof IllegalArgumentException) {
            if (message.contains("released SHACL shapes")) {
                return problem(
                        requestId,
                        422,
                        "CANDIDATE_INVALID",
                        "Candidate does not conform",
                        "The candidate violates released v0.2 shapes.");
            }
            var code = message.contains("idempotency key") ? "IDEMPOTENCY_KEY_REUSED" : "INVALID_REQUEST";
            var status = code.equals("IDEMPOTENCY_KEY_REUSED") ? 409 : 400;
            return problem(
                    requestId, status, code, "Invalid request", "The request does not meet the published contract.");
        }
        if (exception instanceof IllegalStateException) {
            if (message.contains("semantic store response")) {
                return problem(
                        requestId,
                        502,
                        "QUERY_FAILED",
                        "Query failed",
                        "The semantic service returned an invalid query result.");
            }
            if (message.contains("semantic store") || message.contains("released candidate SHACL")) {
                return problem(
                        requestId,
                        503,
                        "PERSISTENCE_UNAVAILABLE",
                        "Persistence unavailable",
                        "The semantic store or released validation artifacts are unavailable.");
            }
            return problem(
                    requestId,
                    409,
                    "INVALID_LIFECYCLE_STATE",
                    "Invalid lifecycle state",
                    "The requested transition is not allowed.");
        }
        return problem(requestId, 500, "INTERNAL_ERROR", "Internal error", "The request could not be completed.");
    }

    private static ApiProblem problem(String requestId, int status, String code, String title, String detail) {
        return new ApiProblem(BASE + code.toLowerCase().replace('_', '-'), title, status, code, detail, requestId);
    }
}
