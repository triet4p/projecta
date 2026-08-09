package org.projecta.semanticcore;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Bounded catalog and overview queries over an explicit server-owned project scope. */
public final class ProjectWorkspaceQueryService {
    private static final String PROJECTA = "https://w3id.org/projecta/ontology/";
    private static final String RDFS = "http://www.w3.org/2000/01/rdf-schema#";
    private static final String PROV = "http://www.w3.org/ns/prov#";
    private final QueryGateway gateway;
    private final GraphIriRouter router;
    private final ObjectMapper json = new ObjectMapper();

    public ProjectWorkspaceQueryService(FusekiGateway gateway, GraphIriRouter router) {
        this(gateway::select, router);
    }

    ProjectWorkspaceQueryService(QueryGateway gateway, GraphIriRouter router) {
        this.gateway = gateway;
        this.router = router;
    }

    /** Query only the supplied finite allowlist; no client filter or graph IRI is accepted. */
    public Catalog catalog(List<ProjectId> authorizedProjects, int limit) {
        if (authorizedProjects == null || authorizedProjects.size() > 100 || limit < 1 || limit > 100) {
            throw new IllegalArgumentException("project catalog limit is invalid");
        }
        var unique = authorizedProjects.stream().distinct().toList();
        var items = new ArrayList<CatalogItem>();
        for (var project : unique) items.add(project(project));
        items.sort(Comparator.comparing(CatalogItem::status)
                .thenComparing(item -> item.name().toLowerCase())
                .thenComparing(CatalogItem::projectId));
        var bounded = items.stream().limit(limit).toList();
        return new Catalog(bounded, revision(unique));
    }

    public CatalogItem project(ProjectId project) {
        var nameAndSummary = rows(gateway.select("SELECT ?name ?summary WHERE { { GRAPH <"
                + graph(project, GraphRole.ASSERTED)
                + "> { <" + projectIri(project) + "> <" + PROJECTA + "name> ?name . OPTIONAL { <"
                + projectIri(project) + "> <" + RDFS + "comment> ?summary . } } } UNION { GRAPH <"
                + graph(project, GraphRole.SOURCES) + "> { <" + projectIri(project) + "> <" + PROJECTA
                + "name> ?name . OPTIONAL { <" + projectIri(project) + "> <" + RDFS + "comment> ?summary . } } } }"));
        var first = nameAndSummary.stream()
                .findFirst()
                .orElseThrow(() -> new IllegalStateException("project catalog is missing a project name"));
        var name = required(first, "name");
        var summary = first.get("summary");
        var counts = count(project);
        var activity = rows(gateway.select("SELECT (MAX(?endedAt) AS ?lastActivityAt) WHERE { GRAPH <"
                        + graph(project, GraphRole.PROVENANCE) + "> { ?activity a <" + PROV + "Activity> ; <" + PROV
                        + "endedAtTime> ?endedAt . } }"))
                .stream()
                .findFirst()
                .map(row -> row.get("lastActivityAt"))
                .orElse(null);
        return new CatalogItem(
                project.value(),
                name,
                summary,
                "active",
                counts,
                activity,
                "fresh",
                "current",
                revision(List.of(project)));
    }

    /** Return bounded labeled collections for exactly one already-authorized project. */
    public Overview overview(ProjectId project, int limit) {
        if (limit < 1 || limit > 100) throw new IllegalArgumentException("project overview limit is invalid");
        var item = project(project);
        return new Overview(
                item,
                list(project, GraphRole.ASSERTED, "Requirement", limit),
                list(project, GraphRole.ASSERTED, "Question", limit),
                list(project, GraphRole.ASSERTED, "Task", limit),
                list(project, GraphRole.INFERRED, "UnresolvedBlocker", limit),
                list(project, GraphRole.ASSERTED, "Risk", limit),
                recentNotes(project, limit),
                pendingCandidates(project, limit),
                evidenceCoverage(project));
    }

