package org.projecta.semanticcore;

import java.util.HashMap;
import java.util.Map;
import org.apache.jena.query.Dataset;
import org.apache.jena.query.ReadWrite;
import org.apache.jena.rdf.model.Model;
import org.apache.jena.rdf.model.ModelFactory;
import org.apache.jena.rdf.model.RDFNode;
import org.apache.jena.rdf.model.Resource;
import org.apache.jena.rdf.model.ResourceFactory;
import org.apache.jena.rdf.model.Statement;
import org.apache.jena.vocabulary.RDF;
import org.apache.jena.vocabulary.RDFS;

/**
 * Versioned invalidation and transactional rebuild boundary for inferred projections.
 *
 * <p>Only the fixed snapshot marker is current. Earlier inferred facts remain in the inferred
 * graph as historical resources after invalidation and are never advertised as current.
 */
public final class InferenceInvalidationRebuildService {
    public static final String CONTRACT_VERSION = "inference-rebuild-plan.v1";
    public static final String RULE_VERSION = "m4.v1";
    public static final String ONTOLOGY_VERSION = "0.5.0";
    private static final String PROJECTA = "https://w3id.org/projecta/ontology/";
    private static final String PROV = "http://www.w3.org/ns/prov#";
    private static final String BASE = "https://w3id.org/projecta/data/project/";
    private static final String STATE_PREFIX = "inference-state.v1|";
    private static final String SNAPSHOT_SUFFIX = "/inferred/snapshot-m4-v1";
    private final Dataset dataset;
    private final GraphIriRouter router;
    private final Model releasedShapes;
    private final InferenceRebuildAuthorization authorization;
    private final Runnable afterWritesHook;

    public InferenceInvalidationRebuildService(Dataset dataset, GraphIriRouter router, Model releasedShapes) {
        this(dataset, router, releasedShapes, InferenceRebuildAuthorization.disabled(), () -> {});
    }

    public InferenceInvalidationRebuildService(
            Dataset dataset,
            GraphIriRouter router,
            Model releasedShapes,
            InferenceRebuildAuthorization authorization,
            Runnable afterWritesHook) {
        this.dataset = dataset;
        this.router = router;
        this.releasedShapes = releasedShapes == null ? ModelFactory.createDefaultModel() : releasedShapes;
        this.authorization = authorization == null ? InferenceRebuildAuthorization.disabled() : authorization;
        this.afterWritesHook = afterWritesHook == null ? () -> {} : afterWritesHook;
    }

    public InferenceRebuildResult invalidate(InferenceInvalidation request) {
        if (request == null) {
            throw new IllegalArgumentException("invalidation request is required");
        }
        authorization.requireEnabled();
        var project = new ProjectId(request.project());
        var provenance = dataset.getNamedModel(graph(project, GraphRole.PROVENANCE));
        var idempotencyIri = invalidationIdempotencyIri(project, request.idempotencyKey());
        var replay =
                readIdempotency(provenance, idempotencyIri, request.bodyDigest(), request.project(), "invalidation");
        if (replay != null) {
            return replay;
        }

        dataset.begin(ReadWrite.WRITE);
        try {
            provenance = dataset.getNamedModel(graph(project, GraphRole.PROVENANCE));
            var existing = readIdempotency(
                    provenance, idempotencyIri, request.bodyDigest(), request.project(), "invalidation");
            if (existing != null) {
                return existing;
            }
            var inferred = dataset.getNamedModel(graph(project, GraphRole.INFERRED));
            var current = currentSnapshot(inferred, project);
            if (!current.revision().equals(request.expectedCurrentInferenceRevision())) {
                throw new IllegalStateException("inference revision is stale");
            }
            preserveHistoricalSnapshot(inferred, project, current);
            markHistoricalFacts(inferred, current.revision());
            var snapshot = inferred.getResource(snapshotIri(project));
            inferred.removeAll(snapshot, null, null);
            snapshot.addProperty(RDF.type, ResourceFactory.createResource(PROJECTA + "InferenceSnapshot"));
            snapshot.addProperty(
                    ResourceFactory.createProperty(PROJECTA + "belongsToProject"),
                    ResourceFactory.createResource(BASE + project.value()));
            snapshot.addLiteral(
                    RDFS.comment,
                    STATE_PREFIX + "state=stale|revision=" + current.revision() + "|cause=" + request.cause());
            var activity = provenance.createResource(BASE + project.value() + "/activity/inference-invalidation/"
                    + request.bodyDigest().substring(7));
            activity.addProperty(RDF.type, ResourceFactory.createResource(PROV + "Activity"));
            activity.addProperty(ResourceFactory.createProperty(PROV + "used"), snapshot);
            activity.addProperty(ResourceFactory.createProperty(PROV + "generated"), snapshot);
            activity.addLiteral(
                    RDFS.comment,
                    "inference-invalidation.v1|cause=" + request.cause() + "|previousRevision=" + current.revision());
            writeIdempotency(provenance, idempotencyIri, request.bodyDigest(), current.revision());
            dataset.commit();
            return new InferenceRebuildResult(
                    "invalidated",
                    "inference-invalidation.v1",
                    request.project(),
                    current.revision(),
                    null,
                    null,
                    null,
                    null);
        } catch (RuntimeException exception) {
            dataset.abort();
            throw exception;
        } finally {
            dataset.end();
        }
    }

