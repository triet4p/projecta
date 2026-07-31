package org.projecta.semanticcore;

import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.UUID;

/** Domain-safe lifecycle writes executed atomically by Fuseki in one SPARQL Update request. */
public final class FusekiLifecycleService {
    private static final String PROJECTA = "https://w3id.org/projecta/ontology/";
    private static final String PROV = "http://www.w3.org/ns/prov#";
    private final FusekiGateway gateway;
    private final GraphIriRouter router;
    private final RemoteCandidateValidationService validation;

    public FusekiLifecycleService(FusekiGateway gateway, GraphIriRouter router) {
        this(gateway, router, null);
    }

    public FusekiLifecycleService(
            FusekiGateway gateway, GraphIriRouter router, RemoteCandidateValidationService validation) {
        this.gateway = gateway;
        this.router = router;
        this.validation = validation;
    }

    /**
     * Confirms a candidate without an idempotency record, for in-process callers and focused tests.
     *
     * <p>The runtime HTTP boundary uses {@link #confirmDecision} instead.
     */
    public synchronized String confirm(
            ProjectId project, String candidateId, String reviewerId, String label, LocalDate validFrom) {
        return confirm(project, candidateId, reviewerId, label, validFrom, null, null, null, null);
    }

    private String confirm(
            ProjectId project,
            String candidateId,
            String reviewerId,
            String label,
            LocalDate validFrom,
            String assertedIri,
            String keyRecord,
            String requestFingerprint,
            String attemptToken) {
        require(label, "assertion label");
        if (validation != null) {
            var validationResult = validation.validate(project, candidateId);
            if (!validationResult.conforms()) {
                throw new CandidateInvalidException(validationResult);
            }
        }
        var candidate = candidateIri(project, candidateId);
        var item = assertedIri == null
                ? "https://w3id.org/projecta/data/project/" + project.value() + "/requirement/" + UUID.randomUUID()
                : assertedIri;
        var activity = item + "/activity/confirm";
        var statement = item + "/statement/valid-from";
        var now = OffsetDateTime.now().toString();
        var update =
                """
                DELETE { GRAPH <%s> { <%s> <https://w3id.org/projecta/ontology/candidateStatus> ?status } }
                INSERT {
                  GRAPH <%s> { <%s> a <https://w3id.org/projecta/ontology/KnowledgeItem>, <https://w3id.org/projecta/ontology/Requirement> ; <http://www.w3.org/2000/01/rdf-schema#label> %s ; <http://www.w3.org/ns/prov#wasDerivedFrom> <%s> ; <http://www.w3.org/ns/prov#wasAttributedTo> <%s> ; <https://w3id.org/projecta/ontology/belongsToProject> <https://w3id.org/projecta/data/project/%s> ; <https://w3id.org/projecta/ontology/validFrom> \"%s\"^^<http://www.w3.org/2001/XMLSchema#date> . }
                  GRAPH <%s> { <%s> a <http://www.w3.org/ns/prov#Activity> ; <http://www.w3.org/ns/prov#used> <%s> ; <http://www.w3.org/ns/prov#generated> <%s> ; <http://www.w3.org/ns/prov#wasAssociatedWith> <%s> ; <https://w3id.org/projecta/ontology/reviewDecision> <https://w3id.org/projecta/ontology/confirmed> ; <http://www.w3.org/ns/prov#endedAtTime> \"%s\"^^<http://www.w3.org/2001/XMLSchema#dateTime> . <%s> a <http://www.w3.org/1999/02/22-rdf-syntax-ns#Statement> ; <http://www.w3.org/1999/02/22-rdf-syntax-ns#subject> <%s> ; <http://www.w3.org/1999/02/22-rdf-syntax-ns#predicate> <https://w3id.org/projecta/ontology/validFrom> ; <http://www.w3.org/1999/02/22-rdf-syntax-ns#object> \"%s\"^^<http://www.w3.org/2001/XMLSchema#date> . }
                  GRAPH <%s> { <%s> <https://w3id.org/projecta/ontology/candidateStatus> <https://w3id.org/projecta/ontology/asserted> . }
                  %s
                }
                WHERE { GRAPH <%s> { <%s> a <https://w3id.org/projecta/ontology/Candidate> ; <https://w3id.org/projecta/ontology/candidateStatus> ?status ; <http://www.w3.org/ns/prov#wasDerivedFrom> ?source ; <http://www.w3.org/ns/prov#wasGeneratedBy> ?generator ; <http://www.w3.org/ns/prov#generatedAtTime> ?generatedAt ; <https://w3id.org/projecta/ontology/generator> ?generatorName ; <https://w3id.org/projecta/ontology/proposedOntologyVersion> ?version ; <https://w3id.org/projecta/ontology/belongsToProject> <https://w3id.org/projecta/data/project/%s> . FILTER(?status IN (<https://w3id.org/projecta/ontology/validated>, <https://w3id.org/projecta/ontology/pending-review>)) } %s }
                """
                        .formatted(
                                router.route(project, GraphRole.CANDIDATES),
                                candidate,
                                router.route(project, GraphRole.ASSERTED),
                                item,
                                literal(label),
                                candidate,
                                reviewerIri(project, reviewerId),
                                project.value(),
                                validFrom,
                                router.route(project, GraphRole.PROVENANCE),
                                activity,
                                candidate,
                                item,
                                reviewerIri(project, reviewerId),
                                now,
                                statement,
                                item,
                                validFrom,
                                router.route(project, GraphRole.CANDIDATES),
                                candidate,
                                keyRecord == null
                                        ? ""
                                        : "GRAPH <" + router.route(project, GraphRole.PROVENANCE) + "> { <"
                                                + keyRecord
                                                + "> <http://www.w3.org/1999/02/22-rdf-syntax-ns#value> "
                                                + literal(requestFingerprint)
                                                + " ; <http://www.w3.org/2000/01/rdf-schema#label> \"confirmation-idempotency\" ; <http://www.w3.org/2000/01/rdf-schema#comment> "
                                                + literal(attemptToken)
                                                + " . }",
                                router.route(project, GraphRole.CANDIDATES),
                                candidate,
                                project.value(),
                                keyRecord == null
                                        ? ""
                                        : "FILTER NOT EXISTS { GRAPH <"
                                                + router.route(project, GraphRole.PROVENANCE)
                                                + "> { <"
                                                + keyRecord
                                                + "> ?p ?o } }");
        gateway.update(update);
        if (keyRecord != null
                && !gateway.ask("ASK { GRAPH <" + router.route(project, GraphRole.PROVENANCE) + "> { <" + keyRecord
                        + "> <http://www.w3.org/1999/02/22-rdf-syntax-ns#value> " + literal(requestFingerprint)
                        + " } }")) {
            throw new IllegalArgumentException("idempotency key was already used for another request");
        }
        if (!gateway.ask(
                "ASK { GRAPH <" + router.route(project, GraphRole.ASSERTED) + "> { <" + item + "> ?p ?o } }")) {
            throw new IllegalStateException("candidate does not conform or has a terminal decision");
        }
        return item;
    }