    private List<Map<String, String>> list(ProjectId project, GraphRole role, String type, int limit) {
        var result = rows(gateway.select("SELECT ?item ?label WHERE { GRAPH <" + graph(project, role) + "> { ?item a <"
                + PROJECTA + type + "> ; <" + RDFS + "label> ?label . } } ORDER BY ?item LIMIT " + limit));
        return result.stream()
                .map(row -> Map.of("handle", opaque(required(row, "item")), "label", required(row, "label")))
                .toList();
    }

    private List<Map<String, String>> recentNotes(ProjectId project, int limit) {
        var result = rows(gateway.select("SELECT ?note ?label ?recordedAt WHERE { GRAPH <"
                + graph(project, GraphRole.SOURCES)
                + "> { ?note a <" + PROJECTA + "Note> ; <" + PROJECTA + "name> ?label . OPTIONAL { ?note <"
                + PROJECTA + "recordedAt> ?recordedAt . } } } ORDER BY DESC(?recordedAt) ?note LIMIT " + limit));
        return result.stream()
                .map(row -> {
                    Map<String, String> value = new LinkedHashMap<>();
                    value.put("handle", opaque(row.get("note")));
                    value.put("label", required(row, "label"));
                    if (row.containsKey("recordedAt")) value.put("recordedAt", row.get("recordedAt"));
                    return value;
                })
                .toList();
    }

    private List<Map<String, String>> pendingCandidates(ProjectId project, int limit) {
        var result = rows(gateway.select("SELECT ?candidate ?label WHERE { GRAPH <"
                + graph(project, GraphRole.CANDIDATES)
                + "> { ?candidate a <" + PROJECTA + "Candidate> ; <" + PROJECTA + "candidateStatus> <" + PROJECTA
                + "pending-review> . OPTIONAL { ?candidate <" + RDFS
                + "label> ?label . } } } ORDER BY ?candidate LIMIT " + limit));
        return result.stream()
                .map(row -> Map.of("handle", opaque(required(row, "candidate")), "label", required(row, "label")))
                .toList();
    }

    private Map<String, Integer> evidenceCoverage(ProjectId project) {
        var result = rows(
                gateway.select("SELECT (COUNT(DISTINCT ?item) AS ?covered) (COUNT(DISTINCT ?allItem) AS ?total) WHERE {"
                        + " { SELECT ?item WHERE { GRAPH <" + graph(project, GraphRole.SOURCES) + "> { ?item <"
                        + PROJECTA + "contentText> ?text } } }"
                        + " UNION { SELECT ?allItem WHERE { GRAPH <" + graph(project, GraphRole.ASSERTED)
                        + "> { ?allItem a <" + PROJECTA + "KnowledgeItem> } } } }"));
        var row = result.stream().findFirst().orElse(Map.of());
        return Map.of("covered", parseInteger(row.get("covered")), "total", parseInteger(row.get("total")));
    }

    private Map<String, Integer> count(ProjectId project) {
        var query = "SELECT (COUNT(DISTINCT ?requirement) AS ?requirements) (COUNT(DISTINCT ?task) AS ?tasks)"
                + " (COUNT(DISTINCT ?question) AS ?questions) (COUNT(DISTINCT ?risk) AS ?risks)"
                + " (COUNT(DISTINCT ?note) AS ?notes) (COUNT(DISTINCT ?candidate) AS ?candidates) WHERE {"
                + " { SELECT ?requirement WHERE { GRAPH <" + graph(project, GraphRole.ASSERTED) + "> { ?requirement a <"
                + PROJECTA + "Requirement> } } } UNION { SELECT ?task WHERE { GRAPH <"
                + graph(project, GraphRole.ASSERTED)
                + "> { ?task a <" + PROJECTA + "Task> } } } UNION { SELECT ?question WHERE { GRAPH <"
                + graph(project, GraphRole.ASSERTED) + "> { ?question a <" + PROJECTA
                + "Question> } } } UNION { SELECT ?risk WHERE { GRAPH <"
                + graph(project, GraphRole.ASSERTED) + "> { ?risk a <" + PROJECTA
                + "Risk> } } } UNION { SELECT ?note WHERE { GRAPH <"
                + graph(project, GraphRole.SOURCES) + "> { ?note a <" + PROJECTA
                + "Note> } } } UNION { SELECT ?candidate WHERE { GRAPH <"
                + graph(project, GraphRole.CANDIDATES) + "> { ?candidate a <" + PROJECTA + "Candidate> } } } }";
        var row = rows(gateway.select(query)).stream().findFirst().orElse(Map.of());
        var result = new LinkedHashMap<String, Integer>();
        for (var key : List.of("requirements", "tasks", "questions", "risks", "notes", "candidates")) {
            result.put(key, parseInteger(row.get(key)));
        }
        return result;
    }

