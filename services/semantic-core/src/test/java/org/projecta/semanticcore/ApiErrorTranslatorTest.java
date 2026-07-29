package org.projecta.semanticcore;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;

import org.junit.jupiter.api.Test;

class ApiErrorTranslatorTest {
    private final ApiErrorTranslator translator = new ApiErrorTranslator();

    @Test
    void returnsOnlyPublishedProblemFieldsForInvalidInput() {
        var problem = translator.translate("req-01", new IllegalArgumentException("resource ID must be valid"));

        assertEquals(400, problem.status());
        assertEquals("INVALID_REQUEST", problem.code());
        assertEquals("req-01", problem.requestId());
        assertFalse(problem.detail().contains("resource ID"));
    }

    @Test
    void translatesScopeAndIdempotencyFailuresWithoutInternalDetails() {
        var missing = translator.translate(
                "req-02", new ProjectScopedQueryService.ResourceNotFoundException("graph https://internal.example"));
        var reused = translator.translate(
                "req-03", new IllegalArgumentException("idempotency key was reused with a different request body"));

        assertEquals(404, missing.status());
        assertEquals("RESOURCE_NOT_FOUND", missing.code());
        assertFalse(missing.detail().contains("internal"));
        assertEquals(409, reused.status());
        assertEquals("IDEMPOTENCY_KEY_REUSED", reused.code());
    }

    @Test
    void translatesLifecycleAndUnexpectedFailuresToPublishedCodes() {
        assertEquals(
                "INVALID_LIFECYCLE_STATE",
                translator
                        .translate("req-04", new IllegalStateException("candidate is terminal"))
                        .code());
        assertEquals(
                "INTERNAL_ERROR",
                translator
                        .translate("req-05", new RuntimeException("Fuseki URL"))
                        .code());
    }
}
