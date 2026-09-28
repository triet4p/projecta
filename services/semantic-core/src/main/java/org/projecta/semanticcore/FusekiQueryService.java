package org.projecta.semanticcore;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.security.MessageDigest;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

/** Finite read and validation views backed by Fuseki; no client SPARQL crosses this boundary. */
public final class FusekiQueryService {
    private static final String PROJECTA = "https://w3id.org/projecta/ontology/";
    private static final String PROV = "http://www.w3.org/ns/prov#";
    private final FusekiGateway gateway;
    private final GraphIriRouter router;
    private final RemoteCandidateValidationService validation;
    private final ObjectMapper json = new ObjectMapper();

    public FusekiQueryService(
            FusekiGateway gateway, GraphIriRouter router, RemoteCandidateValidationService validation) {
        this.gateway = gateway;
        this.router = router;
        this.validation = validation;
    }

    /** Validates one candidate in the trusted project's candidates graph. */
    public CandidateValidationResult validate(ProjectId project, String candidateId) {
        candidate(project, candidateId);
        return validation.validate(project, candidateId);
    }

    /** Validates and atomically promotes one conforming extracted candidate. */
    public CandidateValidationResult validateAndMarkValidated(ProjectId project, String candidateId, String actorId) {
        var result = validate(project, candidateId);
        if (result.conforms()) {
            markValidated(project, candidateId, actorId);
        }
        return result;
    }

    /** Marks a conforming extracted candidate ready for the released human-review operations. */
    public void markValidated(ProjectId project, String candidateId, String actorId) {
        var candidate = candidate(project, candidateId);
        if (actorId == null || !actorId.matches("[a-z0-9][a-z0-9-]{0,62}")) {
            throw new IllegalArgumentException("actor ID is invalid");
        }
        var projectIri = "https://w3id.org/projecta/data/project/" + project.value();
        var activity = projectIri + "/activity/validate-" + UUID.randomUUID();
        gateway.update("""
                DELETE { GRAPH <%s> { <%s> <%scandidateStatus> <%sextracted> } }
                INSERT {
                  GRAPH <%s> { <%s> <%scandidateStatus> <%svalidated> }
                  GRAPH <%s> { <%s> a <http://www.w3.org/ns/prov#Activity> ;
                    <http://www.w3.org/ns/prov#used> <%s> ;
                    <http://www.w3.org/ns/prov#wasAssociatedWith> <%s> ;
                    <http://www.w3.org/ns/prov#endedAtTime> "%s"^^<http://www.w3.org/2001/XMLSchema#dateTime> ;
                    <https://w3id.org/projecta/ontology/belongsToProject> <%s> ;
                    <http://www.w3.org/2000/01/rdf-schema#label> "candidate-validation" . }
                }
                WHERE { GRAPH <%s> { <%s> a <%sCandidate> ; <%scandidateStatus> <%sextracted> . } }
                """.formatted(
                        router.route(project, GraphRole.CANDIDATES),
                        candidate,
                        PROJECTA,
                        PROJECTA,
                        router.route(project, GraphRole.CANDIDATES),
                        candidate,
                        PROJECTA,
                        PROJECTA,
                        router.route(project, GraphRole.PROVENANCE),
                        activity,
                        candidate,
                        "https://w3id.org/projecta/data/project/" + project.value() + "/person/" + actorId,
                        OffsetDateTime.now(),
                        projectIri,
                        router.route(project, GraphRole.CANDIDATES),
                        candidate,
                        PROJECTA,
                        PROJECTA,
                        PROJECTA));
    }

    /** Returns the finite current-knowledge view, optionally restricted to an allowlisted type. */
    public List<Map<String, String>> current(ProjectId project, String type) {
        if (type != null && !type.equals("Requirement"))
            throw new IllegalArgumentException("knowledge-item type is not allowlisted");
        var filter = type == null ? "" : " ; a <" + PROJECTA + type + ">";
        return rows(gateway.select("SELECT ?item ?label ?validFrom WHERE { GRAPH <"
                + router.route(project, GraphRole.ASSERTED) + "> { ?item a <" + PROJECTA + "KnowledgeItem>" + filter
                + " ; <http://www.w3.org/2000/01/rdf-schema#label> ?label ; <" + PROJECTA
                + "validFrom> ?validFrom . } }"));
    }