    /** Confirms once per durable key; a matching retry returns the deterministic asserted IRI. */
    public synchronized String confirm(
            ProjectId project,
            String candidateId,
            String reviewerId,
            String idempotencyKey,
            String label,
            LocalDate validFrom) {
        return confirmDecision(project, candidateId, reviewerId, idempotencyKey, label, validFrom)
                .itemIri();
    }

    /** Atomically confirms or reports that the same durable idempotency record already won the race. */
    public synchronized Confirmation confirmDecision(
            ProjectId project,
            String candidateId,
            String reviewerId,
            String idempotencyKey,
            String label,
            LocalDate validFrom) {
        requireKey(idempotencyKey);
        var item =
                "https://w3id.org/projecta/data/project/" + project.value() + "/requirement/confirm-" + idempotencyKey;
        var record = idempotencyRecord(project, idempotencyKey);
        var fingerprint = "confirm|" + candidateId + "|" + label + "|" + validFrom;
        if (gateway.ask("ASK { GRAPH <" + router.route(project, GraphRole.PROVENANCE) + "> { <" + record
                + "> <http://www.w3.org/1999/02/22-rdf-syntax-ns#value> " + literal(fingerprint) + " } }")) {
            return new Confirmation(item, true);
        }
        if (gateway.ask(
                "ASK { GRAPH <" + router.route(project, GraphRole.PROVENANCE) + "> { <" + record + "> ?p ?o } }")) {
            throw new IllegalArgumentException("idempotency key was already used for another request");
        }
        var attemptToken = UUID.randomUUID().toString();
        confirm(project, candidateId, reviewerId, label, validFrom, item, record, fingerprint, attemptToken);
        var created = gateway.ask("ASK { GRAPH <" + router.route(project, GraphRole.PROVENANCE) + "> { <" + record
                + "> <http://www.w3.org/2000/01/rdf-schema#comment> " + literal(attemptToken) + " } }");
        return new Confirmation(item, !created);
    }

