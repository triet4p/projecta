package org.projecta.semanticcore;

import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import org.apache.jena.query.Dataset;
import org.apache.jena.query.ReadWrite;
import org.apache.jena.rdf.model.Model;
import org.apache.jena.rdf.model.ModelFactory;
import org.apache.jena.rdf.model.RDFNode;
import org.apache.jena.rdf.model.ResourceFactory;
import org.apache.jena.rdf.model.Statement;
import org.apache.jena.vocabulary.RDF;
import org.apache.jena.vocabulary.RDFS;

/**
 * Atomic, approved-only boundary for moving reviewed candidates into the asserted graph.
 *
 * <p>This service is deliberately separate from the legacy confirmation service. Its default
 * authorization is disabled, so production composition must make an explicit semantic-owner
 * decision before this boundary can be called.
 */
public final class ApprovedAssertionMaterializationService {
    private static final String PROJECTA = "https://w3id.org/projecta/ontology/";
    private static final String PROV = "http://www.w3.org/ns/prov#";
    private static final String BASE = "https://w3id.org/projecta/data/project/";
    private static final String META_PREFIX = "projecta-approved-candidate/v1|";
    private static final String RECEIPT_PREFIX = "review-receipt.v1|";
    private final Dataset dataset;
    private final GraphIriRouter router;
    private final CandidateValidationService candidateValidationService;
    private final Model releasedShapes;
    private final MaterializationAuthorization authorization;
    private final Runnable afterWritesHook;

    public ApprovedAssertionMaterializationService(
            Dataset dataset,
            GraphIriRouter router,
            CandidateValidationService candidateValidationService,
            Model releasedShapes) {
        this(
                dataset,
                router,
                candidateValidationService,
                releasedShapes,
                MaterializationAuthorization.disabled(),
                () -> {});
    }

    public ApprovedAssertionMaterializationService(
            Dataset dataset,
            GraphIriRouter router,
            CandidateValidationService candidateValidationService,
            Model releasedShapes,
            MaterializationAuthorization authorization,
            Runnable afterWritesHook) {
        this.dataset = dataset;
        this.router = router;
        this.candidateValidationService = candidateValidationService;
        this.releasedShapes = releasedShapes == null ? ModelFactory.createDefaultModel() : releasedShapes;
        this.authorization = authorization == null ? MaterializationAuthorization.disabled() : authorization;
        this.afterWritesHook = afterWritesHook == null ? () -> {} : afterWritesHook;
    }

