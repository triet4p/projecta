package org.projecta.semanticcore;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import java.util.UUID;

/** Atomically persists normalized M3 candidate proposals and extraction provenance. */
public final class LlmCandidateIngestionService {
    private static final ObjectMapper JSON = new ObjectMapper();
    private static final String BASE = "https://w3id.org/projecta/data/project/";
    private static final String ONTOLOGY = "https://w3id.org/projecta/ontology/";
    private static final String PROV = "http://www.w3.org/ns/prov#";
    private static final String RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#";
    private static final String RDFS = "http://www.w3.org/2000/01/rdf-schema#";
    private static final String XSD = "http://www.w3.org/2001/XMLSchema#";
    private static final String ONTOLOGY_VERSION = "0.4.0";
    private static final Set<String> TYPES = Set.of(
            "Requirement", "Decision", "Question", "Task", "Risk", "Assumption", "Constraint", "ProgressClaim", "ResearchFinding");
    private static final Set<String> PREDICATES = Set.of(
            "implements", "blocks", "dependsOn", "supports", "answers", "resolves", "constrainedBy");

    private final FusekiGateway gateway;
    private final GraphIriRouter router;
    private final RemoteCandidateValidationService validator;

    public LlmCandidateIngestionService(
            FusekiGateway gateway, GraphIriRouter router, RemoteCandidateValidationService validator) {
        this.gateway = gateway;
        this.router = router;
        this.validator = validator;
    }

    /** Writes source, rich candidates, and provenance in one conditional update. */
    public IngestionResult ingest(ProjectId project, String actor, String key, IngestionRequest request) {
        requireId(actor, "actor ID");
        requireKey(key);
        if (request == null || request.rawText() == null || request.rawText().isBlank()) {
            throw new IllegalArgumentException("extraction request is invalid");
        }
        if (request.entities().size() + request.relations().size() + request.links().size() > 100) {
            throw new IllegalArgumentException("extraction result is too large");
        }
        var normalized = request.rawText().replace("\r\n", "\n").replace("\r", "\n");
        validate(request, normalized);
        var projectIri = BASE + project.value();
        var noteId = OpaqueIds.random("note-");
        var note = projectIri + "/note/" + noteId;
        var record = projectIri + "/capture-idempotency/" + OpaqueIds.idempotencyDigest(key);
        var fingerprint = normalized + "|" + request.modelId() + "|" + request.modelVersion() + "|"
                + request.promptVersion() + "|" + request.schemaVersion() + "|" + request.abstentionReason()
                + "|" + request.entities() + "|" + request.relations() + "|" + request.links();
        var now = OffsetDateTime.now().toString();
        var attempt = UUID.randomUUID().toString();
        var sources = sourceTriples(project, actor, note, projectIri, normalized, request, now);
        var candidates = candidateTriples(project, note, projectIri, request, now);
        var provenance = provenanceTriples(project, actor, note, projectIri, record, fingerprint, attempt, request, now);
        var validationResult = validator.validateCapture(project, sources, candidates, provenance);
        if (!validationResult.conforms()) {
            throw new CandidateInvalidException(validationResult);
        }
        var sourceGraph = router.route(project, GraphRole.SOURCES);
        var candidateGraph = router.route(project, GraphRole.CANDIDATES);
        var provenanceGraph = router.route(project, GraphRole.PROVENANCE);
        gateway.update(
                "INSERT { GRAPH <%s> { %s } GRAPH <%s> { %s } GRAPH <%s> { %s } } WHERE { FILTER NOT EXISTS { GRAPH <%s> { <%s> ?p ?o } } }"
                        .formatted(sourceGraph, sources, candidateGraph, candidates, provenanceGraph, provenance, provenanceGraph, record));
        if (!gateway.ask("ASK { GRAPH <" + provenanceGraph + "> { <" + record + "> <" + RDF + "value> " + literal(fingerprint) + " } }")) {
            throw new IllegalArgumentException("idempotency key was reused with a different request body");
        }
        var created = gateway.ask("ASK { GRAPH <" + provenanceGraph + "> { <" + record + "> <" + RDFS + "comment> " + literal(attempt) + " } }");
        if (!created) {
            var replay = gateway.select("SELECT ?note WHERE { GRAPH <" + provenanceGraph + "> { <" + record + "> <" + PROV + "generated> ?note } }");
            note = replayedNote(replay);
            noteId = note.substring(note.lastIndexOf('/') + 1);
        }
        var result = new ArrayList<CandidateResult>();
        var total = request.entities().size() + request.relations().size() + request.links().size();
        for (var index = 1; index <= total; index++) {
            var id = candidateId(noteId, index);
            result.add(new CandidateResult(id, "extracted"));
        }
        return new IngestionResult(noteId, result, !created);
    }

