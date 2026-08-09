package org.projecta.semanticcore;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;

class OperationEventLoggerTest {
    @Test
    void classifiesFiniteOperationsWithoutEmbeddingIdentifiers() {
        assertEquals("note.capture", OperationEventLogger.routeClass("POST", "/v1/quick-notes/captures"));
        assertEquals("knowledge.evidence", OperationEventLogger.routeClass("GET", "/v1/knowledge-items/x/evidence"));
        assertEquals("graph.projection", OperationEventLogger.routeClass("GET", "/v1/entities/link-context"));
        assertEquals("project.catalog", OperationEventLogger.routeClass("GET", "/v1/projects"));
        assertEquals("inference.rebuild", OperationEventLogger.routeClass("POST", "/v1/inference/rebuild"));
        assertEquals("unknown", OperationEventLogger.routeClass("GET", "/v1/internal/secret-id"));
    }

    @Test
    void doesNotEmitSuccessfulCompletionForTerminalErrors() {
        assertTrue(OperationEventLogger.shouldComplete(200));
        assertTrue(OperationEventLogger.shouldComplete(302));
        assertFalse(OperationEventLogger.shouldComplete(409));
        assertFalse(OperationEventLogger.shouldComplete(503));
    }
}
