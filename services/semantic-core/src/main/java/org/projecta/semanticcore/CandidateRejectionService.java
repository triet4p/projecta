package org.projecta.semanticcore;

import java.time.OffsetDateTime;
import java.util.HashMap;
import java.util.Map;
import java.util.Objects;
import java.util.UUID;
import org.apache.jena.datatypes.xsd.XSDDatatype;
import org.apache.jena.query.Dataset;
import org.apache.jena.query.ReadWrite;
import org.apache.jena.rdf.model.ResourceFactory;
import org.apache.jena.vocabulary.RDF;

/** Records a candidate rejection and its provenance without promoting an asserted item. */
public final class CandidateRejectionService {
    private static final String PROJECTA = "https://w3id.org/projecta/ontology/";
    private static final String PROV = "http://www.w3.org/ns/prov#";

    private final Dataset dataset;
    private final GraphIriRouter router;
    private final Map<IdempotencyScope, RejectionResult> completedRejections = new HashMap<>();

    public CandidateRejectionService(Dataset dataset, GraphIriRouter router) {
        this.dataset = Objects.requireNonNull(dataset, "dataset is required");
        this.router = Objects.requireNonNull(router, "graph router is required");
    }

    /**
     * Rejects one candidate. Replaying an identical request returns the original result without a
     * second activity; using the key with a different reason is rejected.
     */
    public synchronized RejectionResult reject(
            ProjectId projectId, String candidateIri, String reviewerIri, String idempotencyKey, String reason) {
        requireNonBlank(candidateIri, "candidate IRI");
        requireNonBlank(reviewerIri, "reviewer IRI");
        requireNonBlank(idempotencyKey, "idempotency key");
        requireNonBlank(reason, "rejection reason");

        var scope = new IdempotencyScope(projectId, idempotencyKey);
        var priorResult = completedRejections.get(scope);
        if (priorResult != null) {
            if (!priorResult.candidateIri().equals(candidateIri)
                    || !priorResult.reason().equals(reason)) {
                throw new IllegalArgumentException("idempotency key was reused with a different request body");
            }
            return priorResult.asReplay();
        }

        dataset.begin(ReadWrite.WRITE);
        try {
            var candidates = dataset.getNamedModel(
                    router.route(projectId, GraphRole.CANDIDATES).toString());
            var candidate = candidates.getResource(candidateIri);
            if (!candidates.containsResource(candidate)) {
                throw new IllegalArgumentException("candidate is not in the trusted project graph");
            }
            var status = ResourceFactory.createProperty(PROJECTA + "candidateStatus");
            var rejected = ResourceFactory.createResource(PROJECTA + "rejected");
            if (candidates.contains(candidate, status, rejected)) {
                throw new IllegalStateException("candidate is already rejected");
            }
            if (candidates.contains(candidate, status, ResourceFactory.createResource(PROJECTA + "asserted"))) {
                throw new IllegalStateException("candidate was already confirmed");
            }

            var provenance = dataset.getNamedModel(
                    router.route(projectId, GraphRole.PROVENANCE).toString());
            var activityIri = candidateIri + "/activity/reject-" + UUID.randomUUID();
            var activity = provenance.createResource(activityIri);
            activity.addProperty(RDF.type, ResourceFactory.createResource(PROV + "Activity"));
            activity.addProperty(ResourceFactory.createProperty(PROV + "used"), candidate);
            activity.addProperty(
                    ResourceFactory.createProperty(PROV + "wasAssociatedWith"),
                    ResourceFactory.createResource(reviewerIri));
            activity.addProperty(ResourceFactory.createProperty(PROJECTA + "reviewDecision"), rejected);
            activity.addLiteral(ResourceFactory.createProperty(PROJECTA + "rejectionReason"), reason);
            activity.addProperty(
                    ResourceFactory.createProperty(PROV + "endedAtTime"),
                    provenance.createTypedLiteral(OffsetDateTime.now().toString(), XSDDatatype.XSDdateTime));

            candidates.removeAll(candidate, status, null);
            candidates.removeAll(candidate, ResourceFactory.createProperty(PROJECTA + "rejectionReason"), null);
            candidate.addProperty(status, rejected);
            candidate.addLiteral(ResourceFactory.createProperty(PROJECTA + "rejectionReason"), reason);
            dataset.commit();

            var result = new RejectionResult(candidateIri, activityIri, reason, false);
            completedRejections.put(scope, result);
            return result;
        } catch (RuntimeException exception) {
            dataset.abort();
            throw exception;
        } finally {
            dataset.end();
        }
    }

    private static void requireNonBlank(String value, String name) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException(name + " is required");
        }
    }

    private record IdempotencyScope(ProjectId projectId, String key) {}

    public record RejectionResult(String candidateIri, String activityIri, String reason, boolean replayed) {
        private RejectionResult asReplay() {
            return new RejectionResult(candidateIri, activityIri, reason, true);
        }
    }
}