    static String sourceTriples(ProjectId project, String actor, String note, String projectIri, String raw, IngestionRequest request, String now) {
        var triples = new StringBuilder("<" + projectIri + "> a <" + ONTOLOGY + "Project> . <" + projectIri + "/person/" + actor + "> a <" + ONTOLOGY + "Person> . <" + note + "> a <" + ONTOLOGY + "Note> ; <" + ONTOLOGY + "name> " + literal("LLM Quick Note") + " ; <" + ONTOLOGY + "rawText> " + literal(raw) + " ; <" + ONTOLOGY + "belongsToProject> <" + projectIri + "> ; <" + ONTOLOGY + "authoredBy> <" + projectIri + "/person/" + actor + "> ; <" + ONTOLOGY + "recordedAt> " + typed(now, "dateTime") + " . ");
        var index = 0;
        for (var evidence : evidence(request)) {
            index++;
            var item = note + "/item-" + index;
            triples.append("<").append(note).append("> <").append(ONTOLOGY).append("hasNoteItem> <").append(item).append("> . <").append(item).append("> a <").append(ONTOLOGY).append("NoteItem> ; <").append(ONTOLOGY).append("isItemOf> <").append(note).append("> ; <").append(ONTOLOGY).append("hasItemType> <").append(ONTOLOGY).append(evidence.itemType()).append("> ; <").append(ONTOLOGY).append("contentText> ").append(literal(evidence.text())).append(" ; <").append(ONTOLOGY).append("evidenceStartOffset> ").append(typed(Integer.toString(evidence.startOffset()), "nonNegativeInteger")).append(" ; <").append(ONTOLOGY).append("evidenceEndOffset> ").append(typed(Integer.toString(evidence.endOffset()), "positiveInteger")).append(" . ");
        }
        return triples.toString();
    }

    String candidateTriples(ProjectId project, String note, String projectIri, IngestionRequest request, String now) {
        var triples = new StringBuilder("<" + projectIri + "> a <" + ONTOLOGY + "Project> . ");
        var index = 0;
        for (var entity : request.entities()) {
            index++;
            var candidate = candidateIri(project, note, index);
            triples.append(baseCandidate(candidate, projectIri, note, index, request, now)).append(" a <").append(ONTOLOGY).append("EntityCandidate> ; <").append(ONTOLOGY).append("proposedClass> <").append(ONTOLOGY).append(entity.type()).append("> ; <").append(ONTOLOGY).append("proposedLabel> ").append(literal(entity.label())).append(" ; <").append(ONTOLOGY).append("confidence> ").append(entity.confidence()).append(" . ");
        }
        for (var relation : request.relations()) {
            index++;
            var candidate = candidateIri(project, note, index);
            triples.append(baseCandidate(candidate, projectIri, note, index, request, now)).append(" a <").append(ONTOLOGY).append("RelationCandidate> ; <").append(ONTOLOGY).append("proposedPredicate> <").append(ONTOLOGY).append(relation.predicate()).append("> ; <").append(ONTOLOGY).append("relationSource> <").append(resolveEntityIri(project, relation.sourceEntityId())).append("> ; <").append(ONTOLOGY).append("relationTarget> <").append(resolveEntityIri(project, relation.targetEntityId())).append("> ; <").append(ONTOLOGY).append("confidence> ").append(relation.confidence()).append(" . ");
        }
        for (var link : request.links()) {
            index++;
            var candidate = candidateIri(project, note, index);
            triples.append(baseCandidate(candidate, projectIri, note, index, request, now)).append(" a <").append(ONTOLOGY).append("EntityLinkCandidate> ; <").append(ONTOLOGY).append("proposedLabel> ").append(literal(link.mention())).append(" ; <").append(ONTOLOGY).append("linkTarget> <").append(resolveEntityIri(project, link.targetEntityId())).append("> ; <").append(ONTOLOGY).append("confidence> ").append(link.confidence()).append(" . ");
        }
        return triples.toString();
    }

    private static String baseCandidate(String candidate, String projectIri, String note, int index, IngestionRequest request, String now) {
        return "<" + candidate + "> a <" + ONTOLOGY + "Candidate> ; <" + ONTOLOGY + "candidateStatus> <" + ONTOLOGY + "extracted> ; <" + ONTOLOGY + "generator> " + literal(request.modelId()) + " ; <" + ONTOLOGY + "proposedOntologyVersion> " + literal(ONTOLOGY_VERSION) + " ; <" + ONTOLOGY + "belongsToProject> <" + projectIri + "> ; <" + PROV + "wasDerivedFrom> <" + note + "/item-" + index + "> ; <" + PROV + "wasGeneratedBy> <" + note + "/activity-" + index + "> ; <" + PROV + "generatedAtTime> " + typed(now, "dateTime") + " ; ";
    }