    /** Returns a bounded allowlisted entity context for same-project link proposals. */
    public List<Map<String, String>> entityLinkContext(ProjectId project, int limit) {
        if (limit < 1 || limit > 100) {
            throw new IllegalArgumentException("entity link context limit must be between 1 and 100");
        }
        var projectIri = "https://w3id.org/projecta/data/project/" + project.value();
        var rows = rows(gateway.select("SELECT DISTINCT ?entity ?type ?label WHERE { GRAPH <"
                + router.route(project, GraphRole.ASSERTED)
                + "> { ?entity <" + PROJECTA + "belongsToProject> <" + projectIri
                + "> ; a ?type ; <http://www.w3.org/2000/01/rdf-schema#label> ?label . VALUES ?type { <" + PROJECTA
                + "Requirement> <" + PROJECTA + "Decision> <" + PROJECTA + "Question> <" + PROJECTA
                + "Risk> <" + PROJECTA + "Assumption> <" + PROJECTA + "Constraint> <" + PROJECTA
                + "ResearchFinding> <" + PROJECTA + "Task> <" + PROJECTA + "ProgressClaim> <" + PROJECTA + "Person> <"
                + PROJECTA + "Team> } } } ORDER BY ?entity LIMIT " + limit));
        return rows.stream()
                .map(row -> Map.of(
                        "id", opaqueIdentifier(row.get("type")) + "--" + opaqueIdentifier(row.get("entity")),
                        "type", opaqueIdentifier(row.get("type")),
                        "label", row.get("label")))
                .toList();
    }

    /** Returns ordered reviewer decisions that used the specified project-scoped candidate. */
    public List<Map<String, String>> history(ProjectId project, String candidateId) {
        return rows(gateway.select("SELECT ?activity ?decision ?reviewer ?endedAt WHERE { GRAPH <"
                + router.route(project, GraphRole.PROVENANCE) + "> { ?activity <" + PROV + "used> <"
                + candidate(project, candidateId) + "> ; <" + PROJECTA + "reviewDecision> ?decision ; <" + PROV
                + "wasAssociatedWith> ?reviewer ; <" + PROV + "endedAtTime> ?endedAt . } } ORDER BY ?endedAt"));
    }

    /** Returns the asserted-item-to-candidate-to-exact-source reviewer evidence chain. */
    public List<Map<String, String>> evidence(ProjectId project, String itemId) {
        var item = "https://w3id.org/projecta/data/project/" + project.value() + "/requirement/" + itemId;
        return rows(gateway.select(
                "SELECT ?candidate ?source ?note ?rawText ?sourceText ?startOffset ?endOffset ?author ?reviewer WHERE { GRAPH <"
                        + router.route(project, GraphRole.ASSERTED)
                        + "> { <" + item + "> <" + PROV + "wasDerivedFrom> ?candidate ; <" + PROV
                        + "wasAttributedTo> ?reviewer . } GRAPH <" + router.route(project, GraphRole.CANDIDATES)
                        + "> { ?candidate <" + PROV + "wasDerivedFrom> ?source . } GRAPH <"
                        + router.route(project, GraphRole.SOURCES) + "> { ?source <" + PROJECTA
                        + "isItemOf> ?note ; <" + PROJECTA + "contentText> ?sourceText ; <" + PROJECTA
                        + "evidenceStartOffset> ?startOffset ; <" + PROJECTA + "evidenceEndOffset> ?endOffset . ?note <"
                        + PROJECTA + "rawText> ?rawText ; <" + PROJECTA + "authoredBy> ?author . } }"));
    }