    /** Returns whether an identical confirmation was durably committed before this request. */
    public boolean hasConfirmationReplay(
            ProjectId project, String candidateId, String idempotencyKey, String label, LocalDate validFrom) {
        requireKey(idempotencyKey);
        var fingerprint = "confirm|" + candidateId + "|" + label + "|" + validFrom;
        return gateway.ask("ASK { GRAPH <" + router.route(project, GraphRole.PROVENANCE) + "> { <"
                + idempotencyRecord(project, idempotencyKey)
                + "> <http://www.w3.org/1999/02/22-rdf-syntax-ns#value> "
                + literal(fingerprint)
                + " } }");
    }

    /**
     * Atomically rejects a candidate and stores the human reason and idempotency record in Fuseki.
     *
     * <p>The returned result marks whether this request committed the decision or replayed it.
     */
    public synchronized Rejection reject(
            ProjectId project, String candidateId, String reviewerId, String idempotencyKey, String reason) {
        require(idempotencyKey, "idempotency key");
        if (reason == null || reason.isBlank() || reason.length() > 4096) {
            throw new IllegalArgumentException("rejection reason is invalid");
        }
        var candidate = candidateIri(project, candidateId);
        requireKey(idempotencyKey);
        var keyRecord = idempotencyRecord(project, idempotencyKey);
        var fingerprint = "reject|" + candidateId + "|" + reason;
        if (gateway.ask("ASK { GRAPH <" + router.route(project, GraphRole.PROVENANCE) + "> { <" + keyRecord
                + "> <http://www.w3.org/1999/02/22-rdf-syntax-ns#value> " + literal(fingerprint) + " } }")) {
            return new Rejection(candidateId, reason, candidate + "/activity/reject-" + idempotencyKey, true);
        }
        if (gateway.ask(
                "ASK { GRAPH <" + router.route(project, GraphRole.PROVENANCE) + "> { <" + keyRecord + "> ?p ?o } }")) {
            throw new IllegalArgumentException("idempotency key was already used for another request");
        }
        var activity = candidate + "/activity/reject-" + idempotencyKey;
        var attemptToken = UUID.randomUUID().toString();
        var now = OffsetDateTime.now().toString();
        var update =
                """
                DELETE { GRAPH <%s> { <%s> <https://w3id.org/projecta/ontology/candidateStatus> ?status } }
                INSERT {
                  GRAPH <%s> { <%s> <https://w3id.org/projecta/ontology/candidateStatus> <https://w3id.org/projecta/ontology/rejected> ; <https://w3id.org/projecta/ontology/rejectionReason> %s . }
                  GRAPH <%s> { <%s> a <http://www.w3.org/ns/prov#Activity> ; <http://www.w3.org/ns/prov#used> <%s> ; <http://www.w3.org/ns/prov#wasAssociatedWith> <%s> ; <https://w3id.org/projecta/ontology/reviewDecision> <https://w3id.org/projecta/ontology/rejected> ; <https://w3id.org/projecta/ontology/rejectionReason> %s ; <http://www.w3.org/ns/prov#endedAtTime> \"%s\"^^<http://www.w3.org/2001/XMLSchema#dateTime> . <%s> <http://www.w3.org/1999/02/22-rdf-syntax-ns#value> %s ; <http://www.w3.org/2000/01/rdf-schema#label> \"rejection-idempotency\" ; <http://www.w3.org/2000/01/rdf-schema#comment> %s . }
                }
                WHERE { GRAPH <%s> { <%s> a <https://w3id.org/projecta/ontology/Candidate> ; <https://w3id.org/projecta/ontology/candidateStatus> ?status . FILTER(?status IN (<https://w3id.org/projecta/ontology/validated>, <https://w3id.org/projecta/ontology/pending-review>)) } FILTER NOT EXISTS { GRAPH <%s> { <%s> ?p ?o } } }
                """
                        .formatted(
                                router.route(project, GraphRole.CANDIDATES),
                                candidate,
                                router.route(project, GraphRole.CANDIDATES),
                                candidate,
                                literal(reason),
                                router.route(project, GraphRole.PROVENANCE),
                                activity,
                                candidate,
                                reviewerIri(project, reviewerId),
                                literal(reason),
                                now,
                                keyRecord,
                                literal(fingerprint),
                                literal(attemptToken),
                                router.route(project, GraphRole.CANDIDATES),
                                candidate,
                                router.route(project, GraphRole.PROVENANCE),
                                keyRecord);
        gateway.update(update);
        if (!gateway.ask("ASK { GRAPH <" + router.route(project, GraphRole.PROVENANCE) + "> { <" + keyRecord
                + "> <http://www.w3.org/1999/02/22-rdf-syntax-ns#value> " + literal(fingerprint) + " } }")) {
            throw new IllegalArgumentException("idempotency key was already used for another request");
        }
        if (!gateway.ask(
                "ASK { GRAPH <" + router.route(project, GraphRole.PROVENANCE) + "> { <" + keyRecord + "> ?p ?o } }")) {
            throw new IllegalStateException("candidate does not conform or has a terminal decision");
        }
        var created = gateway.ask("ASK { GRAPH <" + router.route(project, GraphRole.PROVENANCE) + "> { <" + keyRecord
                + "> <http://www.w3.org/2000/01/rdf-schema#comment> " + literal(attemptToken) + " } }");
        return new Rejection(candidateId, reason, activity, !created);
    }

