package org.projecta.semanticcore;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.nio.file.Path;
import java.time.LocalDate;
import org.apache.jena.rdf.model.ModelFactory;
import org.apache.jena.rdf.model.ResourceFactory;
import org.apache.jena.tdb2.TDB2Factory;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class Tdb2LifecycleIntegrationTest {
    private static final String PROJECTA = "https://w3id.org/projecta/ontology/";
    private static final String CANDIDATE = "https://w3id.org/projecta/data/project/ecommerce-checkout/candidate/c1";
    private static final String REVIEWER = "https://w3id.org/projecta/data/project/ecommerce-checkout/person/le";

    @Test
    void persistsOneRejectionAndItsIdempotentReplayAcrossTdb2Reopen(@TempDir Path storage) {
        var router = new GraphIriRouter();
        var project = new ProjectId("ecommerce-checkout");
        var dataset = TDB2Factory.connectDataset(storage.toString());
        seed(dataset, router, project);
        var service = new CandidateRejectionService(dataset, router);
        service.reject(project, CANDIDATE, REVIEWER, "reject-c1", "Source is insufficient.");
        assertEquals(0, graphSize(dataset, router, project, GraphRole.ASSERTED));
        dataset.close();

        var reopened = TDB2Factory.connectDataset(storage.toString());
        reopened.begin(org.apache.jena.query.ReadWrite.READ);
        try {
            var candidates = reopened.getNamedModel(
                    router.route(project, GraphRole.CANDIDATES).toString());
            assertEquals(
                    PROJECTA + "rejected",
                    candidates
                            .getProperty(
                                    candidates.getResource(CANDIDATE),
                                    ResourceFactory.createProperty(PROJECTA + "candidateStatus"))
                            .getResource()
                            .getURI());
            assertEquals(
                    6,
                    reopened.getNamedModel(
                                    router.route(project, GraphRole.PROVENANCE).toString())
                            .size());
        } finally {
            reopened.end();
        }
        reopened.close();
    }

    @Test
    void rejectsAConflictingDecisionAndKeepsNamedGraphsIsolated(@TempDir Path storage) {
        var router = new GraphIriRouter();
        var project = new ProjectId("ecommerce-checkout");
        var dataset = TDB2Factory.connectDataset(storage.toString());
        seed(dataset, router, project);
        new CandidateConfirmationService(
                        dataset,
                        router,
                        new CandidateValidationService(dataset, router, ModelFactory.createDefaultModel()))
                .confirm(
                        project,
                        CANDIDATE,
                        "https://w3id.org/projecta/data/project/ecommerce-checkout/requirement/r1",
                        REVIEWER,
                        "Address confirmation",
                        LocalDate.of(2026, 7, 29));

        assertThrows(IllegalStateException.class, () -> new CandidateRejectionService(dataset, router)
                .reject(project, CANDIDATE, REVIEWER, "reject-c1", "Too late."));
        assertEquals(0, graphSize(dataset, router, project, GraphRole.INFERRED));
        assertEquals(1, subjectCount(dataset, router, project, GraphRole.ASSERTED));
        dataset.close();
    }

    private static void seed(org.apache.jena.query.Dataset dataset, GraphIriRouter router, ProjectId project) {
        dataset.begin(org.apache.jena.query.ReadWrite.WRITE);
        try {
            dataset.getNamedModel(router.route(project, GraphRole.CANDIDATES).toString())
                    .add(
                            ResourceFactory.createResource(CANDIDATE),
                            ResourceFactory.createProperty(PROJECTA + "candidateStatus"),
                            ResourceFactory.createResource(PROJECTA + "pending-review"));
            dataset.commit();
        } finally {
            dataset.end();
        }
    }

    private static long graphSize(
            org.apache.jena.query.Dataset dataset, GraphIriRouter router, ProjectId project, GraphRole role) {
        dataset.begin(org.apache.jena.query.ReadWrite.READ);
        try {
            return dataset.getNamedModel(router.route(project, role).toString()).size();
        } finally {
            dataset.end();
        }
    }

    private static long subjectCount(
            org.apache.jena.query.Dataset dataset, GraphIriRouter router, ProjectId project, GraphRole role) {
        dataset.begin(org.apache.jena.query.ReadWrite.READ);
        try {
            return dataset.getNamedModel(router.route(project, role).toString())
                    .listSubjects()
                    .toList()
                    .size();
        } finally {
            dataset.end();
        }
    }
}