    static String provenanceTriples(ProjectId project, String actor, String note, String projectIri, String record, String fingerprint, String attempt, IngestionRequest request, String now) {
        var triples = new StringBuilder("<" + record + "> <" + RDF + "value> " + literal(fingerprint) + " ; <" + RDFS + "label> \"llm-extraction-idempotency\" ; <" + RDFS + "comment> " + literal(attempt) + " ; <" + PROV + "generated> <" + note + "> . ");
        var total = request.entities().size() + request.relations().size() + request.links().size();
        for (var index = 1; index <= total; index++) {
            triples.append("<").append(note).append("/activity-").append(index).append("> a <").append(PROV).append("Activity> ; <").append(PROV).append("used> <").append(note).append("/item-").append(index).append("> ; <").append(PROV).append("generated> <").append(projectIri).append("/candidate/").append(candidateId(note.substring(note.lastIndexOf('/') + 1), index)).append("> ; <").append(PROV).append("wasAssociatedWith> <").append(projectIri).append("/person/").append(actor).append("> ; <").append(ONTOLOGY).append("belongsToProject> <").append(projectIri).append("> ; <").append(PROV).append("endedAtTime> ").append(typed(now, "dateTime")).append(" ; <").append(ONTOLOGY).append("modelVersion> ").append(literal(request.modelVersion())).append(" ; <").append(ONTOLOGY).append("promptVersion> ").append(literal(request.promptVersion())).append(" ; <").append(ONTOLOGY).append("schemaVersion> ").append(literal(request.schemaVersion())).append(" . ");
        }
        if (total == 0) {
            triples.append("<").append(note).append("/activity-extraction> a <").append(PROV).append("Activity> ; <").append(PROV).append("wasAssociatedWith> <").append(projectIri).append("/person/").append(actor).append("> ; <").append(ONTOLOGY).append("belongsToProject> <").append(projectIri).append("> ; <").append(ONTOLOGY).append("abstentionReason> ").append(literal(request.abstentionReason())).append(" ; <").append(ONTOLOGY).append("modelVersion> ").append(literal(request.modelVersion())).append(" ; <").append(ONTOLOGY).append("promptVersion> ").append(literal(request.promptVersion())).append(" ; <").append(ONTOLOGY).append("schemaVersion> ").append(literal(request.schemaVersion())).append(" ; <").append(PROV).append("endedAtTime> ").append(typed(now, "dateTime")).append(" . ");
        }
        return triples.toString();
    }

    private static List<Evidence> evidence(IngestionRequest request) {
        var result = new ArrayList<Evidence>();
        request.entities().forEach(item -> result.add(new Evidence(item.startOffset(), item.endOffset(), item.text(), itemType(item.type()))));
        request.relations().forEach(item -> result.add(new Evidence(item.startOffset(), item.endOffset(), item.text(), "research-need")));
        request.links().forEach(item -> result.add(new Evidence(item.startOffset(), item.endOffset(), item.mention(), "research-need")));
        return result;
    }

    private static String candidateId(String noteId, int index) { return noteId + "-" + index; }
    private static String candidateIri(ProjectId project, String note, int index) { return BASE + project.value() + "/candidate/" + candidateId(note.substring(note.lastIndexOf('/') + 1), index); }
    String resolveEntityIri(ProjectId project, String encodedId) {
        if (encodedId == null || !encodedId.matches("[A-Za-z0-9][A-Za-z0-9._-]{0,127}")) {
            throw new IllegalArgumentException("entity target ID is invalid");
        }
        var separator = encodedId.indexOf("--");
        if (separator <= 0 || separator == encodedId.length() - 2) {
            throw new IllegalArgumentException("entity target ID must preserve its canonical type");
        }
        var type = encodedId.substring(0, separator).toLowerCase();
        var id = encodedId.substring(separator + 2);
        var route = switch (type) {
            case "requirement", "decision", "question", "task", "risk", "assumption", "constraint", "progressclaim", "researchfinding", "person", "team" -> type;
            default -> throw new IllegalArgumentException("entity target type is not allowlisted");
        };
        var iri = BASE + project.value() + "/" + route + "/" + id;
        var graph = router.route(project, GraphRole.ASSERTED);
        if (!gateway.ask("ASK { GRAPH <" + graph + "> { <" + iri + "> <" + ONTOLOGY + "belongsToProject> <" + BASE + project.value() + "> } }")) {
            throw new IllegalArgumentException("entity target is not present in the trusted project");
        }
        return iri;
    }
    private static String itemType(String type) {
        return switch (type) {
            case "ProgressClaim" -> "progress-update";
            case "ResearchFinding" -> "research-need";
            default -> type.toLowerCase();
        };
    }
    static String replayedNote(String response) {
        try {
            var bindings = JSON.readTree(response).path("results").path("bindings");
            if (!bindings.isArray() || bindings.size() != 1) {
                throw new IllegalStateException("capture replay record is unavailable");
            }
            var note = bindings.get(0).path("note").path("value").asText();
            if (note.isBlank()) {
                throw new IllegalStateException("capture replay record is unavailable");
            }
            return note;
        } catch (JsonProcessingException exception) {
            throw new IllegalStateException("capture replay record is unavailable", exception);
        }
    }

