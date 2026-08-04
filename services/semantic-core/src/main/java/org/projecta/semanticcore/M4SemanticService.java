package org.projecta.semanticcore;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Fuseki-backed, typed M4 retrieval and deterministic inferred-state boundary. */
public final class M4SemanticService {
    private static final String PROJECTA = "https://w3id.org/projecta/ontology/";
    private static final String PROV = "http://www.w3.org/ns/prov#";
    private static final String RDFS = "http://www.w3.org/2000/01/rdf-schema#";
    private final FusekiGateway gateway;
    private final GraphIriRouter router;
    private final M4QueryTemplateRegistry registry;
    private final ObjectMapper json = new ObjectMapper();

    public M4SemanticService(FusekiGateway gateway, GraphIriRouter router, M4QueryTemplateRegistry registry) {
        this.gateway = gateway;
        this.router = router;
        this.registry = registry;
    }

    public Map<String, Object> retrieve(ProjectId project, String queryId, Map<String, ?> parameters) {
        registry.validate(queryId, parameters);
        int limit =
                ((Number) (parameters.containsKey("limit") ? parameters.get("limit") : Integer.valueOf(50))).intValue();
        String revisionBefore = snapshotRevision(project);
        String query =
                switch (queryId) {
                    case "current-requirements" -> currentQuery(project, limit);
                    case "requirement-history" ->
                        historyQuery(project, String.valueOf(parameters.get("requirementId")), limit);
                    case "unresolved-blockers" -> blockerQuery(project, limit);
                    default -> throw new IllegalArgumentException("query ID is not allowlisted");
                };
        List<Map<String, String>> resultRows = rows(gateway.select(query));
        String revisionAfter = snapshotRevision(project);
        String inferenceRevision = queryId.equals("unresolved-blockers") ? inferenceSnapshotRevision(project) : null;
        return envelope(queryId, resultRows, revisionAfter, inferenceRevision, !revisionBefore.equals(revisionAfter));
    }

    /** Rebuilds all M4 derivations from asserted data in one Fuseki update request. */
    public Map<String, Object> rebuildInference(ProjectId project) {
        String asserted = router.route(project, GraphRole.ASSERTED).toString();
        String inferred = router.route(project, GraphRole.INFERRED).toString();
        String provenance = router.route(project, GraphRole.PROVENANCE).toString();
        String base = projectIri(project);
        String delete = "DELETE { GRAPH <" + inferred + "> { ?s ?p ?o } GRAPH <" + provenance
                + "> { ?a ?ap ?ao } } WHERE { { GRAPH <" + inferred + "> { ?s ?p ?o } } UNION { GRAPH <"
                + provenance + "> { ?a ?ap ?ao . FILTER(STRSTARTS(STR(?a), \"" + base + "/activity/m4-\")) } } };";
        // Fuseki accepts one request containing several update operations only when each
        // operation is explicitly delimited. Keep the delete-and-rebuild transaction intact.
        String sourceRevision = snapshotRevision(project);
        String update = delete + snapshotMarker(inferred, base, sourceRevision) + ";"
                + unresolvedRule(asserted, inferred, provenance, base, sourceRevision) + ";"
                + deliveryRiskRule(asserted, inferred, provenance, base, sourceRevision) + ";"
                + impactRule(asserted, inferred, provenance, base, sourceRevision);
        gateway.update(update);
        String ruleQuery = "SELECT DISTINCT ?ruleIdentifier WHERE { GRAPH <" + inferred + "> { ?item <" + PROJECTA
                + "ruleIdentifier> ?ruleIdentifier } } ORDER BY ?ruleIdentifier";
        List<String> rules = rows(gateway.select(ruleQuery)).stream()
                .map(row -> row.get("ruleIdentifier"))
                .filter(value -> value != null)
                .toList();
        return Map.of(
                "ruleVersion",
                "m4.v1",
                "rebuiltAt",
                OffsetDateTime.now().toString(),
                "projectId",
                project.value(),
                "sourceRevision",
                sourceRevision,
                "materializationRevision",
                materializationRevision(project),
                "materializedRuleIds",
                rules);
    }

