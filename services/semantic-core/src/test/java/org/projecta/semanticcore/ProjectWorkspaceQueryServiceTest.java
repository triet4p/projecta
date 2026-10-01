package org.projecta.semanticcore;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import org.junit.jupiter.api.Test;

class ProjectWorkspaceQueryServiceTest {
    @Test
    void catalogQueriesOnlyTheExplicitAllowlistAndOrdersDeterministically() {
        var service = new ProjectWorkspaceQueryService(ProjectWorkspaceQueryServiceTest::select, new GraphIriRouter());

        var result =
                service.catalog(List.of(new ProjectId("zeta"), new ProjectId("alpha"), new ProjectId("zeta")), 100);

        assertEquals(
                List.of("alpha", "zeta"),
                result.projects().stream()
                        .map(ProjectWorkspaceQueryService.CatalogItem::projectId)
                        .toList());
        assertEquals("Alpha", result.projects().getFirst().name());
        assertEquals(1, result.projects().getFirst().counts().get("requirements"));
        assertTrue(result.catalogRevision().startsWith("catalog-r-"));
    }

    @Test
    void overviewUsesRouteCompatibleOpaqueHandlesForSelectedProject() {
        var service = new ProjectWorkspaceQueryService(ProjectWorkspaceQueryServiceTest::select, new GraphIriRouter());

        var result = service.overview(new ProjectId("alpha"), 10);

        assertEquals("Alpha", result.project().name());
        assertEquals("Requirement", result.currentRequirements().getFirst().get("label"));
        assertEquals(1, result.evidenceCoverage().get("covered"));
        assertEquals(
                "node-h-" + OpaqueIds.opaqueHandle("https://w3id.org/projecta/data/alpha/item-1"),
                result.currentRequirements().getFirst().get("handle"));
        assertEquals(
                "note-h-" + OpaqueIds.opaqueHandle("https://w3id.org/projecta/data/alpha/note-1"),
                result.recentNotes().getFirst().get("handle"));
        assertEquals(
                "candidate-h-" + OpaqueIds.opaqueHandle("https://w3id.org/projecta/data/alpha/candidate-1"),
                result.pendingCandidates().getFirst().get("handle"));
    }

    private static String select(String query) {
        if (query.contains("SELECT ?name ?summary")) {
            var name = query.contains("/alpha") ? "Alpha" : "Zeta";
            return row("name", name, "summary", name + " summary");
        }
        if (query.contains("SELECT ?item ?label"))
            return row("item", "https://w3id.org/projecta/data/alpha/item-1", "label", "Requirement");
        if (query.contains("SELECT ?note ?label"))
            return row("note", "https://w3id.org/projecta/data/alpha/note-1", "label", "Note");
        if (query.contains("SELECT ?candidate ?label"))
            return row("candidate", "https://w3id.org/projecta/data/alpha/candidate-1", "label", "Candidate");
        if (query.contains("MAX(?endedAt)")) return row("lastActivityAt", "2026-08-09T10:00:00Z");
        if (query.contains("AS ?covered")) return row("covered", "1", "total", "1");
        return "{\"results\":{\"bindings\":[{"
                + "\"requirements\":{\"value\":\"1\"},\"tasks\":{\"value\":\"0\"},"
                + "\"questions\":{\"value\":\"0\"},\"risks\":{\"value\":\"0\"},"
                + "\"notes\":{\"value\":\"0\"},\"candidates\":{\"value\":\"0\"}"
                + "}]}}";
    }

    private static String row(String key, String value) {
        return "{\"results\":{\"bindings\":[{\"" + key + "\":{\"value\":\"" + value + "\"}}]}}";
    }

    private static String row(String key, String value, String key2, String value2) {
        return "{\"results\":{\"bindings\":[{\"" + key + "\":{\"value\":\"" + value + "\"},\"" + key2
                + "\":{\"value\":\"" + value2 + "\"}}]}}";
    }
}