    /** Returns a deterministic, bounded graph projection with no RDF identifiers in its payload. */
    public Map<String, Object> graph(ProjectId project, int nodeLimit, int edgeLimit) {
        if (nodeLimit < 1 || nodeLimit > 100 || edgeLimit < 1 || edgeLimit > 200) {
            throw new IllegalArgumentException("graph limits are outside the released bounds");
        }
        var nodeRows = rows(gateway.select(graphNodeQuery(project, nodeLimit + 1)));
        var hasMore = nodeRows.size() > nodeLimit;
        var visibleRows = nodeRows.stream().limit(nodeLimit).toList();
        var nodes = new ArrayList<Map<String, Object>>();
        var visibleResources = new LinkedHashSet<String>();
        for (var row : visibleRows) {
            var resource = row.get("resource");
            if (resource == null || !visibleResources.add(resource)) continue;
            nodes.add(node(
                    resource,
                    required(row, "label"),
                    required(row, "type"),
                    required(row, "verificationState"),
                    required(row, "lifecycleState"),
                    required(row, "provenanceState")));
        }
        var edges = graphEdges(project, visibleResources, edgeLimit);
        var result = new LinkedHashMap<String, Object>();
        result.put("projectionVersion", "s8.graph.v1");
        result.put("sourceRevision", "source-" + opaqueHandle(project.value()));
        result.put("materializationRevision", "materialized-" + opaqueHandle(project.value()));
        result.put("asOf", OffsetDateTime.now().toString());
        result.put("stale", false);
        result.put("partial", false);
        result.put("nodes", nodes);
        result.put("edges", edges.items());
        var page = new LinkedHashMap<String, Object>();
        page.put("nodeLimit", nodeLimit);
        page.put("edgeLimit", edgeLimit);
        page.put("hasMore", hasMore || edges.hasMore());
        page.put("continuation", null);
        page.put("expansionAvailable", !nodes.isEmpty());
        result.put("page", page);
        result.put(
                "filters",
                Map.of(
                        "semanticTypes", List.of(),
                        "verificationStates", List.of(),
                        "lifecycleStates", List.of(),
                        "provenanceStates", List.of(),
                        "relationTypes", List.of(),
                        "evidence", "any"));
        return result;
    }

    /** Returns one bounded hop from a returned graph handle. */
    public Map<String, Object> neighborhood(ProjectId project, String nodeHandle, int edgeLimit) {
        var graph = graph(project, 50, edgeLimit);
        var nodes = castList(graph.get("nodes"));
        if (nodes.stream().noneMatch(item -> nodeHandle.equals(((Map<?, ?>) item).get("handle")))) {
            throw new ProjectScopedQueryService.ResourceNotFoundException("graph node is not visible in this project");
        }
        return graph;
    }

    /** Returns bounded node detail from the same project projection. */
    public Map<String, Object> nodeDetail(ProjectId project, String nodeHandle) {
        var graph = graph(project, 100, 200);
        for (var item : castList(graph.get("nodes"))) {
            var node = (Map<?, ?>) item;
            if (nodeHandle.equals(node.get("handle"))) {
                var detail = new LinkedHashMap<String, Object>();
                detail.putAll((Map<String, Object>) node);
                detail.put("projectLabel", "Active project");
                detail.put("freshness", "available");
                detail.put("relations", List.of());
                detail.put("evidence", List.of());
                detail.put("lifecycle", List.of());
                return detail;
            }
        }
        throw new ProjectScopedQueryService.ResourceNotFoundException("graph node is not visible in this project");
    }

    public Map<String, Object> graphLinks(ProjectId project, String nodeHandle, String link) {
        nodeDetail(project, nodeHandle);
        return Map.of("projectionVersion", "s8.graph.v1", "stale", false, "items", List.of(), "linkType", link);
    }

    /** Returns a bounded, label-first candidate queue for the selected project. */
    public Map<String, Object> candidates(ProjectId project, int limit) {
        if (limit < 1 || limit > 100) {
            throw new IllegalArgumentException("candidate limit is outside the released bounds");
        }
        var rows = rows(gateway.select(manualAndEntityCandidateQuery(project, limit + 1)));
        var result = new ArrayList<Map<String, Object>>();
        for (var row : rows.stream().limit(limit).toList()) {
            result.add(Map.of(
                    "handle",
                    "candidate-h-" + opaqueHandle(row.get("candidate")),
                    "label",
                    required(row, "label"),
                    "proposedType",
                    localName(row.get("type")),
                    "proposedRelations",
                    List.of(),
                    "validationState",
                    localName(row.get("status")),
                    "lifecycleState",
                    "pending-review",
                    "confidence",
                    0.0,
                    "evidenceCount",
                    0));
        }
        return Map.of(
                "sourceRevision",
                "source-" + opaqueHandle(project.value()),
                "stale",
                false,
                "candidates",
                result,
                "hasMore",
                rows.size() > limit);
    }

