package org.projecta.semanticcore;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.apache.jena.query.Dataset;
import org.apache.jena.query.DatasetFactory;
import org.apache.jena.rdf.model.Model;
import org.apache.jena.rdf.model.ModelFactory;
import org.apache.jena.rdf.model.ResourceFactory;
import org.apache.jena.vocabulary.RDF;
import org.apache.jena.vocabulary.RDFS;
import org.junit.jupiter.api.Test;

class InferenceInvalidationRebuildServiceTest {
    private static final String PROJECT = "ecommerce-checkout";
    private static final String SOURCE = "sv_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";
    private static final String DIGEST = "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";
    private static final String ASSERTED = "https://w3id.org/projecta/data/project/ecommerce-checkout/requirement/r1";

    @Test
    void disabledByDefaultAndSuccessfulRebuildPublishesOnlyAfterValidation() {
        var dataset = DatasetFactory.createTxnMem();
        var router = new GraphIriRouter();
        var plan = plan(dataset, router, "rebuild-1", "none");
        var disabled = service(dataset, router, InferenceRebuildAuthorization.disabled(), () -> {});
        assertThrows(IllegalStateException.class, () -> disabled.rebuild(plan));
        assertEquals(0, inferred(dataset, router).size());

        var result = service(dataset, router, InferenceRebuildAuthorization.enabledForTest(), () -> {})
                .rebuild(plan);
        assertEquals("accepted", result.outcome());
        assertTrue(result.materializationRevision().startsWith("sha256:"));
        var snapshot = inferred(dataset, router).getResource(snapshotIri());
        assertEquals("current", state(snapshot));
        assertEquals(
                plan.assertedGraphRevision(),
                snapshot.getProperty(
                                ResourceFactory.createProperty("https://w3id.org/projecta/ontology/sourceRevision"))
                        .getString());
        assertTrue(inferred(dataset, router)
                .listSubjectsWithProperty(
                        RDF.type,
                        ResourceFactory.createResource("https://w3id.org/projecta/ontology/InferenceSnapshot"))
                .hasNext());
        assertTrue(provenance(dataset, router).size() > 0);
    }

    @Test
    void invalidationMarksCurrentStaleAndPreservesHistoricalProjection() {
        var dataset = DatasetFactory.createTxnMem();
        var router = new GraphIriRouter();
        var service = service(dataset, router, InferenceRebuildAuthorization.enabledForTest(), () -> {});
        var accepted = service.rebuild(plan(dataset, router, "rebuild-2", "none"));
        var invalidated = service.invalidate(new InferenceInvalidation(
                PROJECT, InferenceInvalidation.Cause.CORRECTION, accepted.materializationRevision(), "invalidate-1"));
        assertEquals("invalidated", invalidated.outcome());
        assertEquals("stale", state(inferred(dataset, router).getResource(snapshotIri())));
        assertTrue(inferred(dataset, router)
                .containsResource(ResourceFactory.createResource(
                        "https://w3id.org/projecta/data/project/ecommerce-checkout/inferred/revision/"
                                + accepted.materializationRevision().substring(7) + "/snapshot")));
        var replay = service.invalidate(new InferenceInvalidation(
                PROJECT, InferenceInvalidation.Cause.CORRECTION, accepted.materializationRevision(), "invalidate-1"));
        assertEquals("replayed", replay.outcome());
    }

    @Test
    void replayIsIdempotentAndSameKeyConflictDoesNotMutate() {
        var dataset = DatasetFactory.createTxnMem();
        var router = new GraphIriRouter();
        var service = service(dataset, router, InferenceRebuildAuthorization.enabledForTest(), () -> {});
        var plan = plan(dataset, router, "rebuild-replay", "none");
        var accepted = service.rebuild(plan);
        var before = inferred(dataset, router).size();
        assertEquals("replayed", service.rebuild(plan).outcome());
        assertEquals(before, inferred(dataset, router).size());
        var conflict = new InferenceRebuildPlan(
                PROJECT,
                plan.assertedGraphRevision(),
                SOURCE,
                3,
                DIGEST,
                InferenceInvalidationRebuildService.ONTOLOGY_VERSION,
                "m4.v2",
                "none",
                "https://w3id.org/projecta/data/project/ecommerce-checkout/activity/rebuild/rebuild-replay",
                "rebuild-replay");
        assertThrows(IllegalStateException.class, () -> service.rebuild(conflict));
        assertEquals(before, inferred(dataset, router).size());
        assertTrue(accepted.materializationRevision().startsWith("sha256:"));
    }

