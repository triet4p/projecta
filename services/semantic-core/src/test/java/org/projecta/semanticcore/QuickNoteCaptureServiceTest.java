package org.projecta.semanticcore;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.net.URI;
import java.net.http.HttpClient;
import java.time.OffsetDateTime;
import java.util.List;
import org.junit.jupiter.api.Test;

class QuickNoteCaptureServiceTest {
    @Test
    void shapeFailureHappensBeforeAnyGraphUpdate() {
        var gateway = new RecordingGateway();
        var service = new QuickNoteCaptureService(
                gateway,
                new GraphIriRouter(),
                (project, sources, candidates, provenance) -> new CandidateValidationResult(
                        false, List.of(new CandidateValidationResult.Violation("evidence is invalid"))));
        var request = new QuickNoteCaptureService.CaptureRequest(
                "A", List.of(new QuickNoteCaptureService.Segment("task", 0, 1, "A")));

        assertThrows(
                CandidateInvalidException.class,
                () -> service.capture(new ProjectId("ecommerce-checkout"), "le", "capture-rollback", request));
        assertFalse(gateway.updateCalled);
    }

    @Test
    void validatesUnicodeCodePointOffsetsRatherThanUtf16Offsets() {
        var gateway = new RecordingGateway();
        var service = new QuickNoteCaptureService(
                gateway, new GraphIriRouter(), (project, sources, candidates, provenance) -> {
                    assertTrue(sources.contains("evidenceEndOffset> \"6\""));
                    return new CandidateValidationResult(true, List.of());
                });
        var request = new QuickNoteCaptureService.CaptureRequest(
                "😀 task", List.of(new QuickNoteCaptureService.Segment("task", 0, 6, "😀 task")));

        var result = service.capture(new ProjectId("ecommerce-checkout"), "le", "capture-unicode", request);

        assertEquals(6, result.candidates().getFirst().id().length() - 37);
        assertTrue(gateway.updateCalled);
    }

    @Test
    void writesApprovedStructuredNoteTitleWithoutChangingLegacyCaptureDefaults() {
        var gateway = new RecordingGateway();
        var service = new QuickNoteCaptureService(
                gateway, new GraphIriRouter(), (project, sources, candidates, provenance) -> {
                    assertTrue(sources.contains("name> \"Structured title\""));
                    return new CandidateValidationResult(true, List.of());
                });
        var request = new QuickNoteCaptureService.CaptureRequest(
                "Structured title", "A", List.of(new QuickNoteCaptureService.Segment("task", 0, 1, "A")));

        service.capture(new ProjectId("ecommerce-checkout"), "le", "capture-structured-title", request);

        assertTrue(gateway.updateCalled);
    }

    private static final class RecordingGateway extends FusekiGateway {
        private boolean updateCalled;

        private RecordingGateway() {
            super(HttpClient.newHttpClient(), URI.create("http://localhost:1/projecta"));
        }

        @Override
        public void update(String update) {
            updateCalled = true;
        }

        @Override
        public boolean ask(String query) {
            return true;
        }

        @Override
        public String select(String query) {
            return "{\"results\":{\"bindings\":[{\"recordedAt\":{\"value\":\"" + OffsetDateTime.now() + "\"}}]}}";
        }
    }
}
