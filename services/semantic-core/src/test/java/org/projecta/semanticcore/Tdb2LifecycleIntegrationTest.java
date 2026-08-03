package org.projecta.semanticcore;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.nio.file.Path;
import java.time.LocalDate;
import org.apache.jena.dboe.base.block.FileMode;
import org.apache.jena.dboe.base.file.Location;
import org.apache.jena.query.Dataset;
import org.apache.jena.query.DatasetFactory;
import org.apache.jena.rdf.model.ModelFactory;
import org.apache.jena.rdf.model.ResourceFactory;
import org.apache.jena.tdb2.DatabaseMgr;
import org.apache.jena.tdb2.params.StoreParamsBuilder;
import org.apache.jena.tdb2.sys.StoreConnection;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class Tdb2LifecycleIntegrationTest {
    private static final String PROJECTA = "https://w3id.org/projecta/ontology/";
    private static final String CANDIDATE = "https://w3id.org/projecta/data/project/ecommerce-checkout/candidate/c1";
    private static final String REVIEWER = "https://w3id.org/projecta/data/project/ecommerce-checkout/person/le";

    /** Opens an on-disk TDB2 dataset in direct mode so Windows releases the files on close. */
    private static Dataset openTdb2(Path storage) {
        var params = StoreParamsBuilder.create("projecta-test")
                .fileMode(FileMode.direct)
                .build();
        return DatasetFactory.wrap(DatabaseMgr.connectDatasetGraph(storage.toString(), params));
    }

    /** Closes the dataset and releases its TDB2 store connection so it can be reopened or deleted. */
    private static void closeTdb2(Dataset dataset, Path storage) {
        dataset.close();
        StoreConnection.release(Location.create(storage.toString()));
    }

    /** Releases every remaining TDB2 resource so Windows can delete the temp files. */
    private static void resetTdb2() {
        StoreConnection.internalReset();
    }

    @Test
    void persistsOneRejectionAndItsIdempotentReplayAcrossTdb2Reopen(@TempDir Path storage) {
        var router = new GraphIriRouter();
        var project = new ProjectId("ecommerce-checkout");
        var dataset = openTdb2(storage);
        seed(dataset, router, project);
        var service = new CandidateRejectionService(dataset, router);
        service.reject(project, CANDIDATE, REVIEWER, "reject-c1", "Source is insufficient.");
        assertEquals(0, graphSize(dataset, router, project, GraphRole.ASSERTED));
        closeTdb2(dataset, storage);

        var reopened = openTdb2(storage);
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
        closeTdb2(reopened, storage);
        resetTdb2();
    }

    @Test
    void rejectsAConflictingDecisionAndKeepsNamedGraphsIsolated(@TempDir Path storage) {
        var router = new GraphIriRouter();
        var project = new ProjectId("ecommerce-checkout");
        var dataset = openTdb2(storage);
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

        assertThrows(
                IllegalStateException.class,
                () -> new CandidateRejectionService(dataset, router)
                        .reject(project, CANDIDATE, REVIEWER, "reject-c1", "Too late."));
        assertEquals(0, graphSize(dataset, router, project, GraphRole.INFERRED));
        assertEquals(1, subjectCount(dataset, router, project, GraphRole.ASSERTED));
        closeTdb2(dataset, storage);
        resetTdb2();
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