    public InferenceRebuildResult rebuild(InferenceRebuildPlan plan) {
        if (plan == null) {
            throw new IllegalArgumentException("inference rebuild plan is required");
        }
        authorization.requireEnabled();
        var project = new ProjectId(plan.project());
        var bodyDigest = plan.bodyDigest();
        var idempotencyIri = rebuildIdempotencyIri(project, plan.idempotencyKey());
        var replay = readIdempotency(
                dataset.getNamedModel(graph(project, GraphRole.PROVENANCE)),
                idempotencyIri,
                bodyDigest,
                plan.project(),
                "rebuild");
        if (replay != null) {
            return replay;
        }

        dataset.begin(ReadWrite.WRITE);
        try {
            var provenance = dataset.getNamedModel(graph(project, GraphRole.PROVENANCE));
            var existing = readIdempotency(provenance, idempotencyIri, bodyDigest, plan.project(), "rebuild");
            if (existing != null) {
                return existing;
            }
            var asserted = dataset.getNamedModel(graph(project, GraphRole.ASSERTED));
            var actualAssertedRevision = ApprovedAssertionMaterializationService.graphRevision(asserted);
            if (!actualAssertedRevision.equals(plan.assertedGraphRevision())) {
                throw new IllegalStateException("asserted graph revision is stale");
            }
            rejectForeignAssertions(asserted, project);
            var inferred = dataset.getNamedModel(graph(project, GraphRole.INFERRED));
            var current = currentSnapshot(inferred, project);
            if (!current.revision().equals(plan.expectedCurrentInferenceRevision())) {
                throw new IllegalStateException("inference revision is stale");
            }
            if (!current.stale() && !"none".equals(current.revision())) {
                throw new IllegalStateException("inference must be invalidated before rebuild");
            }

            var staged = buildStagedProjection(asserted, project, plan, bodyDigest);
            validateShapes(staged);
            var projectionRevision = ApprovedAssertionMaterializationService.graphRevision(staged);
            preserveHistoricalSnapshot(inferred, project, current);
            var oldCurrent = inferred.getResource(snapshotIri(project));
            inferred.removeAll(oldCurrent, null, null);
            inferred.add(staged);
            inferred.removeAll(inferred.getResource(stagingSnapshotIri(project, bodyDigest)), null, null);
            var currentSnapshot = inferred.getResource(snapshotIri(project));
            currentSnapshot.addProperty(RDF.type, ResourceFactory.createResource(PROJECTA + "InferenceSnapshot"));
            currentSnapshot.addProperty(
                    ResourceFactory.createProperty(PROJECTA + "belongsToProject"),
                    ResourceFactory.createResource(BASE + project.value()));
            currentSnapshot.addLiteral(
                    ResourceFactory.createProperty(PROJECTA + "sourceRevision"), plan.assertedGraphRevision());
            currentSnapshot.addLiteral(ResourceFactory.createProperty(PROJECTA + "ruleVersion"), plan.ruleVersion());
            currentSnapshot.addLiteral(
                    RDFS.comment,
                    STATE_PREFIX + "state=current|revision=" + projectionRevision
                            + "|sourceVersionId=" + plan.sourceVersionId()
                            + "|sourceVersionRevision=" + plan.sourceVersionRevision()
                            + "|sourceVersionDigest=" + plan.sourceVersionDigest()
                            + "|ontologyVersion=" + plan.ontologyVersion());
            var activity = provenance.createResource(plan.rebuildActivityIri());
            activity.addProperty(RDF.type, ResourceFactory.createResource(PROV + "Activity"));
            activity.addProperty(
                    ResourceFactory.createProperty(PROV + "used"),
                    ResourceFactory.createResource(BASE + project.value()));
            activity.addProperty(ResourceFactory.createProperty(PROV + "generated"), currentSnapshot);
            activity.addLiteral(
                    RDFS.comment,
                    "inference-rebuild.v1|assertedGraphRevision=" + plan.assertedGraphRevision()
                            + "|sourceVersionId=" + plan.sourceVersionId()
                            + "|sourceVersionRevision=" + plan.sourceVersionRevision()
                            + "|sourceVersionDigest=" + plan.sourceVersionDigest()
                            + "|ontologyVersion=" + plan.ontologyVersion()
                            + "|ruleVersion=" + plan.ruleVersion());
            writeIdempotency(provenance, idempotencyIri, bodyDigest, projectionRevision);
            afterWritesHook.run();
            validateShapes(inferred);
            dataset.commit();
            return new InferenceRebuildResult(
                    "accepted",
                    CONTRACT_VERSION,
                    plan.project(),
                    projectionRevision,
                    plan.assertedGraphRevision(),
                    plan.sourceVersionId(),
                    plan.ruleVersion(),
                    null);
        } catch (RuntimeException exception) {
            dataset.abort();
            throw exception;
        } finally {
            dataset.end();
        }
    }

