package org.projecta.semanticcore;

import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import java.util.UUID;
import java.util.regex.Pattern;

/** Atomically writes typed Quick Note source, candidate, and provenance records. */
public final class QuickNoteCaptureService {
    private static final String BASE = "https://w3id.org/projecta/data/project/";
    private static final String ONTOLOGY = "https://w3id.org/projecta/ontology/";
    private static final String PROV = "http://www.w3.org/ns/prov#";
    private static final String RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#";
    private static final String RDFS = "http://www.w3.org/2000/01/rdf-schema#";
    private static final String XSD = "http://www.w3.org/2001/XMLSchema#";
    private static final Set<String> TYPES = Set.of(
            "requirement",
            "decision",
            "question",
            "task",
            "risk",
            "assumption",
            "constraint",
            "progress-update",
            "research-need");

    private final FusekiGateway gateway;
    private final GraphIriRouter router;
    private final CaptureValidator validator;

    public QuickNoteCaptureService(FusekiGateway gateway, GraphIriRouter router, CaptureValidator validator) {
        this.gateway = gateway;
        this.router = router;
        this.validator = validator;
    }

    /**
     * Captures a canonical Quick Note in one Fuseki SPARQL Update transaction.
     *
     * <p>The conditional update means only one request may claim an idempotency key across Core
     * processes. It writes sources, candidates, provenance, and the private idempotency record
     * together; malformed evidence is rejected before that update is sent.
     */
    public CaptureResult capture(ProjectId project, String actor, String key, CaptureRequest request) {
        requireId(actor, "actor ID");
        requireKey(key);
        if (request == null || request.rawText() == null) {
            throw new IllegalArgumentException("capture request is invalid");
        }

        var normalized = request.rawText().replace("\r\n", "\n").replace("\r", "\n");
        validate(normalized, request.segments());

        var noteId = OpaqueIds.random("note-");
        var fingerprint = normalized + "|" + request.segments();
        var projectIri = BASE + project.value();
        var record = BASE + project.value() + "/capture-idempotency/" + OpaqueIds.idempotencyDigest(key);
        var note = BASE + project.value() + "/note/" + noteId;
        var sourceGraph = router.route(project, GraphRole.SOURCES).toString();
        var candidateGraph = router.route(project, GraphRole.CANDIDATES).toString();
        var provenanceGraph = router.route(project, GraphRole.PROVENANCE).toString();
        var attemptToken = UUID.randomUUID().toString();
        var now = OffsetDateTime.now().toString();

        var sources = sourceTriples(project, actor, note, projectIri, normalized, request.segments(), now);
        var candidates = candidateTriples(project, noteId, projectIri, request.segments(), now);
        var provenance = provenanceTriples(
                project, actor, noteId, projectIri, record, fingerprint, attemptToken, now, request.segments());
        var validationResult = validator.validate(project, sources, candidates, provenance);
        if (!validationResult.conforms()) {
            throw new CandidateInvalidException(validationResult);
        }
        gateway.update(
                """
                INSERT {
                  GRAPH <%s> { %s }
                  GRAPH <%s> { %s }
                  GRAPH <%s> { %s }
                }
                WHERE {
                  FILTER NOT EXISTS { GRAPH <%s> { <%s> ?existingPredicate ?existingObject } }
                }
                """
                        .formatted(
                                sourceGraph,
                                sources,
                                candidateGraph,
                                candidates,
                                provenanceGraph,
                                provenance,
                                provenanceGraph,
                                record));

        if (!gateway.ask("ASK { GRAPH <" + provenanceGraph + "> { <" + record + "> <" + RDF + "value> "
                + literal(fingerprint) + " } }")) {
            throw new IllegalArgumentException("idempotency key was reused with a different request body");
        }
        var created = gateway.ask("ASK { GRAPH <" + provenanceGraph + "> { <" + record + "> <" + RDFS + "comment> "
                + literal(attemptToken) + " } }");
        var committedNote = created ? note : recordNote(provenanceGraph, record);
        var committedNoteId = committedNote.substring(committedNote.lastIndexOf('/') + 1);
        return result(
                committedNoteId,
                request.segments().size(),
                !created,
                created ? now : recordedAt(sourceGraph, committedNote));
    }