    public MaterializationResult materialize(ApprovedAssertionPlan plan) {
        if (plan == null) {
            throw new IllegalArgumentException("approved assertion plan is required");
        }
        authorization.requireEnabled();
        var project = new ProjectId(plan.project());
        var bodyDigest = plan.bodyDigest();
        var idempotencyIri = idempotencyIri(project, plan.idempotencyKey());

        var replay = readExistingResult(project, idempotencyIri, bodyDigest, plan);
        if (replay != null) {
            return replay;
        }

        dataset.begin(ReadWrite.WRITE);
        try {
            // Every precondition is checked again in the same transaction as the writes.
            var existing = findIdempotency(dataset.getNamedModel(graph(project, GraphRole.PROVENANCE)), idempotencyIri);
            if (existing != null) {
                return existing.bodyDigest().equals(bodyDigest)
                        ? replayResult(existing, plan)
                        : conflict("idempotency key is already bound to a different plan");
            }
            validateBeforeMutation(plan, project);
            var asserted = dataset.getNamedModel(graph(project, GraphRole.ASSERTED));
            var candidates = dataset.getNamedModel(graph(project, GraphRole.CANDIDATES));
            var provenance = dataset.getNamedModel(graph(project, GraphRole.PROVENANCE));
            var expected = graphRevision(asserted);
            if (!expected.equals(plan.expectedAssertedGraphRevision())) {
                throw new IllegalStateException("asserted graph revision is stale");
            }

            var projectResource = ResourceFactory.createResource(BASE + project.value());
            var provActivity = provenance.createResource(plan.provenanceActivityIri());
            for (int index = 0; index < plan.candidates().size(); index++) {
                var candidatePlan = plan.candidates().get(index);
                var candidate = candidates.getResource(candidatePlan.candidateIri());
                var item = asserted.createResource(candidatePlan.assertedIri());
                item.addProperty(RDF.type, ResourceFactory.createResource(PROJECTA + "KnowledgeItem"));
                item.addProperty(RDF.type, ResourceFactory.createResource(PROJECTA + "Requirement"));
                item.addLiteral(RDFS.label, candidatePlan.label());
                item.addProperty(ResourceFactory.createProperty(PROV + "wasDerivedFrom"), candidate);
                item.addProperty(
                        ResourceFactory.createProperty(PROV + "wasAttributedTo"),
                        ResourceFactory.createResource(candidatePlan.reviewerIri()));
                item.addProperty(ResourceFactory.createProperty(PROJECTA + "belongsToProject"), projectResource);
                item.addProperty(
                        ResourceFactory.createProperty(PROJECTA + "validFrom"),
                        asserted.createTypedLiteral(
                                candidatePlan.validFrom().toString(),
                                org.apache.jena.datatypes.xsd.XSDDatatype.XSDdate));

                var activity = index == 0
                        ? provActivity
                        : provenance.createResource(plan.provenanceActivityIri() + "/" + index);
                activity.addProperty(RDF.type, ResourceFactory.createResource(PROV + "Activity"));
                activity.addProperty(ResourceFactory.createProperty(PROV + "used"), candidate);
                activity.addProperty(ResourceFactory.createProperty(PROV + "generated"), item);
                activity.addProperty(
                        ResourceFactory.createProperty(PROV + "wasAssociatedWith"),
                        ResourceFactory.createResource(candidatePlan.reviewerIri()));
                activity.addProperty(
                        ResourceFactory.createProperty(PROJECTA + "reviewDecision"),
                        ResourceFactory.createResource(PROJECTA + "confirmed"));
                activity.addProperty(
                        ResourceFactory.createProperty(PROV + "endedAtTime"),
                        provenance.createTypedLiteral(
                                OffsetDateTime.now().toString(),
                                org.apache.jena.datatypes.xsd.XSDDatatype.XSDdateTime));
                activity.addLiteral(
                        RDFS.comment,
                        RECEIPT_PREFIX + candidatePlan.reviewReceiptDigest()
                                + "|constrainedRelationContractVersion="
                                + candidatePlan.constrainedRelationContractVersion()
                                + "|evidenceSelectionVersion=" + candidatePlan.evidenceSelectionVersion()
                                + "|evidenceDigest=" + candidatePlan.evidenceDigest());
                var statement = provenance.createResource(candidatePlan.assertedIri() + "/statement/valid-from");
                statement.addProperty(RDF.type, RDF.Statement);
                statement.addProperty(RDF.subject, item);
                statement.addProperty(RDF.predicate, ResourceFactory.createProperty(PROJECTA + "validFrom"));
                statement.addProperty(
                        RDF.object,
                        provenance.createTypedLiteral(
                                candidatePlan.validFrom().toString(),
                                org.apache.jena.datatypes.xsd.XSDDatatype.XSDdate));
                candidates.removeAll(candidate, ResourceFactory.createProperty(PROJECTA + "candidateStatus"), null);
                candidate.addProperty(
                        ResourceFactory.createProperty(PROJECTA + "candidateStatus"),
                        ResourceFactory.createResource(PROJECTA + "asserted"));
            }

            var materializationRevision = graphRevision(asserted);
            var idempotency = provenance.createResource(idempotencyIri);
            idempotency.addLiteral(RDFS.label, "materialization-idempotency");
            idempotency.addLiteral(RDF.value, bodyDigest);
            idempotency.addLiteral(RDFS.comment, materializationRevision);
            idempotency.addProperty(ResourceFactory.createProperty(PROV + "wasGeneratedBy"), provActivity);
            afterWritesHook.run();
            validateShapeBoundary(project);
            dataset.commit();
            return new MaterializationResult(
                    "accepted",
                    ApprovedAssertionPlan.CONTRACT_VERSION,
                    bodyDigest,
                    materializationRevision,
                    plan.candidates().stream()
                            .map(ApprovedAssertionPlan.ApprovedCandidate::assertedIri)
                            .toList());
        } catch (RuntimeException exception) {
            dataset.abort();
            throw exception;
        } finally {
            dataset.end();
        }
    }