    private Model buildStagedProjection(
            Model asserted, ProjectId project, InferenceRebuildPlan plan, String bodyDigest) {
        var staged = ModelFactory.createDefaultModel();
        var snapshot = staged.createResource(stagingSnapshotIri(project, bodyDigest));
        snapshot.addProperty(RDF.type, ResourceFactory.createResource(PROJECTA + "InferenceSnapshot"));
        snapshot.addProperty(
                ResourceFactory.createProperty(PROJECTA + "belongsToProject"),
                ResourceFactory.createResource(BASE + project.value()));
        snapshot.addLiteral(ResourceFactory.createProperty(PROJECTA + "sourceRevision"), plan.assertedGraphRevision());
        snapshot.addLiteral(ResourceFactory.createProperty(PROJECTA + "ruleVersion"), plan.ruleVersion());
        deriveUnresolved(asserted, staged, project, plan, bodyDigest);
        deriveDelivery(asserted, staged, project, plan, bodyDigest);
        deriveImpact(asserted, staged, project, plan, bodyDigest);
        return staged;
    }

    private void deriveUnresolved(
            Model asserted, Model staged, ProjectId project, InferenceRebuildPlan plan, String digest) {
        var blocks = ResourceFactory.createProperty(PROJECTA + "blocks");
        var status = ResourceFactory.createProperty(PROJECTA + "hasWorkStatus");
        var open = ResourceFactory.createResource(PROJECTA + "Open");
        var label = ResourceFactory.createProperty("http://www.w3.org/2000/01/rdf-schema#label");
        var taskType = ResourceFactory.createResource(PROJECTA + "Task");
        var questionType = ResourceFactory.createResource(PROJECTA + "Question");
        var taskIt = asserted.listResourcesWithProperty(RDF.type, taskType);
        while (taskIt.hasNext()) {
            var task = taskIt.next();
            if (!asserted.contains(task, status, open)) {
                continue;
            }
            var questions = asserted.listSubjectsWithProperty(blocks, task).toList();
            for (var question : questions) {
                if (!asserted.contains(question, RDF.type, questionType)) {
                    continue;
                }
                var id = "unresolved-"
                        + ApprovedAssertionPlan.digest(question.getURI() + "|" + task.getURI())
                                .substring(7, 23);
                var derived = staged.createResource(
                        BASE + project.value() + "/inferred/revision/" + digest.substring(7) + "/" + id);
                addDerived(
                        staged,
                        derived,
                        "UnresolvedBlocker",
                        question,
                        task,
                        task,
                        "m4.unresolved-dependency",
                        labelValue(asserted, question),
                        plan);
            }
        }
    }

    private void deriveDelivery(
            Model asserted, Model staged, ProjectId project, InferenceRebuildPlan plan, String digest) {
        var implementsProperty = ResourceFactory.createProperty(PROJECTA + "implements");
        var status = ResourceFactory.createProperty(PROJECTA + "hasWorkStatus");
        var blocked = ResourceFactory.createResource(PROJECTA + "Blocked");
        var taskType = ResourceFactory.createResource(PROJECTA + "Task");
        var requirementType = ResourceFactory.createResource(PROJECTA + "Requirement");
        var label = ResourceFactory.createProperty("http://www.w3.org/2000/01/rdf-schema#label");
        var tasks = asserted.listResourcesWithProperty(RDF.type, taskType);
        while (tasks.hasNext()) {
            var task = tasks.next();
            if (!asserted.contains(task, status, blocked)) {
                continue;
            }
            var requirements =
                    asserted.listObjectsOfProperty(task, implementsProperty).toList();
            for (var object : requirements) {
                if (!object.isResource() || !asserted.contains(object.asResource(), RDF.type, requirementType)) {
                    continue;
                }
                var requirement = object.asResource();
                var id = "delivery-risk-"
                        + ApprovedAssertionPlan.digest(requirement.getURI() + "|" + task.getURI())
                                .substring(7, 23);
                var derived = staged.createResource(
                        BASE + project.value() + "/inferred/revision/" + digest.substring(7) + "/" + id);
                addDerived(
                        staged,
                        derived,
                        "DeliveryRisk",
                        task,
                        requirement,
                        task,
                        "m4.delivery-risk",
                        labelValue(asserted, requirement),
                        plan);
            }
        }
    }

