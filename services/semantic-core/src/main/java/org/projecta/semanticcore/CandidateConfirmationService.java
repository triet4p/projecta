package org.projecta.semanticcore;

import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.UUID;
import org.apache.jena.datatypes.xsd.XSDDatatype;
import org.apache.jena.query.Dataset;
import org.apache.jena.query.ReadWrite;
import org.apache.jena.rdf.model.ResourceFactory;
import org.apache.jena.vocabulary.RDF;
import org.apache.jena.vocabulary.RDFS;

/** Promotes a validated candidate atomically with review and reified provenance. */
public final class CandidateConfirmationService {
    private static final String PROJECTA = "https://w3id.org/projecta/ontology/";
    private static final String PROV = "http://www.w3.org/ns/prov#";
    private final Dataset dataset;
    private final GraphIriRouter router;
    private final CandidateValidationService validationService;

    public CandidateConfirmationService(
            Dataset dataset, GraphIriRouter router, CandidateValidationService validationService) {
        this.dataset = dataset;
        this.router = router;
        this.validationService = validationService;
    }

    public String confirm(
            ProjectId projectId,
            String candidateIri,
            String assertedIri,
            String reviewerIri,
            String label,
            LocalDate validFrom) {
        if (label == null || label.isBlank() || validFrom == null) {
            throw new IllegalArgumentException("assertion label and validFrom are required");
        }
        dataset.begin(ReadWrite.WRITE);
        try {
            var candidates = dataset.getNamedModel(
                    router.route(projectId, GraphRole.CANDIDATES).toString());
            var candidate = candidates.getResource(candidateIri);
            if (!candidates.containsResource(candidate)) {
                throw new IllegalArgumentException("candidate is not in the trusted project graph");
            }
            if (!validationService.validate(projectId).conforms()) {
                throw new IllegalArgumentException("candidate does not conform to released shapes");
            }
            var status = ResourceFactory.createProperty(PROJECTA + "candidateStatus");
            if (candidates.contains(candidate, status, ResourceFactory.createResource(PROJECTA + "rejected"))
                    || candidates.contains(candidate, status, ResourceFactory.createResource(PROJECTA + "asserted"))) {
                throw new IllegalStateException("candidate already has a terminal decision");
            }
            var asserted = dataset.getNamedModel(
                    router.route(projectId, GraphRole.ASSERTED).toString());
            var provenance = dataset.getNamedModel(
                    router.route(projectId, GraphRole.PROVENANCE).toString());
            var item = asserted.createResource(assertedIri);
            var project = ResourceFactory.createResource("https://w3id.org/projecta/data/project/" + projectId.value());
            item.addProperty(RDF.type, ResourceFactory.createResource(PROJECTA + "KnowledgeItem"));
            item.addProperty(RDF.type, ResourceFactory.createResource(PROJECTA + "Requirement"));
            item.addLiteral(RDFS.label, label);
            item.addProperty(ResourceFactory.createProperty(PROV + "wasDerivedFrom"), candidate);
            item.addProperty(
                    ResourceFactory.createProperty(PROV + "wasAttributedTo"),
                    ResourceFactory.createResource(reviewerIri));
            item.addProperty(ResourceFactory.createProperty(PROJECTA + "belongsToProject"), project);
            item.addProperty(
                    ResourceFactory.createProperty(PROJECTA + "validFrom"),
                    asserted.createTypedLiteral(validFrom.toString(), XSDDatatype.XSDdate));
            var activity = provenance.createResource(assertedIri + "/activity/confirm-" + UUID.randomUUID());
            activity.addProperty(RDF.type, ResourceFactory.createResource(PROV + "Activity"));
            activity.addProperty(ResourceFactory.createProperty(PROV + "used"), candidate);
            activity.addProperty(ResourceFactory.createProperty(PROV + "generated"), item);
            activity.addProperty(
                    ResourceFactory.createProperty(PROV + "wasAssociatedWith"),
                    ResourceFactory.createResource(reviewerIri));
            activity.addProperty(
                    ResourceFactory.createProperty(PROJECTA + "reviewDecision"),
                    ResourceFactory.createResource(PROJECTA + "confirmed"));
            activity.addProperty(
                    ResourceFactory.createProperty(PROV + "endedAtTime"),
                    provenance.createTypedLiteral(OffsetDateTime.now().toString(), XSDDatatype.XSDdateTime));
            var statement = provenance.createResource(assertedIri + "/statement/valid-from");
            statement.addProperty(RDF.type, RDF.Statement);
            statement.addProperty(RDF.subject, item);
            statement.addProperty(RDF.predicate, ResourceFactory.createProperty(PROJECTA + "validFrom"));
            statement.addProperty(RDF.object, provenance.createTypedLiteral(validFrom.toString(), XSDDatatype.XSDdate));
            candidates.removeAll(candidate, status, null);
            candidate.addProperty(status, ResourceFactory.createResource(PROJECTA + "asserted"));
            dataset.commit();
            return assertedIri;
        } catch (RuntimeException exception) {
            dataset.abort();
            throw exception;
        } finally {
            dataset.end();
        }
    }
}