    /** Returns whether an identical rejection was durably committed before this request. */
    public boolean hasRejectionReplay(ProjectId project, String candidateId, String idempotencyKey, String reason) {
        requireKey(idempotencyKey);
        var fingerprint = "reject|" + candidateId + "|" + reason;
        return gateway.ask("ASK { GRAPH <" + router.route(project, GraphRole.PROVENANCE) + "> { <"
                + idempotencyRecord(project, idempotencyKey)
                + "> <http://www.w3.org/1999/02/22-rdf-syntax-ns#value> "
                + literal(fingerprint)
                + " } }");
    }

    private String candidateIri(ProjectId project, String candidateId) {
        require(candidateId, "candidate ID");
        return "https://w3id.org/projecta/data/project/" + project.value() + "/candidate/" + candidateId;
    }

    private String reviewerIri(ProjectId project, String reviewerId) {
        require(reviewerId, "reviewer ID");
        return "https://w3id.org/projecta/data/project/" + project.value() + "/person/" + reviewerId;
    }

    private String idempotencyRecord(ProjectId project, String key) {
        return "https://w3id.org/projecta/data/project/" + project.value() + "/idempotency/" + key;
    }

    private static String literal(String value) {
        return "\"" + value.replace("\\", "\\\\").replace("\"", "\\\"") + "\"";
    }

    private static void require(String value, String name) {
        if (value == null || value.isBlank() || !value.matches("[a-zA-Z0-9][a-zA-Z0-9 -]{0,127}"))
            throw new IllegalArgumentException(name + " is invalid");
    }

    private static void requireKey(String value) {
        if (value == null || !value.matches("[A-Za-z0-9-]{1,128}")) {
            throw new IllegalArgumentException("idempotency key is invalid");
        }
    }

    public record Rejection(String candidateId, String reason, String activityIri, boolean replayed) {}

    public record Confirmation(String itemIri, boolean replayed) {}
}