    private static String sourceTriples(
            ProjectId project,
            String actor,
            String note,
            String projectIri,
            String rawText,
            List<Segment> segments,
            String now) {
        var triples = new StringBuilder("<" + projectIri + "> a <" + ONTOLOGY + "Project> . <" + projectIri
                + "/person/" + actor + "> a <" + ONTOLOGY + "Person> . <" + note + "> a <" + ONTOLOGY
                + "Note> ; <" + ONTOLOGY + "name> " + literal("Quick Note") + " ; <" + ONTOLOGY + "rawText> "
                + literal(rawText)
                + " ; <" + ONTOLOGY + "belongsToProject> <" + projectIri + "> ; <" + ONTOLOGY
                + "authoredBy> <" + projectIri + "/person/" + actor + "> ; <" + ONTOLOGY + "recordedAt> "
                + typed(now, "dateTime") + " . ");
        for (var index = 0; index < segments.size(); index++) {
            var segment = segments.get(index);
            var item = noteItem(project, note.substring(note.lastIndexOf('/') + 1), index + 1);
            triples.append("<")
                    .append(note)
                    .append("> <")
                    .append(ONTOLOGY)
                    .append("hasNoteItem> <")
                    .append(item)
                    .append("> . <")
                    .append(item)
                    .append("> a <")
                    .append(ONTOLOGY)
                    .append("NoteItem> ; <")
                    .append(ONTOLOGY)
                    .append("isItemOf> <")
                    .append(note)
                    .append("> ; <")
                    .append(ONTOLOGY)
                    .append("hasItemType> <")
                    .append(ONTOLOGY)
                    .append(segment.type())
                    .append("> ; <")
                    .append(ONTOLOGY)
                    .append("contentText> ")
                    .append(literal(segment.text()))
                    .append(" ; <")
                    .append(ONTOLOGY)
                    .append("evidenceStartOffset> ")
                    .append(typed(Integer.toString(segment.startOffset()), "nonNegativeInteger"))
                    .append(" ; <")
                    .append(ONTOLOGY)
                    .append("evidenceEndOffset> ")
                    .append(typed(Integer.toString(segment.endOffset()), "positiveInteger"))
                    .append(" . ");
        }
        return triples.toString();
    }

    private static String candidateTriples(
            ProjectId project, String noteId, String projectIri, List<Segment> segments, String now) {
        var triples = new StringBuilder("<" + projectIri + "> a <" + ONTOLOGY + "Project> . ");
        for (var index = 0; index < segments.size(); index++) {
            var candidate = candidate(project, noteId, index + 1);
            var item = noteItem(project, noteId, index + 1);
            var activity = activity(project, noteId, index + 1);
            triples.append("<")
                    .append(candidate)
                    .append("> a <")
                    .append(ONTOLOGY)
                    .append("Candidate> ; <")
                    .append(ONTOLOGY)
                    .append("candidateStatus> <")
                    .append(ONTOLOGY)
                    .append("extracted> ; <")
                    .append(ONTOLOGY)
                    .append("generator> \"manual-quick-note-v0.3.0\" ; <")
                    .append(ONTOLOGY)
                    .append("proposedOntologyVersion> \"0.3.0\" ; <")
                    .append(ONTOLOGY)
                    .append("belongsToProject> <")
                    .append(projectIri)
                    .append("> ; <")
                    .append(PROV)
                    .append("wasDerivedFrom> <")
                    .append(item)
                    .append("> ; <")
                    .append(PROV)
                    .append("wasGeneratedBy> <")
                    .append(activity)
                    .append("> ; <")
                    .append(PROV)
                    .append("generatedAtTime> ")
                    .append(typed(now, "dateTime"))
                    .append(" . ");
        }
        return triples.toString();
    }

    private static String provenanceTriples(
            ProjectId project,
            String actor,
            String noteId,
            String projectIri,
            String record,
            String fingerprint,
            String attemptToken,
            String now,
            List<Segment> segments) {
        var note = BASE + project.value() + "/note/" + noteId;
        var triples = new StringBuilder("<" + record + "> <" + RDF + "value> " + literal(fingerprint) + " ; <" + RDFS
                + "label> \"quick-note-capture-idempotency\" ; <" + RDFS + "comment> " + literal(attemptToken)
                + " ; <" + PROV + "generated> <" + note + "> . ");
        for (var index = 0; index < segments.size(); index++) {
            var item = noteItem(project, noteId, index + 1);
            var candidate = candidate(project, noteId, index + 1);
            var activity = activity(project, noteId, index + 1);
            triples.append("<")
                    .append(activity)
                    .append("> a <")
                    .append(PROV)
                    .append("Activity> ; <")
                    .append(PROV)
                    .append("used> <")
                    .append(item)
                    .append("> ; <")
                    .append(PROV)
                    .append("generated> <")
                    .append(candidate)
                    .append("> ; <")
                    .append(PROV)
                    .append("wasAssociatedWith> <")
                    .append(projectIri)
                    .append("/person/")
                    .append(actor)
                    .append("> ; <")
                    .append(ONTOLOGY)
                    .append("belongsToProject> <")
                    .append(projectIri)
                    .append("> ; <")
                    .append(PROV)
                    .append("endedAtTime> ")
                    .append(typed(now, "dateTime"))
                    .append(" . ");
        }
        return triples.toString();
    }