    private String snapshotMarker(String inferred, String base, String sourceRevision) {
        return "INSERT DATA { GRAPH <" + inferred + "> { <" + base + "/inferred/snapshot-m4-v1> a <"
                + PROJECTA + "InferenceSnapshot> ; <" + PROJECTA + "belongsToProject> <" + base + "> ; <"
                + PROJECTA + "sourceRevision> \"" + sourceRevision + "\" ; <" + PROJECTA
                + "ruleVersion> \"m4.v1\" . } }";
    }

    private String unresolvedRule(
            String asserted, String inferred, String provenance, String base, String sourceRevision) {
        return ("""
                INSERT { GRAPH <%s> { ?derived a <%sUnresolvedBlocker> ; <%saboutTask> ?task ; <%sderivedFromAssertion> ?question, ?task ; <%sbelongsToProject> <%s> ; <%ssourceRevision> "%%SOURCE_REVISION%%" ; <%sruleIdentifier> "m4.unresolved-dependency" ; <%sruleVersion> "1" ; <%slabel> ?label . } GRAPH <%s> { ?activity a <%sActivity> ; <%sused> ?question, ?task ; <%sgenerated> ?derived ; <%sruleIdentifier> "m4.unresolved-dependency" ; <%sruleVersion> "1" ; <%sbelongsToProject> <%s> . } }
                WHERE { GRAPH <%s> { ?question a <%sQuestion> ; <%sblocks> ?task ; <%slabel> ?label ; <%shasWorkStatus> <%sOpen> . ?task a <%sTask> . } BIND(IRI(CONCAT("%s/inferred/unresolved-blocker-", ENCODE_FOR_URI(STRAFTER(STR(?question), "/question/")), "-", ENCODE_FOR_URI(STRAFTER(STR(?task), "/task/")))) AS ?derived) BIND(IRI(CONCAT("%s/activity/m4-unresolved-", ENCODE_FOR_URI(STRAFTER(STR(?derived), "/inferred/")))) AS ?activity) }
                """)
                .formatted(
                        inferred,
                        PROJECTA,
                        PROJECTA,
                        PROJECTA,
                        PROJECTA,
                        base,
                        PROJECTA,
                        PROJECTA,
                        PROJECTA,
                        RDFS,
                        provenance,
                        PROV,
                        PROV,
                        PROV,
                        PROJECTA,
                        PROJECTA,
                        PROJECTA,
                        base,
                        asserted,
                        PROJECTA,
                        PROJECTA,
                        RDFS,
                        PROJECTA,
                        PROJECTA,
                        PROJECTA,
                        base,
                        base)
                .replace("%SOURCE_REVISION%", sourceRevision);
    }

    private String deliveryRiskRule(
            String asserted, String inferred, String provenance, String base, String sourceRevision) {
        return ("""
                INSERT { GRAPH <%s> { ?derived a <%sDeliveryRisk> ; <%saboutTask> ?task ; <%sderivedFromAssertion> ?task, ?requirement ; <%sbelongsToProject> <%s> ; <%ssourceRevision> "%%SOURCE_REVISION%%" ; <%sruleIdentifier> "m4.delivery-risk" ; <%sruleVersion> "1" ; <%slabel> ?label . } GRAPH <%s> { ?activity a <%sActivity> ; <%sused> ?task, ?requirement ; <%sgenerated> ?derived ; <%sruleIdentifier> "m4.delivery-risk" ; <%sruleVersion> "1" ; <%sbelongsToProject> <%s> . } }
                WHERE { GRAPH <%s> { ?task a <%sTask> ; <%shasWorkStatus> <%sBlocked> ; <%simplements> ?requirement . ?requirement a <%sRequirement> ; <%slabel> ?label . } BIND(IRI(CONCAT("%s/inferred/delivery-risk-", ENCODE_FOR_URI(STRAFTER(STR(?requirement), "/requirement/")))) AS ?derived) BIND(IRI(CONCAT("%s/activity/m4-delivery-", ENCODE_FOR_URI(STRAFTER(STR(?derived), "/inferred/")))) AS ?activity) }
                """)
                .formatted(
                        inferred,
                        PROJECTA,
                        PROJECTA,
                        PROJECTA,
                        PROJECTA,
                        base,
                        PROJECTA,
                        PROJECTA,
                        PROJECTA,
                        RDFS,
                        provenance,
                        PROV,
                        PROV,
                        PROV,
                        PROJECTA,
                        PROJECTA,
                        PROJECTA,
                        base,
                        asserted,
                        PROJECTA,
                        PROJECTA,
                        PROJECTA,
                        PROJECTA,
                        PROJECTA,
                        RDFS,
                        base,
                        base)
                .replace("%SOURCE_REVISION%", sourceRevision);
    }