    private void deriveImpact(
            Model asserted, Model staged, ProjectId project, InferenceRebuildPlan plan, String digest) {
        var supersededBy = ResourceFactory.createProperty(PROJECTA + "supersededBy");
        var implementsProperty = ResourceFactory.createProperty(PROJECTA + "implements");
        var requirementType = ResourceFactory.createResource(PROJECTA + "Requirement");
        var taskType = ResourceFactory.createResource(PROJECTA + "Task");
        var oldRequirements = asserted.listResourcesWithProperty(RDF.type, requirementType);
        while (oldRequirements.hasNext()) {
            var old = oldRequirements.next();
            if (!asserted.contains(old, supersededBy)) {
                continue;
            }
            var tasks =
                    asserted.listSubjectsWithProperty(implementsProperty, old).toList();
            for (var task : tasks) {
                if (!asserted.contains(task, RDF.type, taskType)) {
                    continue;
                }
                var id = "impact-review-"
                        + ApprovedAssertionPlan.digest(old.getURI() + "|" + task.getURI())
                                .substring(7, 23);
                var derived = staged.createResource(
                        BASE + project.value() + "/inferred/revision/" + digest.substring(7) + "/" + id);
                addDerived(
                        staged,
                        derived,
                        "ImpactReview",
                        old,
                        task,
                        task,
                        "m4.impact-review",
                        labelValue(asserted, old),
                        plan);
            }
        }
    }

    private void addDerived(
            Model staged,
            Resource derived,
            String type,
            Resource first,
            Resource second,
            Resource task,
            String ruleIdentifier,
            String label,
            InferenceRebuildPlan plan) {
        derived.addProperty(RDF.type, ResourceFactory.createResource(PROJECTA + type));
        derived.addProperty(
                ResourceFactory.createProperty(PROJECTA + "belongsToProject"),
                ResourceFactory.createResource(BASE + plan.project()));
        derived.addProperty(ResourceFactory.createProperty(PROJECTA + "derivedFromAssertion"), first);
        derived.addProperty(ResourceFactory.createProperty(PROJECTA + "derivedFromAssertion"), second);
        derived.addProperty(ResourceFactory.createProperty(PROJECTA + "aboutTask"), task);
        derived.addLiteral(ResourceFactory.createProperty(PROJECTA + "ruleIdentifier"), ruleIdentifier);
        derived.addLiteral(ResourceFactory.createProperty(PROJECTA + "ruleVersion"), "1");
        derived.addLiteral(ResourceFactory.createProperty(PROJECTA + "sourceRevision"), plan.assertedGraphRevision());
        if (label != null && !label.isBlank()) {
            derived.addLiteral(RDFS.label, label);
        }
        derived.addLiteral(RDFS.comment, "inference-state.v1|state=current|ruleVersion=" + plan.ruleVersion());
    }

    private void validateShapes(Model data) {
        if (releasedShapes.isEmpty()) {
            return;
        }
        var report = org.apache.jena.shacl.ShaclValidator.get().validate(releasedShapes.getGraph(), data.getGraph());
        if (!report.conforms()) {
            throw new IllegalStateException("inference projection violates released SHACL shapes");
        }
    }

    private void rejectForeignAssertions(Model asserted, ProjectId project) {
        var belongs = ResourceFactory.createProperty(PROJECTA + "belongsToProject");
        var expected = ResourceFactory.createResource(BASE + project.value());
        var resources = asserted.listSubjectsWithProperty(belongs);
        while (resources.hasNext()) {
            var resource = resources.next();
            if (!asserted.contains(resource, belongs, expected)) {
                throw new IllegalArgumentException("asserted graph contains a cross-project resource");
            }
        }
    }

