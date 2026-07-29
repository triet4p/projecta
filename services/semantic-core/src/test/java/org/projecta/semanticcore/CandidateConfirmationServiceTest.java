package org.projecta.semanticcore;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.time.LocalDate;
import org.apache.jena.query.DatasetFactory;
import org.apache.jena.rdf.model.ModelFactory;
import org.apache.jena.rdf.model.ResourceFactory;
import org.junit.jupiter.api.Test;

class CandidateConfirmationServiceTest {
    @Test
    void confirmsCandidateWithAssertedAndProvenanceWrites() {
        var dataset = DatasetFactory.createTxnMem();
        var router = new GraphIriRouter();
        var project = new ProjectId("ecommerce-checkout");
        var candidate = "https://w3id.org/projecta/data/project/ecommerce-checkout/candidate/c1";
        dataset.getNamedModel(router.route(project, GraphRole.CANDIDATES).toString())
                .add(
                        ResourceFactory.createResource(candidate),
                        ResourceFactory.createProperty("https://w3id.org/projecta/ontology/candidateStatus"),
                        ResourceFactory.createResource("https://w3id.org/projecta/ontology/validated"));

        var assertedIri = confirmationService(dataset, router)
                .confirm(
                        project,
                        candidate,
                        "https://w3id.org/projecta/data/project/ecommerce-checkout/requirement/r1",
                        "https://w3id.org/projecta/data/project/ecommerce-checkout/person/le",
                        "Address confirmation",
                        LocalDate.of(2026, 7, 29));

        assertEquals(
                1,
                dataset.getNamedModel(router.route(project, GraphRole.ASSERTED).toString())
                        .listSubjects()
                        .toList()
                        .size());
        assertEquals(
                assertedIri,
                dataset.getNamedModel(router.route(project, GraphRole.ASSERTED).toString())
                        .listSubjects()
                        .next()
                        .getURI());
        assertEquals(
                2,
                dataset.getNamedModel(
                                router.route(project, GraphRole.PROVENANCE).toString())
                        .listSubjects()
                        .toList()
                        .size());
    }

    @Test
    void rollsBackAllWritesWhenPromotionFails() {
        var dataset = DatasetFactory.createTxnMem();
        var router = new GraphIriRouter();
        var project = new ProjectId("ecommerce-checkout");
        var candidate = "https://w3id.org/projecta/data/project/ecommerce-checkout/candidate/c1";
        dataset.getNamedModel(router.route(project, GraphRole.CANDIDATES).toString())
                .add(
                        ResourceFactory.createResource(candidate),
                        ResourceFactory.createProperty("https://w3id.org/projecta/ontology/candidateStatus"),
                        ResourceFactory.createResource("https://w3id.org/projecta/ontology/validated"));

        assertThrows(IllegalArgumentException.class, () -> confirmationService(dataset, router)
                .confirm(
                        project,
                        candidate,
                        "https://w3id.org/projecta/data/project/ecommerce-checkout/requirement/r1",
                        "https://w3id.org/projecta/data/project/ecommerce-checkout/person/le",
                        "Address confirmation",
                        null));

        assertEquals(
                0,
                dataset.getNamedModel(router.route(project, GraphRole.ASSERTED).toString())
                        .size());
        assertEquals(
                0,
                dataset.getNamedModel(
                                router.route(project, GraphRole.PROVENANCE).toString())
                        .size());
    }

    private static CandidateConfirmationService confirmationService(
            org.apache.jena.query.Dataset dataset, GraphIriRouter router) {
        return new CandidateConfirmationService(
                dataset, router, new CandidateValidationService(dataset, router, ModelFactory.createDefaultModel()));
    }
}