    private List<Map<String, String>> rows(String response) {
        try {
            var result = new ArrayList<Map<String, String>>();
            for (JsonNode row : json.readTree(response).path("results").path("bindings")) {
                var values = new LinkedHashMap<String, String>();
                row.fields()
                        .forEachRemaining(entry -> values.put(
                                entry.getKey(), entry.getValue().path("value").asText()));
                result.add(values);
            }
            return result;
        } catch (Exception exception) {
            throw new IllegalStateException(
                    "semantic project catalog response was invalid: "
                            + response.substring(0, Math.min(response.length(), 32)),
                    exception);
        }
    }

    private String graph(ProjectId project, GraphRole role) {
        return router.route(project, role).toString();
    }

    private String projectIri(ProjectId project) {
        return "https://w3id.org/projecta/data/project/" + project.value();
    }

    private int parseInteger(String value) {
        try {
            if (value == null) throw new IllegalStateException("semantic project catalog count is missing");
            return Integer.parseInt(value);
        } catch (NumberFormatException exception) {
            throw new IllegalStateException("semantic project catalog count was invalid", exception);
        }
    }

    private static String required(Map<String, String> row, String field) {
        var value = row.get(field);
        if (value == null || value.isBlank()) {
            throw new IllegalStateException("semantic project catalog response is missing: " + field);
        }
        return value;
    }

    private String revision(List<ProjectId> projects) {
        try {
            var digest = MessageDigest.getInstance("SHA-256")
                    .digest(projects.stream()
                            .map(ProjectId::value)
                            .sorted()
                            .reduce((left, right) -> left + "\n" + right)
                            .orElse("")
                            .getBytes(StandardCharsets.UTF_8));
            var result = new StringBuilder("catalog-r-");
            for (byte item : digest) result.append(String.format("%02x", item));
            return result.substring(0, 50);
        } catch (Exception exception) {
            throw new IllegalStateException("SHA-256 is unavailable", exception);
        }
    }

    private String opaque(String iri) {
        try {
            var digest = MessageDigest.getInstance("SHA-256").digest(iri.getBytes(StandardCharsets.UTF_8));
            var result = new StringBuilder("item-h-");
            for (byte item : digest) result.append(String.format("%02x", item));
            return result.substring(0, 48);
        } catch (Exception exception) {
            throw new IllegalStateException("SHA-256 is unavailable", exception);
        }
    }

    public record Catalog(List<CatalogItem> projects, String catalogRevision) {}

    public record CatalogItem(
            String projectId,
            String name,
            String summary,
            String status,
            Map<String, Integer> counts,
            String lastActivityAt,
            String health,
            String freshnessState,
            String freshnessRevision) {}

    public record Overview(
            CatalogItem project,
            List<Map<String, String>> currentRequirements,
            List<Map<String, String>> openQuestions,
            List<Map<String, String>> tasks,
            List<Map<String, String>> blockers,
            List<Map<String, String>> risks,
            List<Map<String, String>> recentNotes,
            List<Map<String, String>> pendingCandidates,
            Map<String, Integer> evidenceCoverage) {}

    @FunctionalInterface
    interface QueryGateway {
        String select(String query);
    }
}
