package org.projecta.semanticcore;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.time.LocalDate;
import org.apache.jena.query.Dataset;
import org.apache.jena.query.DatasetFactory;
import org.apache.jena.rdf.model.ModelFactory;
import org.apache.jena.rdf.model.ResourceFactory;
import org.apache.jena.vocabulary.RDF;
import org.apache.jena.vocabulary.RDFS;
import org.junit.jupiter.api.Test;

class ApprovedAssertionMaterializationServiceTest {
    private static final String PROJECT = "ecommerce-checkout";
    private static final String SOURCE = "sv_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";
    private static final String DIGEST = "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";
    private static final String CANDIDATE = "https://w3id.org/projecta/data/project/ecommerce-checkout/candidate/c1";
    private static final String ASSERTED = "https://w3id.org/projecta/data/project/ecommerce-checkout/requirement/r1";
    private static final String REVIEWER = "https://w3id.org/projecta/data/project/ecommerce-checkout/person/reviewer";

    @Test
    void disabledByDefaultAndApprovedPlanCommitsAllGraphs() {
        var dataset = DatasetFactory.createTxnMem();
        var router = new GraphIriRouter();
        var plan = seed(dataset, router, "key-1", "Address confirmation");
        var disabled = service(dataset, router, MaterializationAuthorization.disabled(), () -> {});

        assertThrows(IllegalStateException.class, () -> disabled.materialize(plan));
        assertEquals(
                0,
                dataset.getNamedModel(router.route(new ProjectId(PROJECT), GraphRole.ASSERTED)
                                .toString())
                        .size());

        var result = service(dataset, router, MaterializationAuthorization.enabledForTest(), () -> {})
                .materialize(plan);
        assertEquals("accepted", result.outcome());
        assertTrue(result.materializationRevision().startsWith("sha256:"));
        assertTrue(dataset.getNamedModel(router.route(new ProjectId(PROJECT), GraphRole.ASSERTED)
                                .toString())
                        .size()
                > 0);
        assertEquals(
                "asserted",
                dataset.getNamedModel(router.route(new ProjectId(PROJECT), GraphRole.CANDIDATES)
                                .toString())
                        .getResource(CANDIDATE)
                        .getProperty(
                                ResourceFactory.createProperty("https://w3id.org/projecta/ontology/candidateStatus"))
                        .getResource()
                        .getLocalName());
        assertTrue(dataset.getNamedModel(router.route(new ProjectId(PROJECT), GraphRole.PROVENANCE)
                                .toString())
                        .size()
                >= 5);
    }

    @Test
    void exactReplayIsIdempotentAndDifferentBodyCannotMutate() {
        var dataset = DatasetFactory.createTxnMem();
        var router = new GraphIriRouter();
        var plan = seed(dataset, router, "key-replay", "Address confirmation");
        var materializer = service(dataset, router, MaterializationAuthorization.enabledForTest(), () -> {});
        var accepted = materializer.materialize(plan);
        var assertedSize = dataset.getNamedModel(
                        router.route(new ProjectId(PROJECT), GraphRole.ASSERTED).toString())
                .size();
        var replay = materializer.materialize(plan);
        assertEquals("replayed", replay.outcome());
        assertEquals(accepted.materializationRevision(), replay.materializationRevision());
        assertEquals(
                assertedSize,
                dataset.getNamedModel(router.route(new ProjectId(PROJECT), GraphRole.ASSERTED)
                                .toString())
                        .size());

        var conflict = seedPlan("key-replay", "Changed label");
        assertThrows(IllegalStateException.class, () -> materializer.materialize(conflict));
        assertEquals(
                assertedSize,
                dataset.getNamedModel(router.route(new ProjectId(PROJECT), GraphRole.ASSERTED)
                                .toString())
                        .size());
    }

    @Test
    void rollbackLeavesCandidateAndAllGraphsUnchanged() {
        var dataset = DatasetFactory.createTxnMem();
        var router = new GraphIriRouter();
        var plan = seed(dataset, router, "key-rollback", "Address confirmation");
        var materializer = service(dataset, router, MaterializationAuthorization.enabledForTest(), () -> {
            throw new IllegalStateException("test failure after all writes");
        });

        assertThrows(IllegalStateException.class, () -> materializer.materialize(plan));
        assertEquals(
                0,
                dataset.getNamedModel(router.route(new ProjectId(PROJECT), GraphRole.ASSERTED)
                                .toString())
                        .size());
        assertEquals(
                0,
                dataset.getNamedModel(router.route(new ProjectId(PROJECT), GraphRole.PROVENANCE)
                                .toString())
                        .size());
        assertEquals(
                "confirmed",
                dataset.getNamedModel(router.route(new ProjectId(PROJECT), GraphRole.CANDIDATES)
                                .toString())
                        .getResource(CANDIDATE)
                        .getProperty(
                                ResourceFactory.createProperty("https://w3id.org/projecta/ontology/candidateStatus"))
                        .getResource()
                        .getLocalName());
    }