    /** Returns the immutable manual Note evidence bound to a same-project candidate. */
    public Map<String, Object> manualCaptureSourceContext(ProjectId project, String candidateId) {
        var candidateIri = candidate(project, candidateId);
        var projectIri = "https://w3id.org/projecta/data/project/" + project.value();
        var sourceRows = rows(gateway.select("""
                SELECT ?status ?generator ?note ?title ?rawText ?sourceText ?itemType ?startOffset ?endOffset
                WHERE {
                  GRAPH <%s> {
                    <%s> a <%sCandidate> ; <%scandidateStatus> ?status ; <%sgenerator> ?generator ;
                      <http://www.w3.org/ns/prov#wasDerivedFrom> ?source ;
                      <%sbelongsToProject> <%s> .
                  }
                  FILTER(?generator = "manual-quick-note-v0.3.0")
                  GRAPH <%s> {
                    ?source <%sisItemOf> ?note ; <%scontentText> ?sourceText ;
                      <%shasItemType> ?itemType ; <%sevidenceStartOffset> ?startOffset ;
                      <%sevidenceEndOffset> ?endOffset .
                    ?note a <%sNote> ; <%sbelongsToProject> <%s> ; <%sname> ?title ; <%srawText> ?rawText .
                  }
                }
                """.formatted(
                        router.route(project, GraphRole.CANDIDATES),
                        candidateIri,
                        PROJECTA,
                        PROJECTA,
                        PROJECTA,
                        PROJECTA,
                        projectIri,
                        router.route(project, GraphRole.SOURCES),
                        PROJECTA,
                        PROJECTA,
                        PROJECTA,
                        PROJECTA,
                        PROJECTA,
                        PROJECTA,
                        PROJECTA,
                        projectIri,
                        PROJECTA,
                        PROJECTA)));
        if (sourceRows.size() != 1) {
            throw new ProjectScopedQueryService.ResourceNotFoundException(
                    "manual candidate source is not uniquely visible in this project");
        }
        var row = sourceRows.getFirst();
        var result = new LinkedHashMap<String, Object>();
        result.put("candidateId", candidateId);
        result.put("candidateRevision", 1);
        result.put("candidateStatus", localName(required(row, "status")));
        result.put("sourceArtifactId", localName(required(row, "note")));
        result.put("title", required(row, "title"));
        result.put("rawText", required(row, "rawText"));
        result.put("evidenceText", required(row, "sourceText"));
        result.put("entityType", entityType(localName(required(row, "itemType"))));
        result.put("startOffset", Integer.parseInt(required(row, "startOffset")));
        result.put("endOffset", Integer.parseInt(required(row, "endOffset")));
        return result;
    }

    /** Returns the finite current knowledge collection using opaque handles. */
    public Map<String, Object> knowledge(ProjectId project, int limit) {
        if (limit < 1 || limit > 100) {
            throw new IllegalArgumentException("knowledge limit is outside the released bounds");
        }
        var current = current(project, "Requirement");
        var items = current.stream()
                .limit(limit)
                .map(row -> Map.<String, Object>of(
                        "handle",
                        "knowledge-h-" + opaqueHandle(row.get("item")),
                        "label",
                        required(row, "label"),
                        "semanticType",
                        "Requirement",
                        "lifecycleState",
                        "current",
                        "verificationState",
                        "asserted",
                        "provenanceState",
                        "source-backed",
                        "validFrom",
                        required(row, "validFrom"),
                        "evidenceCount",
                        0))
                .toList();
        return Map.of(
                "sourceRevision",
                "source-" + opaqueHandle(project.value()),
                "stale",
                false,
                "items",
                items,
                "hasMore",
                current.size() > limit);
    }