    /** Deterministic revision used for optimistic asserted-graph concurrency. */
    public static String graphRevision(Model model) {
        var lines = new ArrayList<String>();
        var statements = model.listStatements();
        while (statements.hasNext()) {
            lines.add(statementKey(statements.next()));
        }
        lines.sort(String::compareTo);
        return ApprovedAssertionPlan.digest(String.join("\n", lines));
    }

    private void validateBeforeMutation(ApprovedAssertionPlan plan, ProjectId project) {
        var candidates = dataset.getNamedModel(graph(project, GraphRole.CANDIDATES));
        if (!candidateValidationService.validate(project).conforms()) {
            throw new IllegalArgumentException("candidate graph does not conform to released shapes");
        }
        var status = ResourceFactory.createProperty(PROJECTA + "candidateStatus");
        var belongsToProject = ResourceFactory.createProperty(PROJECTA + "belongsToProject");
        var confirmed = ResourceFactory.createResource(PROJECTA + "confirmed");
        var seen = new HashSet<String>();
        for (var candidatePlan : plan.candidates()) {
            if (!seen.add(candidatePlan.candidateIri())) {
                throw new IllegalArgumentException("approved plan contains a duplicate candidate");
            }
            var expectedPrefix = BASE + project.value() + "/candidate/";
            if (!candidatePlan.candidateIri().startsWith(expectedPrefix)) {
                throw new IllegalArgumentException("candidate is outside the project scope");
            }
            var candidate = candidates.getResource(candidatePlan.candidateIri());
            if (!candidates.containsResource(candidate)
                    || !candidates.contains(candidate, status, confirmed)
                    || !candidates.contains(
                            candidate, belongsToProject, ResourceFactory.createResource(BASE + project.value()))
                    || !candidates.contains(
                            candidate,
                            ResourceFactory.createProperty(PROJECTA + "proposedOntologyVersion"),
                            candidatePlan.ontologyVersion())) {
                throw new IllegalStateException("candidate is not confirmed and project-scoped");
            }
            var comment = candidates.listStatements(candidate, RDFS.comment, (RDFNode) null).toList().stream()
                    .map(Statement::getObject)
                    .filter(RDFNode::isLiteral)
                    .map(node -> node.asLiteral().getString())
                    .filter(value -> value.startsWith(META_PREFIX))
                    .findFirst()
                    .orElseThrow(() -> new IllegalArgumentException("candidate review binding is incomplete"));
            if (!metadataMatches(comment, candidatePlan)) {
                throw new IllegalArgumentException("candidate revision/source/review binding does not match the plan");
            }
            if (dataset.getNamedModel(graph(project, GraphRole.ASSERTED))
                    .containsResource(ResourceFactory.createResource(candidatePlan.assertedIri()))) {
                throw new IllegalStateException("asserted item already exists for a new materialization");
            }
        }
        var asserted = dataset.getNamedModel(graph(project, GraphRole.ASSERTED));
        if (!graphRevision(asserted).equals(plan.expectedAssertedGraphRevision())) {
            throw new IllegalStateException("asserted graph revision is stale");
        }
        var provenance = dataset.getNamedModel(graph(project, GraphRole.PROVENANCE));
        if (provenance.containsResource(ResourceFactory.createResource(plan.provenanceActivityIri()))) {
            throw new IllegalStateException("provenance activity already exists for a new materialization");
        }
    }

