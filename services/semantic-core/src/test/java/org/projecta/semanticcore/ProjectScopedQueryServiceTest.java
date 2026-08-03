package org.projecta.semanticcore;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.util.Optional;
import org.apache.jena.query.DatasetFactory;
import org.apache.jena.rdf.model.ResourceFactory;
import org.apache.jena.vocabulary.RDF;
import org.apache.jena.vocabulary.RDFS;
import org.junit.jupiter.api.Test;

class ProjectScopedQueryServiceTest {
    private static final String DATA = "https://w3id.org/projecta/data/project/ecommerce-checkout/";
    private static final String PROJECTA = "https://w3id.org/projecta/ontology/";
    private static final String PROV = "http://www.w3.org/ns/prov#";

    @Test
    void returnsOnlyCurrentKnowledgeFromTheTrustedProject() {
        var fixture = fixture();

        var items = fixture.service().currentKnowledgeItems(fixture.project(), Optional.of("Requirement"));

        assertEquals(1, items.size());
        assertEquals("address-confirmation", items.getFirst().id());
        assertThrows(
                IllegalArgumentException.class,
                () -> fixture.service().currentKnowledgeItems(fixture.project(), Optional.of("Candidate")));
    }

    @Test
    void returnsHistoryAndEvidenceOnlyWhenTheWholeChainIsInProjectGraphs() {
        var fixture = fixture();

        var history = fixture.service().candidateHistory(fixture.project(), "address-confirmation");
        var evidence = fixture.service().evidence(fixture.project(), "address-confirmation");

        assertEquals("asserted", history.currentStatus());
        assertEquals(1, history.activities().size());
        assertEquals("confirmed", history.activities().getFirst().decision());
        assertEquals("address-confirmation", evidence.candidateId());
        assertEquals("ni-1", evidence.sourceId());
        assertEquals("le", evidence.reviewerId());
    }

    @Test
    void doesNotResolveAnIdenticalIdFromAnotherProjectGraph() {
        var fixture = fixture();
        var otherProject = new ProjectId("other-project");
        fixture.dataset()
                .getNamedModel(
                        fixture.router().route(otherProject, GraphRole.ASSERTED).toString())
                .add(
                        ResourceFactory.createResource(
                                "https://w3id.org/projecta/data/project/other-project/requirement/address-confirmation"),
                        RDF.type,
                        ResourceFactory.createResource(PROJECTA + "KnowledgeItem"));

        assertThrows(
                ProjectScopedQueryService.ResourceNotFoundException.class,
                () -> fixture.service().evidence(fixture.project(), "missing-item"));
    }

    private static Fixture fixture() {
        var dataset = DatasetFactory.createTxnMem();
        var router = new GraphIriRouter();
        var project = new ProjectId("ecommerce-checkout");
        var item = ResourceFactory.createResource(DATA + "requirement/address-confirmation");
        var candidate = ResourceFactory.createResource(DATA + "candidate/address-confirmation");
        var source = ResourceFactory.createResource(DATA + "note-item/ni-1");
        var reviewer = ResourceFactory.createResource(DATA + "person/le");
        var asserted =
                dataset.getNamedModel(router.route(project, GraphRole.ASSERTED).toString());
        asserted.add(item, RDF.type, ResourceFactory.createResource(PROJECTA + "KnowledgeItem"));
        asserted.add(item, RDF.type, ResourceFactory.createResource(PROJECTA + "Requirement"));
        asserted.add(item, RDFS.label, "Address confirmation");
        asserted.add(
                item, ResourceFactory.createProperty(PROJECTA + "validFrom"), asserted.createLiteral("2026-07-29"));
        asserted.add(item, ResourceFactory.createProperty(PROV + "wasDerivedFrom"), candidate);
        asserted.add(item, ResourceFactory.createProperty(PROV + "wasAttributedTo"), reviewer);
        var candidates = dataset.getNamedModel(
                router.route(project, GraphRole.CANDIDATES).toString());
        candidates.add(
                candidate,
                ResourceFactory.createProperty(PROJECTA + "candidateStatus"),
                ResourceFactory.createResource(PROJECTA + "asserted"));
        candidates.add(candidate, ResourceFactory.createProperty(PROV + "wasDerivedFrom"), source);
        dataset.getNamedModel(router.route(project, GraphRole.SOURCES).toString())
                .add(source, RDF.type, ResourceFactory.createResource(PROJECTA + "NoteItem"));
        var activity = ResourceFactory.createResource(DATA + "activity/review-1");
        var provenance = dataset.getNamedModel(
                router.route(project, GraphRole.PROVENANCE).toString());
        provenance.add(activity, RDF.type, ResourceFactory.createResource(PROV + "Activity"));
        provenance.add(activity, ResourceFactory.createProperty(PROV + "used"), candidate);
        provenance.add(
                activity,
                ResourceFactory.createProperty(PROJECTA + "reviewDecision"),
                ResourceFactory.createResource(PROJECTA + "confirmed"));
        provenance.add(activity, ResourceFactory.createProperty(PROV + "wasAssociatedWith"), reviewer);
        provenance.add(
                activity,
                ResourceFactory.createProperty(PROV + "endedAtTime"),
                provenance.createLiteral("2026-07-29T10:15:00Z"));
        return new Fixture(dataset, router, project, new ProjectScopedQueryService(dataset, router));
    }

    private record Fixture(
            org.apache.jena.query.Dataset dataset,
            GraphIriRouter router,
            ProjectId project,
            ProjectScopedQueryService service) {}
}