    /** Returns a bounded title-first source Note collection with derived item summaries. */
    public Map<String, Object> notes(ProjectId project, int limit) {
        if (limit < 1 || limit > 100) {
            throw new IllegalArgumentException("Note limit is outside the released bounds");
        }
        var noteRows = rows(gateway.select("SELECT DISTINCT ?note ?title ?author ?recordedAt WHERE { GRAPH <"
                + router.route(project, GraphRole.SOURCES)
                + "> { ?note a <" + PROJECTA + "Note> ; <" + PROJECTA + "name> ?title ; <" + PROJECTA
                + "authoredBy> ?author ; <" + PROJECTA
                + "recordedAt> ?recordedAt . } } ORDER BY DESC(?recordedAt) ?note LIMIT "
                + (limit + 1)));
        var notes = new ArrayList<Map<String, Object>>();
        for (var row : noteRows.stream().limit(limit).toList()) {
            var noteIri = row.get("note");
            var itemRows = rows(gateway.select("SELECT ?type ?start ?end WHERE { GRAPH <"
                    + router.route(project, GraphRole.SOURCES)
                    + "> { ?item <" + PROJECTA + "isItemOf> <" + noteIri + "> ; <" + PROJECTA
                    + "hasItemType> ?type ; <" + PROJECTA + "evidenceStartOffset> ?start ; <" + PROJECTA
                    + "evidenceEndOffset> ?end . } } ORDER BY ?start"));
            var types = new LinkedHashSet<String>();
            var covered = 0;
            for (var item : itemRows) {
                types.add(localName(item.get("type")));
                if (item.get("start") != null && item.get("end") != null) covered++;
            }
            notes.add(Map.of(
                    "noteHandle", "note-h-" + opaqueHandle(noteIri),
                    "title", required(row, "title"),
                    "author", localName(row.get("author")),
                    "recordedAt", required(row, "recordedAt"),
                    "itemTypeSummary", List.copyOf(types),
                    "candidateState", "source-only",
                    "evidenceCoverage", itemRows.isEmpty() ? 0.0 : ((double) covered / itemRows.size())));
        }
        return Map.of(
                "sourceRevision",
                "source-" + opaqueHandle(project.value()),
                "stale",
                false,
                "notes",
                notes,
                "hasMore",
                noteRows.size() > limit);
    }

    /** Returns one structured source Note after resolving a previously emitted opaque handle. */
    public Map<String, Object> note(ProjectId project, String handle) {
        var noteIri = resolveNoteHandle(project, handle);
        var noteRows = rows(gateway.select("SELECT ?title ?rawText ?author ?recordedAt WHERE { GRAPH <"
                + router.route(project, GraphRole.SOURCES)
                + "> { <" + noteIri + "> <" + PROJECTA + "name> ?title ; <" + PROJECTA + "rawText> ?rawText ; <"
                + PROJECTA + "authoredBy> ?author ; <" + PROJECTA + "recordedAt> ?recordedAt . } }"));
        if (noteRows.isEmpty()) {
            throw new ProjectScopedQueryService.ResourceNotFoundException("Note handle is not visible in this project");
        }
        var itemRows = rows(gateway.select("SELECT ?type ?content ?start ?end WHERE { GRAPH <"
                + router.route(project, GraphRole.SOURCES)
                + "> { ?item <" + PROJECTA + "isItemOf> <" + noteIri + "> ; <" + PROJECTA + "hasItemType> ?type ; <"
                + PROJECTA + "contentText> ?content ; <" + PROJECTA + "evidenceStartOffset> ?start ; <" + PROJECTA
                + "evidenceEndOffset> ?end . } } ORDER BY ?start"));
        var first = noteRows.get(0);
        var items = itemRows.stream()
                .map(item -> Map.<String, Object>of(
                        "itemType", localName(item.get("type")),
                        "content", required(item, "content"),
                        "startOffset", Integer.parseInt(required(item, "start")),
                        "endOffset", Integer.parseInt(required(item, "end"))))
                .toList();
        return Map.of(
                "noteHandle",
                handle,
                "title",
                required(first, "title"),
                "rawText",
                required(first, "rawText"),
                "author",
                localName(first.get("author")),
                "recordedAt",
                required(first, "recordedAt"),
                "items",
                items,
                "evidenceCoverage",
                itemRows.isEmpty() ? 0.0 : 1.0,
                "candidateState",
                "source-only");
    }

    /** Resolves only a handle previously emitted by the Note projection. */
    public String resolveNoteHandle(ProjectId project, String handle) {
        if (handle == null || !handle.startsWith("note-h-")) {
            throw new IllegalArgumentException("Note handle is invalid");
        }
        var rows =
                rows(gateway.select("SELECT DISTINCT ?note WHERE { GRAPH <" + router.route(project, GraphRole.SOURCES)
                        + "> { ?note a <" + PROJECTA + "Note> . } } ORDER BY ?note"));
        return rows.stream()
                .map(row -> row.get("note"))
                .filter(resource -> ("note-h-" + opaqueHandle(resource)).equals(handle))
                .findFirst()
                .orElseThrow(() -> new ProjectScopedQueryService.ResourceNotFoundException(
                        "Note handle is not visible in this project"));
    }

