package org.projecta.semanticcore;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.net.URI;
import java.net.http.HttpClient;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;

class FusekiQueryServiceProjectionTest {
    private static final String PROJECTA = "https://w3id.org/projecta/ontology/";
    private static final String PROJECT = "https://w3id.org/projecta/data/project/project-alpha";
    private static final String NOTE = PROJECT + "/note/note-1";
    private static final String ITEM = PROJECT + "/note-item/note-1-1";
    private static final String CANDIDATE = PROJECT + "/candidate/note-1-1";

    @Test
    void graphProjectsCommittedSourceAndManualCandidateWithoutStoredCandidateLabel() {
        var gateway = new ProjectionGateway();
        var service = new FusekiQueryService(gateway, new GraphIriRouter(), null);

        var result = service.graph(new ProjectId("project-alpha"), 50, 100);
        var nodes = castMaps(result.get("nodes"));
        var edges = castMaps(result.get("edges"));

        assertEquals(List.of("Note", "NoteItem", "Requirement"), field(nodes, "semanticType"));
        assertEquals(
                List.of("Meeting 10/08", "research new VAE Architecture", "research new VAE Architecture"),
                field(nodes, "label"));
        assertEquals(List.of("hasNoteItem", "derivedFrom"), field(edges, "relationType"));
        assertEquals(List.of("unverified", "candidate"), field(edges, "verificationState"));
        assertTrue(gateway.queries.getFirst().contains("/sources/"));
        assertTrue(gateway.queries.getFirst().contains("manual-quick-note-v0.3.0"));
    }

    @Test
    void candidateQueueProjectsManualLabelAndTypeFromCanonicalSourceItem() {
        var gateway = new ProjectionGateway();
        var service = new FusekiQueryService(gateway, new GraphIriRouter(), null);

        var result = service.candidates(new ProjectId("project-alpha"), 50);
        var candidates = castMaps(result.get("candidates"));

        assertEquals(1, candidates.size());
        assertEquals("research new VAE Architecture", candidates.getFirst().get("label"));
        assertEquals("Requirement", candidates.getFirst().get("proposedType"));
        assertEquals("extracted", candidates.getFirst().get("validationState"));
        assertTrue(gateway.queries.getFirst().contains("contentText"));
        assertTrue(gateway.queries.getFirst().contains("hasItemType"));
        assertTrue(gateway.queries.getFirst().contains("connector-json-mock-v1"));
    }

    @SuppressWarnings("unchecked")
    private static List<Map<String, Object>> castMaps(Object value) {
        return (List<Map<String, Object>>) value;
    }

    private static List<Object> field(List<Map<String, Object>> rows, String name) {
        return rows.stream().map(row -> row.get(name)).toList();
    }

    private static final class ProjectionGateway extends FusekiGateway {
        private final List<String> queries = new ArrayList<>();

        private ProjectionGateway() {
            super(HttpClient.newHttpClient(), URI.create("http://unused.invalid/projecta"));
        }

        @Override
        public String select(String query) {
            queries.add(query);
            if (query.contains("SELECT DISTINCT ?resource")) return nodeRows();
            if (query.contains("SELECT DISTINCT ?source")) return edgeRows();
            if (query.contains("SELECT DISTINCT ?candidate")) return candidateRows();
            throw new AssertionError("Unexpected query: " + query);
        }

        private static String nodeRows() {
            return rows(
                    row(
                            "resource",
                            NOTE,
                            "label",
                            "Meeting 10/08",
                            "type",
                            PROJECTA + "Note",
                            "verificationState",
                            "unverified",
                            "lifecycleState",
                            "current",
                            "provenanceState",
                            "source-backed"),
                    row(
                            "resource",
                            ITEM,
                            "label",
                            "research new VAE Architecture",
                            "type",
                            PROJECTA + "NoteItem",
                            "verificationState",
                            "unverified",
                            "lifecycleState",
                            "current",
                            "provenanceState",
                            "source-backed"),
                    row(
                            "resource",
                            CANDIDATE,
                            "label",
                            "research new VAE Architecture",
                            "type",
                            PROJECTA + "Requirement",
                            "verificationState",
                            "candidate",
                            "lifecycleState",
                            "pending-review",
                            "provenanceState",
                            "candidate-proposed"));
        }

        private static String edgeRows() {
            return rows(
                    row(
                            "source",
                            NOTE,
                            "target",
                            ITEM,
                            "predicate",
                            PROJECTA + "hasNoteItem",
                            "verificationState",
                            "unverified",
                            "provenanceState",
                            "source-backed"),
                    row(
                            "source",
                            CANDIDATE,
                            "target",
                            ITEM,
                            "predicate",
                            PROJECTA + "derivedFrom",
                            "verificationState",
                            "candidate",
                            "provenanceState",
                            "candidate-proposed"));
        }

        private static String candidateRows() {
            return rows(row(
                    "candidate",
                    CANDIDATE,
                    "label",
                    "research new VAE Architecture",
                    "status",
                    PROJECTA + "extracted",
                    "type",
                    PROJECTA + "Requirement"));
        }

        private static String rows(String... bindings) {
            return "{\"results\":{\"bindings\":[" + String.join(",", bindings) + "]}}";
        }

        private static String row(String... pairs) {
            var values = new ArrayList<String>();
            for (var index = 0; index < pairs.length; index += 2) {
                values.add("\"" + pairs[index] + "\":{\"value\":\"" + pairs[index + 1] + "\"}");
            }
            return "{" + String.join(",", values) + "}";
        }
    }
}