    private String impactRule(String asserted, String inferred, String provenance, String base, String sourceRevision) {
        return ("""
                INSERT { GRAPH <%s> { ?derived a <%sImpactReview> ; <%saboutTask> ?task ; <%sderivedFromAssertion> ?old, ?task ; <%sbelongsToProject> <%s> ; <%ssourceRevision> "%%SOURCE_REVISION%%" ; <%sruleIdentifier> "m4.impact-review" ; <%sruleVersion> "1" ; <%slabel> ?label . } GRAPH <%s> { ?activity a <%sActivity> ; <%sused> ?old, ?task ; <%sgenerated> ?derived ; <%sruleIdentifier> "m4.impact-review" ; <%sruleVersion> "1" ; <%sbelongsToProject> <%s> . } }
                WHERE { GRAPH <%s> { ?old a <%sRequirement> ; <%ssupersededBy> ?replacement ; <%slabel> ?label . ?task a <%sTask> ; <%simplements> ?old . } BIND(IRI(CONCAT("%s/inferred/impact-review-", ENCODE_FOR_URI(STRAFTER(STR(?old), "/requirement/")), "-", ENCODE_FOR_URI(STRAFTER(STR(?task), "/task/")))) AS ?derived) BIND(IRI(CONCAT("%s/activity/m4-impact-", ENCODE_FOR_URI(STRAFTER(STR(?derived), "/inferred/")))) AS ?activity) }
                """)
                .formatted(
                        inferred,
                        PROJECTA,
                        PROJECTA,
                        PROJECTA,
                        PROJECTA,
                        base,
                        PROJECTA,
                        PROJECTA,
                        PROJECTA,
                        RDFS,
                        provenance,
                        PROV,
                        PROV,
                        PROV,
                        PROJECTA,
                        PROJECTA,
                        PROJECTA,
                        base,
                        asserted,
                        PROJECTA,
                        PROJECTA,
                        RDFS,
                        PROJECTA,
                        PROJECTA,
                        base,
                        base)
                .replace("%SOURCE_REVISION%", sourceRevision);
    }

    private String currentQuery(ProjectId project, int limit) {
        return assertedEvidenceQuery(
                project,
                "?item a <" + PROJECTA + "Requirement> ; <" + RDFS + "label> ?label ; <" + PROJECTA
                        + "validFrom> ?validFrom . FILTER NOT EXISTS { ?item <" + PROJECTA + "validTo> ?validTo }",
                "ORDER BY DESC(?validFrom) ?item",
                limit);
    }

    private String historyQuery(ProjectId project, String id, int limit) {
        if (!id.matches("[a-z0-9][a-z0-9-]{0,62}")) throw new IllegalArgumentException("requirement ID is invalid");
        String target = projectIri(project) + "/requirement/" + id;
        return assertedEvidenceQuery(
                project,
                "?item a <" + PROJECTA + "Requirement> ; <" + RDFS + "label> ?label ; <" + PROJECTA
                        + "validFrom> ?validFrom . FILTER(?item = <" + target + "> || EXISTS { ?item (<" + PROJECTA
                        + "supersededBy>|^<" + PROJECTA + "supersededBy>)* <" + target + "> })",
                "ORDER BY ?validFrom ?item",
                limit);
    }

    private String blockerQuery(ProjectId project, int limit) {
        return inferredEvidenceQuery(
                project,
                "?item a <" + PROJECTA + "UnresolvedBlocker> ; <" + RDFS + "label> ?label ; <" + PROJECTA
                        + "ruleIdentifier> ?ruleIdentifier ; <" + PROJECTA + "ruleVersion> ?ruleVersion ; <" + PROJECTA
                        + "derivedFromAssertion> ?input",
                "ORDER BY ?item",
                limit);
    }

    private String assertedEvidenceQuery(ProjectId project, String body, String order, int limit) {
        return evidenceQuery(project, router.route(project, GraphRole.ASSERTED).toString(), body, order, limit);
    }