    @Test
    void staleGraphAndUnapprovedCandidateFailBeforeMutation() {
        var dataset = DatasetFactory.createTxnMem();
        var router = new GraphIriRouter();
        var plan = seed(dataset, router, "key-stale", "Address confirmation");
        var asserted = dataset.getNamedModel(
                router.route(new ProjectId(PROJECT), GraphRole.ASSERTED).toString());
        asserted.add(ResourceFactory.createResource(ASSERTED + "/existing"), RDFS.label, "existing");
        var materializer = service(dataset, router, MaterializationAuthorization.enabledForTest(), () -> {});
        assertThrows(IllegalStateException.class, () -> materializer.materialize(plan));
        assertEquals(1, asserted.size());

        var rejectedDataset = DatasetFactory.createTxnMem();
        var rejectedRouter = new GraphIriRouter();
        var rejectedPlan = seed(rejectedDataset, rejectedRouter, "key-rejected", "Address confirmation");
        var rejected = rejectedDataset.getNamedModel(rejectedRouter
                .route(new ProjectId(PROJECT), GraphRole.CANDIDATES)
                .toString());
        var status = ResourceFactory.createProperty("https://w3id.org/projecta/ontology/candidateStatus");
        rejected.removeAll(rejected.getResource(CANDIDATE), status, null);
        rejected.getResource(CANDIDATE)
                .addProperty(status, ResourceFactory.createResource("https://w3id.org/projecta/ontology/rejected"));
        assertThrows(
                IllegalStateException.class,
                () -> service(rejectedDataset, rejectedRouter, MaterializationAuthorization.enabledForTest(), () -> {})
                        .materialize(rejectedPlan));
        assertEquals(
                0,
                rejectedDataset
                        .getNamedModel(rejectedRouter
                                .route(new ProjectId(PROJECT), GraphRole.ASSERTED)
                                .toString())
                        .size());
    }

    private static ApprovedAssertionMaterializationService service(
            Dataset dataset, GraphIriRouter router, MaterializationAuthorization authorization, Runnable hook) {
        var shapes = ModelFactory.createDefaultModel();
        return new ApprovedAssertionMaterializationService(
                dataset, router, new CandidateValidationService(dataset, router, shapes), shapes, authorization, hook);
    }

    private static ApprovedAssertionPlan seed(Dataset dataset, GraphIriRouter router, String key, String label) {
        var plan = seedPlan(key, label);
        var candidates = dataset.getNamedModel(
                router.route(new ProjectId(PROJECT), GraphRole.CANDIDATES).toString());
        var candidate = candidates.createResource(CANDIDATE);
        var project = ResourceFactory.createResource("https://w3id.org/projecta/data/project/" + PROJECT);
        candidate.addProperty(RDF.type, ResourceFactory.createResource("https://w3id.org/projecta/ontology/Candidate"));
        candidate.addProperty(
                ResourceFactory.createProperty("https://w3id.org/projecta/ontology/belongsToProject"), project);
        candidate.addProperty(
                ResourceFactory.createProperty("https://w3id.org/projecta/ontology/candidateStatus"),
                ResourceFactory.createResource("https://w3id.org/projecta/ontology/confirmed"));
        candidate.addLiteral(
                ResourceFactory.createProperty("https://w3id.org/projecta/ontology/proposedOntologyVersion"), "0.4.0");
        candidate.addProperty(
                RDFS.comment,
                ApprovedAssertionPlan.metadataComment(plan.candidates().getFirst()));
        return plan;
    }

    private static ApprovedAssertionPlan seedPlan(String key, String label) {
        var candidate = new ApprovedAssertionPlan.ApprovedCandidate(
                PROJECT,
                CANDIDATE,
                7,
                SOURCE,
                3,
                DIGEST,
                DIGEST,
                "0.4.0",
                "constrained-relation.v1",
                "relation-evidence.v1",
                ASSERTED,
                REVIEWER,
                label,
                LocalDate.of(2026, 8, 22));
        return new ApprovedAssertionPlan(
                PROJECT,
                SOURCE,
                3,
                java.util.List.of(candidate),
                "0.4.0",
                "constrained-relation.v1",
                "relation-evidence.v1",
                ApprovedAssertionMaterializationService.graphRevision(ModelFactory.createDefaultModel()),
                "https://w3id.org/projecta/data/project/ecommerce-checkout/activity/materialize/" + key,
                key);
    }
}