    /** Resolves only a handle previously emitted by the bounded candidate projection. */
    public String resolveCandidateHandle(ProjectId project, String handle) {
        if (handle == null || !handle.startsWith("candidate-h-")) {
            throw new IllegalArgumentException("candidate handle is invalid");
        }
        var rows = rows(gateway.select("SELECT DISTINCT ?candidate WHERE { GRAPH <"
                + router.route(project, GraphRole.CANDIDATES) + "> { ?candidate a ?type . } } ORDER BY ?candidate"));
        return rows.stream()
                .map(row -> row.get("candidate"))
                .filter(resource -> ("candidate-h-" + opaqueHandle(resource)).equals(handle))
                .map(FusekiQueryService::localName)
                .findFirst()
                .orElseThrow(() -> new ProjectScopedQueryService.ResourceNotFoundException(
                        "candidate handle is not visible in this project"));
    }

    /** Resolves only a handle previously emitted by the bounded knowledge projection. */
    public String resolveKnowledgeHandle(ProjectId project, String handle) {
        if (handle == null || !handle.startsWith("knowledge-h-")) {
            throw new IllegalArgumentException("knowledge handle is invalid");
        }
        var rows = rows(gateway.select("SELECT DISTINCT ?item WHERE { GRAPH <"
                + router.route(project, GraphRole.ASSERTED) + "> { ?item a <" + PROJECTA
                + "KnowledgeItem> . } } ORDER BY ?item"));
        return rows.stream()
                .map(row -> row.get("item"))
                .filter(resource -> ("knowledge-h-" + opaqueHandle(resource)).equals(handle))
                .map(FusekiQueryService::localName)
                .findFirst()
                .orElseThrow(() -> new ProjectScopedQueryService.ResourceNotFoundException(
                        "knowledge handle is not visible in this project"));
    }

