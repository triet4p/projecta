package org.projecta.semanticcore;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;

import org.apache.jena.query.DatasetFactory;
import org.apache.jena.rdf.model.ModelFactory;
import org.apache.jena.riot.Lang;
import org.apache.jena.riot.RDFParser;
import org.junit.jupiter.api.Test;

class CandidateValidationServiceTest {
    private static final String PROJECT = "ecommerce-checkout";
    private static final String CANDIDATE = "https://w3id.org/projecta/data/project/ecommerce-checkout/candidate/c1";

    @Test
    void returnsStructuredViolationsWithoutMutatingOtherGraphs() {
        var dataset = DatasetFactory.createTxnMem();
        var router = new GraphIriRouter();
        var candidateGraph = dataset.getNamedModel(
                router.route(new ProjectId(PROJECT), GraphRole.CANDIDATES).toString());
        RDFParser.fromString("@prefix ex: <https://example.test/> . <" + CANDIDATE + "> a ex:Candidate .", Lang.TURTLE)
                .parse(candidateGraph);
        var shapes = ModelFactory.createDefaultModel();
        RDFParser.fromString("""
                @prefix ex: <https://example.test/> .
                @prefix sh: <http://www.w3.org/ns/shacl#> .
                ex:CandidateShape a sh:NodeShape ; sh:targetClass ex:Candidate ;
                  sh:property [ sh:path ex:label ; sh:minCount 1 ; sh:message "candidate label is required" ] .
                """, Lang.TURTLE).parse(shapes);

        var result = new CandidateValidationService(dataset, router, shapes).validate(new ProjectId(PROJECT));

        assertFalse(result.conforms());
        assertEquals(
                "candidate label is required", result.violations().getFirst().message());
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
    }
}
