package org.projecta.semanticcore;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.time.LocalDate;
import java.util.List;
import org.apache.jena.query.Dataset;
import org.apache.jena.query.DatasetFactory;
import org.apache.jena.rdf.model.ModelFactory;
import org.apache.jena.rdf.model.ResourceFactory;
import org.apache.jena.vocabulary.RDFS;
import org.junit.jupiter.api.Test;

class ManualApprovedReviewBindingTest {
    private static final String PROJECT = "project-alpha";
    private static final String CANDIDATE =
            "https://w3id.org/projecta/data/project/project-alpha/candidate/note-1-1";
    private static final String BINDING =
            "projecta-approved-candidate/v1|candidateRevision=1|sourceVersionId=sv_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
                    + "|sourceVersionRevision=1|reviewReceiptDigest=sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
                    + "|evidenceDigest=sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
                    + "|constrainedRelationContractVersion=manual-entity-capture.v1|evidenceSelectionVersion=text-anchor.v1";

    @Test
    void appliesConfirmedTransitionToValidatedCandidateOnly() {
        var dataset = DatasetFactory.createTxnMem();
        var router = new GraphIriRouter();
        var project = new ProjectId(PROJECT);
        seedValidated(dataset, router);

        new ManualApprovedReviewBinding(dataset, router)
                .applyConfirmedBinding(project, CANDIDATE, BINDING, "0.3.0");

        var status = ResourceFactory.createProperty("https://w3id.org/projecta/ontology/candidateStatus");
        var candidates =
                dataset.getNamedModel(router.route(project, GraphRole.CANDIDATES).toString());
        assertEquals(
                "confirmed",
                candidates
                        .getResource(CANDIDATE)
                        .getProperty(status)
                        .getResource()
                        .getLocalName());
        assertTrue(candidates.contains(
                candidates.getResource(CANDIDATE),
                RDFS.comment,
                BINDING));
    }

    @Test
    void failsClosedOnUnvalidatedCrossProjectOrMissingRows() {
        var dataset = DatasetFactory.createTxnMem();
        var router = new GraphIriRouter();
        var project = new ProjectId(PROJECT);
        var binding = new ManualApprovedReviewBinding(dataset, router);

        assertThrows(
                IllegalStateException.class,
                () -> binding.applyConfirmedBinding(project, CANDIDATE, BINDING, "0.3.0"));
        assertEquals(
                0,
                dataset.getNamedModel(router.route(project, GraphRole.ASSERTED).toString())
                        .size());

        seedValidated(dataset, router);
        assertThrows(
                IllegalArgumentException.class,
                () -> binding.applyConfirmedBinding(
                        new ProjectId("project-beta"), CANDIDATE, BINDING, "0.3.0"));
        assertThrows(
                IllegalArgumentException.class,
                () -> binding.applyConfirmedBinding(project, CANDIDATE, "tampered", "0.3.0"));
        assertThrows(
                IllegalStateException.class,
                () -> binding.applyConfirmedBinding(project, CANDIDATE, BINDING, "0.2.0"));

        var candidates =
                dataset.getNamedModel(router.route(project, GraphRole.CANDIDATES).toString());
        assertEquals(
                "validated",
                candidates
                        .getResource(CANDIDATE)
                        .getProperty(ResourceFactory.createProperty(
                                "https://w3id.org/projecta/ontology/candidateStatus"))
                        .getResource()
                        .getLocalName());
    }

    private static void seedValidated(Dataset dataset, GraphIriRouter router) {
        var project = new ProjectId(PROJECT);
        var candidates =
                dataset.getNamedModel(router.route(project, GraphRole.CANDIDATES).toString());
        var candidate = candidates.createResource(CANDIDATE);
        candidate.addProperty(
                org.apache.jena.vocabulary.RDF.type,
                ResourceFactory.createResource("https://w3id.org/projecta/ontology/Candidate"));
        candidate.addProperty(
                ResourceFactory.createProperty("https://w3id.org/projecta/ontology/belongsToProject"),
                ResourceFactory.createResource("https://w3id.org/projecta/data/project/" + PROJECT));
        candidate.addProperty(
                ResourceFactory.createProperty("https://w3id.org/projecta/ontology/candidateStatus"),
                ResourceFactory.createResource("https://w3id.org/projecta/ontology/validated"));
        candidate.addLiteral(
                ResourceFactory.createProperty("https://w3id.org/projecta/ontology/proposedOntologyVersion"),
                "0.3.0");
        candidate.addProperty(
                ResourceFactory.createProperty("http://www.w3.org/ns/prov#wasDerivedFrom"),
                ResourceFactory.createResource("https://w3id.org/projecta/data/project/" + PROJECT + "/note-item/x-1"));
        candidate.addProperty(
                ResourceFactory.createProperty("http://www.w3.org/ns/prov#wasGeneratedBy"),
                ResourceFactory.createResource("https://w3id.org/projecta/data/project/" + PROJECT + "/activity/x-1"));
        candidate.addProperty(
                ResourceFactory.createProperty("https://w3id.org/projecta/ontology/generator"),
                "manual-quick-note-v0.3.0");
        candidate.addProperty(
                ResourceFactory.createProperty("http://www.w3.org/ns/prov#generatedAtTime"),
                candidates.createTypedLiteral(
                        "2026-09-27T00:00:00Z",
                        org.apache.jena.datatypes.xsd.XSDDatatype.XSDdateTime));
    }

    @Test
    void materializerStaysDisabledByDefault() {
        var dataset = DatasetFactory.createTxnMem();
        var router = new GraphIriRouter();
        var candidate = new ApprovedAssertionPlan.ApprovedCandidate(
                PROJECT,
                CANDIDATE,
                1,
                "sv_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                1,
                "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                "sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
                "0.3.0",
                "manual-entity-capture.v1",
                "text-anchor.v1",
                "https://w3id.org/projecta/data/project/project-alpha/requirement/req-manual-1",
                "https://w3id.org/projecta/data/project/project-alpha/person/reviewer-1",
                "Parity assertion label",
                LocalDate.of(2026, 9, 27));
        var plan = new ApprovedAssertionPlan(
                PROJECT,
                "sv_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                1,
                List.of(candidate),
                "0.3.0",
                "manual-entity-capture.v1",
                "text-anchor.v1",
                ApprovedAssertionMaterializationService.graphRevision(ModelFactory.createDefaultModel()),
                "https://w3id.org/projecta/data/project/project-alpha/activity/materialize/manual-1",
                "binding-key-1");
        seedValidated(dataset, router);
        new ManualApprovedReviewBinding(dataset, router)
                .applyConfirmedBinding(new ProjectId(PROJECT), CANDIDATE, BINDING, "0.3.0");
        var shapes = ModelFactory.createDefaultModel();
        var disabled = new ApprovedAssertionMaterializationService(
                dataset,
                router,
                new CandidateValidationService(dataset, router, shapes),
                shapes,
                MaterializationAuthorization.disabled(),
                () -> {});
        assertThrows(IllegalStateException.class, () -> disabled.materialize(plan));
        assertEquals(
                0,
                dataset.getNamedModel(router.route(new ProjectId(PROJECT), GraphRole.ASSERTED).toString())
                        .size());
    }
}