    @Test
    void staleCrossProjectAndFailedShapeOrTransactionLeaveAssertedTruthUntouched() {
        var dataset = DatasetFactory.createTxnMem();
        var router = new GraphIriRouter();
        var service = service(dataset, router, InferenceRebuildAuthorization.enabledForTest(), () -> {});
        var accepted = service.rebuild(plan(dataset, router, "rebuild-stale", "none"));
        var asserted = asserted(dataset, router);
        var assertedSize = asserted.size();
        assertThrows(
                IllegalStateException.class, () -> service.rebuild(plan(dataset, router, "rebuild-stale-2", "none")));
        assertEquals(assertedSize, asserted.size());

        var foreign = asserted.createResource(ASSERTED + "/foreign");
        foreign.addProperty(
                ResourceFactory.createProperty("https://w3id.org/projecta/ontology/belongsToProject"),
                ResourceFactory.createResource("https://w3id.org/projecta/data/project/other"));
        assertThrows(
                IllegalArgumentException.class,
                () -> service.rebuild(plan(dataset, router, "rebuild-foreign", "none")));
        asserted.removeAll(foreign, null, null);

        var failing = service(dataset, router, InferenceRebuildAuthorization.enabledForTest(), () -> {
            throw new IllegalStateException("injected rebuild failure");
        });
        assertThrows(
                IllegalStateException.class,
                () -> failing.rebuild(plan(dataset, router, "rebuild-fail", accepted.materializationRevision())));
        assertEquals(assertedSize, asserted.size());
    }

    @Test
    void releasedShapeFailureOccursBeforeAnyInferenceWrite() {
        var shapes = ModelFactory.createDefaultModel();
        var shape = shapes.createResource("https://example.test/ForbiddenSnapshotShape");
        shape.addProperty(RDF.type, ResourceFactory.createResource("http://www.w3.org/ns/shacl#NodeShape"));
        shape.addProperty(
                ResourceFactory.createProperty("http://www.w3.org/ns/shacl#targetClass"),
                ResourceFactory.createResource("https://w3id.org/projecta/ontology/InferenceSnapshot"));
        var property = shapes.createResource();
        property.addProperty(
                ResourceFactory.createProperty("http://www.w3.org/ns/shacl#path"),
                ResourceFactory.createProperty("https://example.test/required"));
        property.addLiteral(ResourceFactory.createProperty("http://www.w3.org/ns/shacl#minCount"), 1);
        shape.addProperty(ResourceFactory.createProperty("http://www.w3.org/ns/shacl#property"), property);
        var dataset = DatasetFactory.createTxnMem();
        var router = new GraphIriRouter();
        var service = new InferenceInvalidationRebuildService(
                dataset, router, shapes, InferenceRebuildAuthorization.enabledForTest(), () -> {});
        assertThrows(
                IllegalStateException.class, () -> service.rebuild(plan(dataset, router, "rebuild-shape", "none")));
        assertEquals(0, inferred(dataset, router).size());
        assertEquals(0, asserted(dataset, router).size());
    }

    private static InferenceInvalidationRebuildService service(
            Dataset dataset, GraphIriRouter router, InferenceRebuildAuthorization authorization, Runnable hook) {
        return new InferenceInvalidationRebuildService(
                dataset, router, ModelFactory.createDefaultModel(), authorization, hook);
    }

    private static InferenceRebuildPlan plan(Dataset dataset, GraphIriRouter router, String key, String expected) {
        var asserted = asserted(dataset, router);
        return new InferenceRebuildPlan(
                PROJECT,
                ApprovedAssertionMaterializationService.graphRevision(asserted),
                SOURCE,
                3,
                DIGEST,
                InferenceInvalidationRebuildService.ONTOLOGY_VERSION,
                InferenceInvalidationRebuildService.RULE_VERSION,
                expected,
                "https://w3id.org/projecta/data/project/ecommerce-checkout/activity/rebuild/" + key,
                key);
    }

    private static Model asserted(Dataset dataset, GraphIriRouter router) {
        return dataset.getNamedModel(
                router.route(new ProjectId(PROJECT), GraphRole.ASSERTED).toString());
    }

    private static Model inferred(Dataset dataset, GraphIriRouter router) {
        return dataset.getNamedModel(
                router.route(new ProjectId(PROJECT), GraphRole.INFERRED).toString());
    }

    private static Model provenance(Dataset dataset, GraphIriRouter router) {
        return dataset.getNamedModel(
                router.route(new ProjectId(PROJECT), GraphRole.PROVENANCE).toString());
    }

    private static String snapshotIri() {
        return "https://w3id.org/projecta/data/project/ecommerce-checkout/inferred/snapshot-m4-v1";
    }

    private static String state(org.apache.jena.rdf.model.Resource snapshot) {
        var comment = snapshot.getProperty(RDFS.comment);
        return comment == null ? "" : comment.getString().split("\\|")[1].split("=")[1];
    }
}