    private void preserveHistoricalSnapshot(Model inferred, ProjectId project, Snapshot current) {
        if ("none".equals(current.revision())) {
            return;
        }
        var historical = inferred.getResource(BASE + project.value() + "/inferred/revision/"
                + current.revision().substring(7) + "/snapshot");
        inferred.removeAll(historical, null, null);
        var live = inferred.getResource(snapshotIri(project));
        historical.addProperty(RDF.type, ResourceFactory.createResource(PROJECTA + "InferenceSnapshot"));
        var properties = live.listProperties();
        while (properties.hasNext()) {
            var statement = properties.next();
            historical.addProperty(statement.getPredicate(), statement.getObject());
        }
        historical.addLiteral(RDFS.comment, STATE_PREFIX + "state=historical|revision=" + current.revision());
    }

    private void markHistoricalFacts(Model inferred, String revision) {
        if ("none".equals(revision)) {
            return;
        }
        var sourceRevision = ResourceFactory.createProperty(PROJECTA + "sourceRevision");
        var resources =
                inferred.listSubjectsWithProperty(sourceRevision, revision).toList();
        for (var resource : resources) {
            resource.addLiteral(RDFS.comment, STATE_PREFIX + "state=historical|revision=" + revision);
        }
    }

    private Snapshot currentSnapshot(Model inferred, ProjectId project) {
        var snapshot = inferred.getResource(snapshotIri(project));
        if (!inferred.containsResource(snapshot)) {
            return new Snapshot("none", false);
        }
        var comment = inferred.listStatements(snapshot, RDFS.comment, (RDFNode) null).toList().stream()
                .map(Statement::getObject)
                .filter(RDFNode::isLiteral)
                .map(node -> node.asLiteral().getString())
                .filter(value -> value.startsWith(STATE_PREFIX))
                .findFirst()
                .orElse("");
        var fields = fields(comment);
        return new Snapshot(fields.getOrDefault("revision", "none"), "stale".equals(fields.get("state")));
    }

    private static String labelValue(Model model, Resource resource) {
        var label = model.getProperty(resource, RDFS.label);
        return label == null || !label.getObject().isLiteral() ? "" : label.getString();
    }

    private static Map<String, String> fields(String value) {
        var fields = new HashMap<String, String>();
        if (!value.startsWith(STATE_PREFIX)) {
            return fields;
        }
        for (var part : value.substring(STATE_PREFIX.length()).split("\\|")) {
            var pair = part.split("=", 2);
            if (pair.length == 2) {
                fields.put(pair[0], pair[1]);
            }
        }
        return fields;
    }

    private InferenceRebuildResult readIdempotency(
            Model provenance, String iri, String bodyDigest, String project, String kind) {
        var record = provenance.getResource(iri);
        if (!provenance.containsResource(record)) {
            return null;
        }
        var body = provenance.getProperty(record, RDF.value);
        var revision = provenance.getProperty(record, RDFS.comment);
        if (body == null
                || revision == null
                || !body.getObject().isLiteral()
                || !revision.getObject().isLiteral()) {
            throw new IllegalStateException(kind + " idempotency record is incomplete");
        }
        if (!body.getString().equals(bodyDigest)) {
            throw new IllegalStateException("idempotency key is already bound to a different request");
        }
        return new InferenceRebuildResult(
                "replayed",
                kind.equals("rebuild") ? CONTRACT_VERSION : "inference-invalidation.v1",
                project,
                revision.getString(),
                null,
                null,
                null,
                null);
    }

    private static void writeIdempotency(Model provenance, String iri, String bodyDigest, String revision) {
        var record = provenance.createResource(iri);
        record.addLiteral(RDFS.label, "inference-idempotency");
        record.addLiteral(RDF.value, bodyDigest);
        record.addLiteral(RDFS.comment, revision);
    }

    private String graph(ProjectId project, GraphRole role) {
        return router.route(project, role).toString();
    }

    private static String snapshotIri(ProjectId project) {
        return BASE + project.value() + SNAPSHOT_SUFFIX;
    }

    private static String stagingSnapshotIri(ProjectId project, String bodyDigest) {
        return BASE + project.value() + "/inferred/staging/" + bodyDigest.substring(7) + "/snapshot";
    }

    private static String rebuildIdempotencyIri(ProjectId project, String key) {
        return BASE + project.value() + "/inferred/rebuild-idempotency/"
                + ApprovedAssertionPlan.digest(key).substring(7);
    }

    private static String invalidationIdempotencyIri(ProjectId project, String key) {
        return BASE + project.value() + "/inferred/invalidation-idempotency/"
                + ApprovedAssertionPlan.digest(key).substring(7);
    }

    private record Snapshot(String revision, boolean stale) {}
}