    private String inferredEvidenceQuery(ProjectId project, String body, String order, int limit) {
        return evidenceQuery(project, router.route(project, GraphRole.INFERRED).toString(), body, order, limit);
    }

    private String evidenceQuery(ProjectId project, String graph, String body, String order, int limit) {
        return "SELECT ?item ?label ?validFrom ?ruleIdentifier ?ruleVersion ?input ?source ?sourceText ?startOffset ?endOffset WHERE { GRAPH <"
                + graph + "> { " + body + " } OPTIONAL { { GRAPH <" + router.route(project, GraphRole.ASSERTED)
                + "> { ?item <" + PROV + "wasDerivedFrom> ?candidate . } } UNION { GRAPH <" + graph
                + "> { ?item <" + PROJECTA + "derivedFromAssertion> ?assertion . } GRAPH <"
                + router.route(project, GraphRole.ASSERTED)
                + "> { ?assertion <" + PROV + "wasDerivedFrom> ?candidate . } } GRAPH <"
                + router.route(project, GraphRole.CANDIDATES)
                + "> { ?candidate <" + PROV + "wasDerivedFrom> ?source . } GRAPH <"
                + router.route(project, GraphRole.SOURCES)
                + "> { ?source <" + PROJECTA + "contentText> ?sourceText ; <" + PROJECTA
                + "evidenceStartOffset> ?startOffset ; <"
                + PROJECTA + "evidenceEndOffset> ?endOffset . } } } " + order + " LIMIT " + limit;
    }

    private Map<String, Object> envelope(
            String queryId,
            List<Map<String, String>> rows,
            String sourceRevision,
            String inferenceRevision,
            boolean partial) {
        var itemMap = new LinkedHashMap<String, Map<String, Object>>();
        var citations = new ArrayList<Map<String, Object>>();
        for (var row : rows) {
            String id = opaque(row.get("item"));
            var item = itemMap.computeIfAbsent(id, ignored -> new LinkedHashMap<>());
            item.put("id", id);
            item.put("type", queryId.equals("unresolved-blockers") ? "UnresolvedBlocker" : "Requirement");
            item.put("label", row.getOrDefault("label", ""));
            item.put("status", queryId.equals("unresolved-blockers") ? "inferred" : "asserted");
            if (row.containsKey("validFrom")) item.put("asOf", row.get("validFrom"));
            if (row.containsKey("ruleIdentifier")) {
                var existing = item.get("derivation");
                var inputs = new ArrayList<String>();
                if (existing instanceof Map<?, ?> previous && previous.get("inputIds") instanceof List<?> oldInputs) {
                    oldInputs.forEach(value -> inputs.add(String.valueOf(value)));
                }
                if (row.containsKey("input")) inputs.add(opaque(row.get("input")));
                item.put(
                        "derivation",
                        Map.of(
                                "ruleId",
                                row.get("ruleIdentifier"),
                                "ruleVersion",
                                row.getOrDefault("ruleVersion", "1"),
                                "inputIds",
                                inputs.stream().distinct().toList()));
            }
            if (row.containsKey("source")
                    && row.containsKey("sourceText")
                    && row.containsKey("startOffset")
                    && row.containsKey("endOffset")) {
                String citationId =
                        "evidence-" + sha256(id + "|" + row.get("source")).substring(0, 54);
                var citation = Map.<String, Object>of(
                        "id",
                        citationId,
                        "sourceId",
                        opaque(row.get("source")),
                        "evidenceText",
                        row.get("sourceText"),
                        "startOffset",
                        Integer.parseInt(row.get("startOffset")),
                        "endOffset",
                        Integer.parseInt(row.get("endOffset")));
                var citationIds = new ArrayList<String>();
                if (item.get("citationIds") instanceof List<?> oldIds)
                    oldIds.forEach(value -> citationIds.add(String.valueOf(value)));
                citationIds.add(citationId);
                item.put("citationIds", citationIds.stream().distinct().toList());
                var itemCitations = new ArrayList<Map<String, Object>>();
                if (item.get("citations") instanceof List<?> oldCitations) {
                    oldCitations.forEach(value -> {
                        if (value instanceof Map<?, ?> oldCitation) {
                            var typed = new LinkedHashMap<String, Object>();
                            oldCitation.forEach((key, value2) -> typed.put(String.valueOf(key), value2));
                            itemCitations.add(typed);
                        }
                    });
                }
                itemCitations.add(citation);
                item.put("citations", itemCitations);
                citations.add(citation);
            }
        }
        var items = new ArrayList<>(itemMap.values());
        boolean stale = partial
                || (queryId.equals("unresolved-blockers")
                        && (inferenceRevision == null || !sourceRevision.equals(inferenceRevision)));
        return Map.of(
                "items", items,
                "citations", citations,
                "meta",
                        Map.of(
                                "projectionVersion", "m4.v1",
                                "sourceRevision", sourceRevision,
                                "asOf", latestAsOf(rows),
                                "partial", partial,
                                "stale", stale));
    }

