package org.projecta.semanticcore;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.apache.jena.query.DatasetFactory;
import org.apache.jena.rdf.model.ResourceFactory;
import org.junit.jupiter.api.Test;

class CandidateRejectionServiceTest {
    private static final String PROJECTA = "https://w3id.org/projecta/ontology/";
    private static final String CANDIDATE = "https://w3id.org/projecta/data/project/ecommerce-checkout/candidate/c1";
    private static final String REVIEWER = "https://w3id.org/projecta/data/project/ecommerce-checkout/person/le";

    @Test
    void rejectsCandidateWithProvenanceAndNoAssertedWrite() {
        var dataset = DatasetFactory.createTxnMem();
        var router = new GraphIriRouter();
        var project = new ProjectId("ecommerce-checkout");
        seedCandidate(dataset, router, project);
        var service = new CandidateRejectionService(dataset, router);

        var result = service.reject(project, CANDIDATE, REVIEWER, "reject-c1-01", "Source is insufficient.");

        assertFalse(result.replayed());
        var candidates = dataset.getNamedModel(
                router.route(project, GraphRole.CANDIDATES).toString());
        assertTrue(candidates.contains(
                ResourceFactory.createResource(CANDIDATE),
                ResourceFactory.createProperty(PROJECTA + "candidateStatus"),
                ResourceFactory.createResource(PROJECTA + "rejected")));
        assertEquals(
                "Source is insufficient.",
                candidates
                        .getResource(CANDIDATE)
                        .getProperty(ResourceFactory.createProperty(PROJECTA + "rejectionReason"))
                        .getString());
        assertEquals(
                0,
                dataset.getNamedModel(router.route(project, GraphRole.ASSERTED).toString())
                        .size());
        assertEquals(
                6,
                dataset.getNamedModel(
                                router.route(project, GraphRole.PROVENANCE).toString())
                        .size());
    }

    @Test
    void replaysSameIdempotencyKeyWithoutASecondActivity() {
        var dataset = DatasetFactory.createTxnMem();
        var router = new GraphIriRouter();
        var project = new ProjectId("ecommerce-checkout");
        seedCandidate(dataset, router, project);
        var service = new CandidateRejectionService(dataset, router);

        var first = service.reject(project, CANDIDATE, REVIEWER, "reject-c1-01", "Source is insufficient.");
        var replay = service.reject(project, CANDIDATE, REVIEWER, "reject-c1-01", "Source is insufficient.");

        assertTrue(replay.replayed());
        assertEquals(first.activityIri(), replay.activityIri());
        assertEquals(
                6,
                dataset.getNamedModel(
                                router.route(project, GraphRole.PROVENANCE).toString())
                        .size());
        assertThrows(
                IllegalArgumentException.class,
                () -> service.reject(project, CANDIDATE, REVIEWER, "reject-c1-01", "Different reason."));
        assertThrows(
                IllegalArgumentException.class,
                () -> service.reject(
                        project,
                        "https://w3id.org/projecta/data/project/ecommerce-checkout/candidate/c2",
                        REVIEWER,
                        "reject-c1-01",
                        "Source is insufficient."));
    }

    @Test
    void doesNotMutateGraphsWhenCandidateIsOutsideTrustedProject() {
        var dataset = DatasetFactory.createTxnMem();
        var router = new GraphIriRouter();
        var project = new ProjectId("ecommerce-checkout");
        var service = new CandidateRejectionService(dataset, router);

        assertThrows(
                IllegalArgumentException.class,
                () -> service.reject(project, CANDIDATE, REVIEWER, "reject-c1-01", "Source is insufficient."));

        assertEquals(
                0,
                dataset.getNamedModel(
                                router.route(project, GraphRole.CANDIDATES).toString())
                        .size());
        assertEquals(
                0,
                dataset.getNamedModel(
                                router.route(project, GraphRole.PROVENANCE).toString())
                        .size());
        assertEquals(
                0,
                dataset.getNamedModel(router.route(project, GraphRole.ASSERTED).toString())
                        .size());
    }

    private static void seedCandidate(org.apache.jena.query.Dataset dataset, GraphIriRouter router, ProjectId project) {
        dataset.getNamedModel(router.route(project, GraphRole.CANDIDATES).toString())
                .add(
                        ResourceFactory.createResource(CANDIDATE),
                        ResourceFactory.createProperty(PROJECTA + "candidateStatus"),
                        ResourceFactory.createResource(PROJECTA + "pending-review"));
    }
}