    private static String noteItem(ProjectId project, String noteId, int number) {
        return BASE + project.value() + "/note-item/" + noteId + "-" + number;
    }

    private static String candidate(ProjectId project, String noteId, int number) {
        return BASE + project.value() + "/candidate/" + noteId + "-" + number;
    }

    private static String activity(ProjectId project, String noteId, int number) {
        return BASE + project.value() + "/activity/extract-" + noteId + "-" + number;
    }

    private String recordedAt(String sourceGraph, String note) {
        var response = gateway.select("SELECT ?recordedAt WHERE { GRAPH <" + sourceGraph + "> { <" + note + "> <"
                + ONTOLOGY + "recordedAt> ?recordedAt } }");
        var match = Pattern.compile("\\\"value\\\"\\s*:\\s*\\\"([^\\\"]+)\\\"").matcher(response);
        if (!match.find()) {
            throw new IllegalStateException("capture replay record is unavailable");
        }
        return match.group(1);
    }

    private String recordNote(String provenanceGraph, String record) {
        var response = gateway.select("SELECT ?note WHERE { GRAPH <" + provenanceGraph + "> { <" + record + "> <" + PROV
                + "generated> ?note } }");
        var match = Pattern.compile("\\\"value\\\"\\s*:\\s*\\\"([^\\\"]+)\\\"").matcher(response);
        if (!match.find()) {
            throw new IllegalStateException("capture replay record is unavailable");
        }
        return match.group(1);
    }

    private static CaptureResult result(String noteId, int count, boolean replayed, String recordedAt) {
        var candidates = new ArrayList<CandidateResult>();
        for (var index = 0; index < count; index++) {
            var identifier = noteId + "-" + (index + 1);
            candidates.add(new CandidateResult(identifier, identifier, "extracted"));
        }
        return new CaptureResult(noteId, recordedAt, candidates, replayed);
    }

    private static void validate(String raw, List<Segment> segments) {
        if (raw.isBlank() || segments == null || segments.isEmpty()) {
            throw new IllegalArgumentException("capture request is invalid");
        }
        var previousEnd = 0;
        var rawLength = raw.codePointCount(0, raw.length());
        for (var segment : segments) {
            if (segment == null
                    || !TYPES.contains(segment.type())
                    || segment.startOffset() < previousEnd
                    || segment.startOffset() >= segment.endOffset()
                    || segment.endOffset() > rawLength
                    || !codePointSlice(raw, segment.startOffset(), segment.endOffset())
                            .equals(segment.text())) {
                throw new IllegalArgumentException("capture evidence is invalid");
            }
            previousEnd = segment.endOffset();
        }
    }

    private static String codePointSlice(String raw, int start, int end) {
        return raw.substring(raw.offsetByCodePoints(0, start), raw.offsetByCodePoints(0, end));
    }

    private static String typed(String value, String datatype) {
        return literal(value) + "^^<" + XSD + datatype + ">";
    }

    private static String literal(String value) {
        return "\""
                + value.replace("\\", "\\\\")
                        .replace("\"", "\\\"")
                        .replace("\n", "\\n")
                        .replace("\r", "\\r") + "\"";
    }

    private static void requireId(String value, String name) {
        if (value == null || !value.matches("[a-z0-9][a-z0-9-]{0,62}")) {
            throw new IllegalArgumentException(name + " is invalid");
        }
    }

    private static void requireKey(String key) {
        if (key == null || !key.matches("[A-Za-z0-9-]{1,128}")) {
            throw new IllegalArgumentException("idempotency key is invalid");
        }
    }

    @FunctionalInterface
    public interface CaptureValidator {
        CandidateValidationResult validate(ProjectId project, String sources, String candidates, String provenance);
    }

    public record Segment(String type, int startOffset, int endOffset, String text) {}

    public record CaptureRequest(String rawText, List<Segment> segments) {}

    public record CandidateResult(String id, String sourceItemId, String status) {}

    public record CaptureResult(String noteId, String recordedAt, List<CandidateResult> candidates, boolean replayed) {}
}