    private String latestAsOf(List<Map<String, String>> rows) {
        return rows.stream()
                .map(row -> row.get("validFrom"))
                .filter(value -> value != null && !value.isBlank())
                .findFirst()
                .orElseGet(() -> OffsetDateTime.now().toString());
    }

    /** A measured, stable revision over every RDF term in the asserted graph. */
    private String snapshotRevision(ProjectId project) {
        return "fuseki-"
                + graphRevision(router.route(project, GraphRole.ASSERTED).toString());
    }

    private String inferenceSnapshotRevision(ProjectId project) {
        String inferred = router.route(project, GraphRole.INFERRED).toString();
        String query = "SELECT ?sourceRevision WHERE { GRAPH <" + inferred + "> { <" + projectIri(project)
                + "/inferred/snapshot-m4-v1> a <" + PROJECTA + "InferenceSnapshot> ; <" + PROJECTA
                + "sourceRevision> ?sourceRevision ; <" + PROJECTA + "ruleVersion> \"m4.v1\" . } }";
        List<Map<String, String>> result = rows(gateway.select(query));
        return result.size() == 1 ? result.getFirst().get("sourceRevision") : null;
    }

    private String materializationRevision(ProjectId project) {
        String inferred =
                graphRevision(router.route(project, GraphRole.INFERRED).toString());
        String provenance =
                graphRevision(router.route(project, GraphRole.PROVENANCE).toString());
        return "fuseki-" + sha256(inferred + "|" + provenance);
    }

    private String graphRevision(String graphIri) {
        String query = "SELECT ?s ?p ?o WHERE { GRAPH <" + graphIri + "> { ?s ?p ?o } }";
        try {
            var triples = new ArrayList<String>();
            for (JsonNode binding :
                    json.readTree(gateway.select(query)).path("results").path("bindings")) {
                triples.add(termKey(binding.path("s")) + " " + termKey(binding.path("p")) + " "
                        + termKey(binding.path("o")));
            }
            triples.sort(Comparator.naturalOrder());
            return sha256(String.join("\n", triples));
        } catch (Exception exception) {
            throw new IllegalStateException("semantic graph revision response was invalid", exception);
        }
    }

    private String termKey(JsonNode term) {
        return term.path("type").asText() + "|" + term.path("value").asText() + "|"
                + term.path("datatype").asText() + "|" + term.path("xml:lang").asText();
    }

    private List<Map<String, String>> rows(String body) {
        try {
            var result = new ArrayList<Map<String, String>>();
            for (JsonNode row : json.readTree(body).path("results").path("bindings")) {
                var values = new LinkedHashMap<String, String>();
                row.fields()
                        .forEachRemaining(entry -> values.put(
                                entry.getKey(), entry.getValue().path("value").asText()));
                result.add(values);
            }
            return result;
        } catch (Exception exception) {
            throw new IllegalStateException("semantic store response was invalid", exception);
        }
    }

    private String projectIri(ProjectId project) {
        return "https://w3id.org/projecta/data/project/" + project.value();
    }

    private String opaque(String iri) {
        if (iri == null) return "id-unknown";
        return "id-" + sha256(iri).substring(0, 56);
    }

    private String sha256(String value) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8));
            StringBuilder result = new StringBuilder(digest.length * 2);
            for (byte item : digest) result.append(String.format("%02x", item));
            return result.toString();
        } catch (Exception exception) {
            throw new IllegalStateException("SHA-256 is unavailable", exception);
        }
    }
}