    private List<Map<String, String>> rows(String body) {
        try {
            var result = new ArrayList<Map<String, String>>();
            for (JsonNode row : json.readTree(body).path("results").path("bindings")) {
                var values = new java.util.LinkedHashMap<String, String>();
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

    private EdgeResult graphEdges(ProjectId project, Set<String> resources, int edgeLimit) {
        if (resources.isEmpty()) return new EdgeResult(List.of(), false);
        var rows = rows(gateway.select(graphEdgeQuery(project, edgeLimit + 1)));
        var result = new ArrayList<Map<String, Object>>();
        for (var row : rows) {
            if (result.size() >= edgeLimit) break;
            if (!resources.contains(row.get("source")) || !resources.contains(row.get("target"))) continue;
            result.add(Map.of(
                    "handle",
                    "edge-h-" + opaqueHandle(row.get("source") + row.get("predicate") + row.get("target")),
                    "sourceHandle",
                    "node-h-" + opaqueHandle(row.get("source")),
                    "targetHandle",
                    "node-h-" + opaqueHandle(row.get("target")),
                    "relationType",
                    localName(row.get("predicate")),
                    "direction",
                    "source-to-target",
                    "verificationState",
                    required(row, "verificationState"),
                    "provenanceState",
                    required(row, "provenanceState"),
                    "evidenceCount",
                    0));
        }
        return new EdgeResult(result, rows.size() > edgeLimit);
    }

    private String graphNodeQuery(ProjectId project, int limit) {
        return """
                SELECT DISTINCT ?resource ?label ?type ?verificationState ?lifecycleState ?provenanceState WHERE {
                  { GRAPH <%s> {
                      ?resource <http://www.w3.org/2000/01/rdf-schema#label> ?label ; a ?type .
                    }
                    BIND("asserted" AS ?verificationState)
                    BIND("current" AS ?lifecycleState)
                    BIND("source-backed" AS ?provenanceState)
                  }
                  UNION
                  { GRAPH <%s> {
                      ?resource a <%sNote> ; <%sname> ?label .
                    }
                    BIND(<%sNote> AS ?type)
                    BIND("unverified" AS ?verificationState)
                    BIND("current" AS ?lifecycleState)
                    BIND("source-backed" AS ?provenanceState)
                  }
                  UNION
                  { GRAPH <%s> {
                      ?resource a <%sNoteItem> ; <%scontentText> ?label .
                    }
                    BIND(<%sNoteItem> AS ?type)
                    BIND("unverified" AS ?verificationState)
                    BIND("current" AS ?lifecycleState)
                    BIND("source-backed" AS ?provenanceState)
                  }
                  UNION
                  { %s
                    BIND(?candidate AS ?resource)
                    BIND("candidate" AS ?verificationState)
                    BIND("pending-review" AS ?lifecycleState)
                    BIND("candidate-proposed" AS ?provenanceState)
                  }
                }
                ORDER BY ?resource
                LIMIT %d
                """.formatted(
                        router.route(project, GraphRole.ASSERTED),
                        router.route(project, GraphRole.SOURCES),
                        PROJECTA,
                        PROJECTA,
                        PROJECTA,
                        router.route(project, GraphRole.SOURCES),
                        PROJECTA,
                        PROJECTA,
                        PROJECTA,
                        manualAndEntityCandidatePattern(project),
                        limit);
    }

    private String manualAndEntityCandidateQuery(ProjectId project, int limit) {
        return """
                SELECT DISTINCT ?candidate ?label ?status ?type WHERE {
                  %s
                }
                ORDER BY ?candidate
                LIMIT %d
                """.formatted(manualAndEntityCandidatePattern(project), limit);
    }

    private String manualAndEntityCandidatePattern(ProjectId project) {
        return """
                { GRAPH <%s> {
                    ?candidate a <%sCandidate> ;
                      <%scandidateStatus> ?status ;
                      <%sgenerator> ?generator ;
                      <http://www.w3.org/ns/prov#wasDerivedFrom> ?source .
                    FILTER(?generator IN ("manual-quick-note-v0.3.0", "connector-json-mock-v1"))
                  }
                  GRAPH <%s> {
                    ?source <%scontentText> ?label ; <%shasItemType> ?itemType .
                  }
                  VALUES (?itemType ?type) {
                    (<%srequirement> <%sRequirement>)
                    (<%sdecision> <%sDecision>)
                    (<%squestion> <%sQuestion>)
                    (<%stask> <%sTask>)
                    (<%srisk> <%sRisk>)
                    (<%sassumption> <%sAssumption>)
                    (<%sconstraint> <%sConstraint>)
                    (<%sprogress-update> <%sProgressClaim>)
                    (<%sresearch-need> <%sResearchFinding>)
                  }
                }
                UNION
                { GRAPH <%s> {
                    ?candidate a <%sEntityCandidate> ;
                      <%scandidateStatus> ?status ;
                      <%sproposedLabel> ?label ;
                      <%sproposedClass> ?type .
                  }
                }
                """.formatted(
                        router.route(project, GraphRole.CANDIDATES),
                        PROJECTA,
                        PROJECTA,
                        PROJECTA,
                        router.route(project, GraphRole.SOURCES),
                        PROJECTA,
                        PROJECTA,
                        PROJECTA,
                        PROJECTA,
                        PROJECTA,
                        PROJECTA,
                        PROJECTA,
                        PROJECTA,
                        PROJECTA,
                        PROJECTA,
                        PROJECTA,
                        PROJECTA,
                        PROJECTA,
                        PROJECTA,
                        PROJECTA,
                        PROJECTA,
                        PROJECTA,
                        PROJECTA,
                        PROJECTA,
                        PROJECTA,
                        PROJECTA,
                        PROJECTA,
                        PROJECTA,
                        router.route(project, GraphRole.CANDIDATES),
                        PROJECTA,
                        PROJECTA,
                        PROJECTA,
                        PROJECTA);
    }

    private String graphEdgeQuery(ProjectId project, int limit) {
        return """
                SELECT DISTINCT ?source ?target ?predicate ?verificationState ?provenanceState WHERE {
                  { GRAPH <%s> {
                      ?source ?predicate ?target .
                      VALUES ?predicate {
                        <%simplements> <%sblocks> <%sdependsOn> <%ssupports>
                        <%sanswers> <%sresolves> <%sconstrainedBy> <%ssupersedes>
                        <%sderivedFrom> <%sbelongsToProject> <%sevidenceFor> <%sprovenanceFor>
                      }
                    }
                    BIND("asserted" AS ?verificationState)
                    BIND("source-backed" AS ?provenanceState)
                  }
                  UNION
                  { GRAPH <%s> { ?source <%shasNoteItem> ?target . }
                    BIND(<%shasNoteItem> AS ?predicate)
                    BIND("unverified" AS ?verificationState)
                    BIND("source-backed" AS ?provenanceState)
                  }
                  UNION
                  { GRAPH <%s> {
                      ?source a <%sCandidate> ;
                        <http://www.w3.org/ns/prov#wasDerivedFrom> ?target .
                    }
                    BIND(<%sderivedFrom> AS ?predicate)
                    BIND("candidate" AS ?verificationState)
                    BIND("candidate-proposed" AS ?provenanceState)
                  }
                }
                ORDER BY ?source ?target
                LIMIT %d
                """.formatted(
                        router.route(project, GraphRole.ASSERTED),
                        PROJECTA,
                        PROJECTA,
                        PROJECTA,
                        PROJECTA,
                        PROJECTA,
                        PROJECTA,
                        PROJECTA,
                        PROJECTA,
                        PROJECTA,
                        PROJECTA,
                        PROJECTA,
                        PROJECTA,
                        router.route(project, GraphRole.SOURCES),
                        PROJECTA,
                        PROJECTA,
                        router.route(project, GraphRole.CANDIDATES),
                        PROJECTA,
                        PROJECTA,
                        limit);
    }

    private static Map<String, Object> node(
            String resource,
            String label,
            String type,
            String verificationState,
            String lifecycleState,
            String provenanceState) {
        var result = new LinkedHashMap<String, Object>();
        result.put("handle", "node-h-" + opaqueHandle(resource));
        result.put("label", label);
        result.put("semanticType", localName(type));
        result.put("lifecycleState", lifecycleState);
        result.put("verificationState", verificationState);
        result.put("provenanceState", provenanceState);
        result.put("direction", "source-to-target");
        result.put("evidenceCount", 0);
        result.put("projectScope", "selected");
        result.put("dates", Map.of());
        result.put("availableActions", List.of("view-detail", "view-evidence"));
        return result;
    }

    private static String localName(String iri) {
        if (iri == null || iri.isBlank()) throw new IllegalStateException("semantic store response is missing an IRI");
        var slash = iri.lastIndexOf('/');
        var hash = iri.lastIndexOf('#');
        return iri.substring(Math.max(slash, hash) + 1);
    }

    private static String entityType(String itemType) {
        return switch (itemType) {
            case "requirement" -> "Requirement";
            case "decision" -> "Decision";
            case "question" -> "Question";
            case "task" -> "Task";
            case "risk" -> "Risk";
            case "assumption" -> "Assumption";
            case "constraint" -> "Constraint";
            case "progress-update" -> "ProgressClaim";
            case "research-need" -> "ResearchFinding";
            default -> throw new IllegalArgumentException("manual Note item type is not allowlisted");
        };
    }

    private static String required(Map<String, String> row, String field) {
        var value = row.get(field);
        if (value == null || value.isBlank()) {
            throw new IllegalStateException("semantic store response is missing required field: " + field);
        }
        return value;
    }

    private static String opaqueHandle(String value) {
        try {
            var digest = MessageDigest.getInstance("SHA-256")
                    .digest(value.getBytes(java.nio.charset.StandardCharsets.UTF_8));
            var builder = new StringBuilder();
            for (int i = 0; i < 12; i++) builder.append(String.format("%02x", digest[i]));
            return builder.toString();
        } catch (java.security.NoSuchAlgorithmException exception) {
            throw new IllegalStateException("opaque handle hashing is unavailable", exception);
        }
    }

    private static List<Object> castList(Object value) {
        return value instanceof List<?> list ? new ArrayList<>(list) : List.of();
    }

    private record EdgeResult(List<Map<String, Object>> items, boolean hasMore) {}

    private String candidate(ProjectId project, String id) {
        if (id == null || !id.matches("[a-z0-9][a-z0-9-]{0,62}"))
            throw new IllegalArgumentException("candidate ID is invalid");
        return "https://w3id.org/projecta/data/project/" + project.value() + "/candidate/" + id;
    }

    private static String opaqueIdentifier(String iri) {
        var slash = iri.lastIndexOf('/');
        return slash < 0 ? iri : iri.substring(slash + 1);
    }
}