    static void validate(IngestionRequest request, String rawText) {
        if (request.modelId() == null || request.modelVersion() == null || request.promptVersion() == null || request.schemaVersion() == null) throw new IllegalArgumentException("extraction provenance is invalid");
        if (request.entities().isEmpty() && request.relations().isEmpty() && request.links().isEmpty()
                && (request.abstentionReason() == null || request.abstentionReason().isBlank())) {
            throw new IllegalArgumentException("empty extraction must record an abstention reason");
        }
        request.entities().forEach(entity -> { if (!TYPES.contains(entity.type())) throw new IllegalArgumentException("entity type is not allowlisted"); });
        request.relations().forEach(relation -> { if (!PREDICATES.contains(relation.predicate())) throw new IllegalArgumentException("relation predicate is not allowlisted"); });
        var codePoints = rawText.codePoints().toArray();
        request.entities().forEach(entity -> requireEvidence(rawText, codePoints, entity.startOffset(), entity.endOffset(), entity.text()));
        request.relations().forEach(relation -> requireEvidence(rawText, codePoints, relation.startOffset(), relation.endOffset(), relation.text()));
        request.links().forEach(link -> requireEvidence(rawText, codePoints, link.startOffset(), link.endOffset(), link.mention()));
    }
    private static void requireEvidence(String rawText, int[] codePoints, int start, int end, String expected) {
        if (expected == null || start < 0 || start >= end || end > codePoints.length) throw new IllegalArgumentException("evidence is invalid");
        var actual = new String(codePoints, start, end - start);
        if (!actual.equals(expected)) throw new IllegalArgumentException("evidence does not match source text");
    }
    private static String typed(String value, String datatype) { return literal(value) + "^^<" + XSD + datatype + ">"; }
    private static String literal(String value) { return "\"" + value.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n").replace("\r", "\\r") + "\""; }
    private static void requireId(String value, String name) { if (value == null || !value.matches("[a-z0-9][a-z0-9-]{0,62}")) throw new IllegalArgumentException(name + " is invalid"); }
    private static void requireKey(String key) { if (key == null || !key.matches("[A-Za-z0-9-]{1,128}")) throw new IllegalArgumentException("idempotency key is invalid"); }

    public record IngestionRequest(String rawText, String modelId, String modelVersion, String promptVersion, String schemaVersion, List<EntityProposal> entities, List<RelationProposal> relations, List<LinkProposal> links, String abstentionReason) {
        public IngestionRequest { entities = entities == null ? List.of() : List.copyOf(entities); relations = relations == null ? List.of() : List.copyOf(relations); links = links == null ? List.of() : List.copyOf(links); }
        public IngestionRequest(String rawText, String modelId, String modelVersion, String promptVersion, String schemaVersion, List<EntityProposal> entities, List<RelationProposal> relations, List<LinkProposal> links) {
            this(rawText, modelId, modelVersion, promptVersion, schemaVersion, entities, relations, links, null);
        }
    }
    public record EntityProposal(String type, String label, String text, int startOffset, int endOffset, double confidence) {}
    public record RelationProposal(String predicate, String sourceEntityId, String targetEntityId, String text, int startOffset, int endOffset, double confidence) {}
    public record LinkProposal(String mention, String targetEntityId, int startOffset, int endOffset, double confidence) {}
    public record Evidence(int startOffset, int endOffset, String text, String itemType) {}
    public record CandidateResult(String id, String status) {}
    public record IngestionResult(String noteId, List<CandidateResult> candidates, boolean replayed) {}
}