    private void validateShapeBoundary(ProjectId project) {
        if (releasedShapes.isEmpty()) {
            return;
        }
        var closure = ModelFactory.createDefaultModel();
        for (var role : GraphRole.values()) {
            closure.add(dataset.getNamedModel(graph(project, role)));
        }
        var report = org.apache.jena.shacl.ShaclValidator.get().validate(releasedShapes.getGraph(), closure.getGraph());
        if (!report.conforms()) {
            throw new IllegalStateException("materialization would violate released SHACL shapes");
        }
    }

    private MaterializationResult readExistingResult(
            ProjectId project, String idempotencyIri, String bodyDigest, ApprovedAssertionPlan plan) {
        dataset.begin(ReadWrite.READ);
        try {
            var existing = findIdempotency(dataset.getNamedModel(graph(project, GraphRole.PROVENANCE)), idempotencyIri);
            if (existing == null) {
                return null;
            }
            if (!existing.bodyDigest().equals(bodyDigest)) {
                throw new IllegalStateException("idempotency key is already bound to a different plan");
            }
            return replayResult(existing, plan);
        } finally {
            dataset.end();
        }
    }

    private static MaterializationResult replayResult(Idempotency existing, ApprovedAssertionPlan plan) {
        return new MaterializationResult(
                "replayed",
                ApprovedAssertionPlan.CONTRACT_VERSION,
                existing.bodyDigest(),
                existing.materializationRevision(),
                plan.candidates().stream()
                        .map(ApprovedAssertionPlan.ApprovedCandidate::assertedIri)
                        .toList());
    }

    private static MaterializationResult conflict(String message) {
        throw new IllegalStateException(message);
    }

    private static Idempotency findIdempotency(Model provenance, String iri) {
        var resource = provenance.getResource(iri);
        if (!provenance.containsResource(resource)) {
            return null;
        }
        var body = provenance.getProperty(resource, RDF.value);
        var revision = provenance.getProperty(resource, RDFS.comment);
        if (body == null
                || !body.getObject().isLiteral()
                || revision == null
                || !revision.getObject().isLiteral()) {
            throw new IllegalStateException("materialization idempotency record is incomplete");
        }
        return new Idempotency(body.getString(), revision.getString());
    }

    private static boolean metadataMatches(String value, ApprovedAssertionPlan.ApprovedCandidate candidate) {
        var fields = new HashMap<String, String>();
        for (var field : value.substring(META_PREFIX.length()).split("\\|")) {
            var parts = field.split("=", 2);
            if (parts.length == 2) {
                fields.put(parts[0], parts[1]);
            }
        }
        return Integer.toString(candidate.candidateRevision()).equals(fields.get("candidateRevision"))
                && candidate.sourceVersionId().equals(fields.get("sourceVersionId"))
                && Integer.toString(candidate.sourceVersionRevision()).equals(fields.get("sourceVersionRevision"))
                && candidate.reviewReceiptDigest().equals(fields.get("reviewReceiptDigest"))
                && candidate.evidenceDigest().equals(fields.get("evidenceDigest"))
                && candidate
                        .constrainedRelationContractVersion()
                        .equals(fields.get("constrainedRelationContractVersion"))
                && candidate.evidenceSelectionVersion().equals(fields.get("evidenceSelectionVersion"));
    }

    private String graph(ProjectId project, GraphRole role) {
        return router.route(project, role).toString();
    }

    private static String idempotencyIri(ProjectId project, String key) {
        return BASE + project.value() + "/materialization-idempotency/"
                + ApprovedAssertionPlan.digest(key).substring("sha256:".length());
    }

    private static String statementKey(Statement statement) {
        return nodeKey(statement.getSubject()) + " " + statement.getPredicate().getURI() + " "
                + nodeKey(statement.getObject());
    }

    private static String nodeKey(RDFNode node) {
        if (node.isURIResource()) {
            return "<" + node.asResource().getURI() + ">";
        }
        if (node.isLiteral()) {
            var literal = node.asLiteral();
            return "\"" + literal.getLexicalForm() + "\"^^" + literal.getDatatypeURI();
        }
        return node.toString();
    }

    private record Idempotency(String bodyDigest, String materializationRevision) {}
}
