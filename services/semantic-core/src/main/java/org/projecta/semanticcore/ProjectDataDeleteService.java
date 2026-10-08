package org.projecta.semanticcore;

import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Deletes all quads in the five canonical graph IRIs of exactly one project.
 *
 * <p>projecta-deletion.v1 semantic boundary: per-role {@code DELETE WHERE}
 * over the canonical IRIs from {@link GraphIriRouter} (same shape as the
 * import rollback clear). No ontology term, SHACL shape, or inference rule is
 * touched: instance quads are removed as data. The purge refuses when any
 * graph outside the five canonical IRIs carries this project's prefix
 * (foreign-graph fail-closed, mirroring the import isolation check), and
 * refuses an empty scope so an already-absent project can never report a
 * misleading purge.
 */
public final class ProjectDataDeleteService {
    private final FusekiGateway gateway;
    private final GraphIriRouter router;

    public ProjectDataDeleteService(FusekiGateway gateway, GraphIriRouter router) {
        this.gateway = gateway;
        this.router = router;
    }

    /** Count triples per role for exactly one project without mutating anything. */
    public Map<String, Object> counts(ProjectId project) {
        var graphs = canonicalGraphs(project);
        assertNoForeignProjectGraphs(project, graphs);
        var counts = new LinkedHashMap<String, Object>();
        long total = 0;
        for (var role : GraphRole.values()) {
            long count = countTriples(graphs.get(role));
            counts.put(role.pathSegment(), count);
            total += count;
        }
        counts.put("total", total);
        return counts;
    }

    /**
     * Clear the five canonical graphs of exactly one project.
     *
     * @return per-role removed triple counts plus {@code total}
     */
    public Map<String, Object> delete(ProjectId project) {
        var graphs = canonicalGraphs(project);
        assertNoForeignProjectGraphs(project, graphs);
        var before = new LinkedHashMap<String, Long>();
        long total = 0;
        for (var role : GraphRole.values()) {
            long count = countTriples(graphs.get(role));
            before.put(role.pathSegment(), count);
            total += count;
        }
        if (total == 0) {
            throw new IllegalStateException("project has no semantic state to delete");
        }
        var update = new StringBuilder();
        for (var role : GraphRole.values()) {
            update.append("DELETE WHERE { GRAPH <").append(graphs.get(role)).append("> { ?s ?p ?o } }; ");
        }
        gateway.update(update.toString());
        var removed = new LinkedHashMap<String, Object>();
        long removedTotal = 0;
        for (var role : GraphRole.values()) {
            long after = countTriples(graphs.get(role));
            if (after != 0) {
                throw new IllegalStateException("project graph was not fully cleared");
            }
            removed.put(role.pathSegment(), before.get(role.pathSegment()));
            removedTotal += before.get(role.pathSegment());
        }
        removed.put("total", removedTotal);
        return removed;
    }

    private void assertNoForeignProjectGraphs(ProjectId project, Map<GraphRole, String> graphs) {
        var allowed = String.join(
                ", ", graphs.values().stream().map(graph -> "<" + graph + ">").toList());
        var prefix = "https://w3id.org/projecta/data/project/" + project.value() + "/";
        boolean foreign = gateway.ask("ASK { GRAPH ?graph { ?s ?p ?o } FILTER(STRSTARTS(STR(?graph), "
                + quoted(prefix)
                + ")) FILTER(?graph NOT IN ("
                + allowed
                + ")) }");
        if (foreign) {
            throw new IllegalStateException("project has graphs outside its canonical scope");
        }
    }

    private long countTriples(String graph) {
        var response = gateway.select("SELECT (COUNT(*) AS ?count) WHERE { GRAPH <" + graph + "> { ?s ?p ?o } }");
        try {
            var bindings = new com.fasterxml.jackson.databind.ObjectMapper()
                    .readTree(response)
                    .path("results")
                    .path("bindings");
            if (bindings.size() != 1) {
                throw new IllegalStateException("semantic count response was invalid");
            }
            return Long.parseLong(bindings.get(0).path("count").path("value").asText());
        } catch (IllegalStateException exception) {
            throw exception;
        } catch (Exception exception) {
            throw new IllegalStateException("semantic count response was invalid", exception);
        }
    }

    private Map<GraphRole, String> canonicalGraphs(ProjectId project) {
        var result = new HashMap<GraphRole, String>();
        for (var role : GraphRole.values()) {
            result.put(role, router.route(project, role).toString());
        }
        return result;
    }

    private static String quoted(String value) {
        return "\"" + value.replace("\\", "\\\\").replace("\"", "\\\"") + "\"";
    }
}
