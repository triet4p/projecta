package org.projecta.semanticcore;

import org.apache.jena.query.Dataset;
import org.apache.jena.query.ReadWrite;
import org.apache.jena.rdf.model.ModelFactory;
import org.apache.jena.rdf.model.ResourceFactory;
import org.apache.jena.vocabulary.RDF;
import org.apache.jena.vocabulary.RDFS;

/**
 * Production domain logic for the human-approval lifecycle transition.
 *
 * <p>Marks a validated, same-project manual candidate {@code confirmed} and attaches the exact
 * {@code projecta-approved-candidate/v1} safe review binding derived from the persisted RM-61
 * confirm receipt, so the RM-63 {@code ApprovedAssertionMaterializationService} boundary can
 * recheck the binding transactionally. Fails closed on missing/unvalidated/cross-project/
 * ontology-mismatch rows and mutates nothing else.
 *
 * <p>Composition is deliberately unwired: production {@code SemanticCoreApplication} never
 * constructs this class. Only test-only composition may supply
 * {@code MaterializationAuthorization.enabledForTest()} (RM-63 authorizes test-only opt-in, never
 * production enablement); every other caller gets the disabled fail-closed default.
 */
public final class ApprovedCandidateBindingService {
    private static final String PROJECTA = "https://w3id.org/projecta/ontology/";
    private static final String BASE = "https://w3id.org/projecta/data/project/";

    private final Dataset dataset;
    private final GraphIriRouter router;
    private final MaterializationAuthorization authorization;

    public ApprovedCandidateBindingService(
            Dataset dataset, GraphIriRouter router, MaterializationAuthorization authorization) {
        if (dataset == null || router == null) {
            throw new IllegalArgumentException("dataset and graph router are required");
        }
        this.dataset = dataset;
        this.router = router;
        this.authorization =
                authorization == null ? MaterializationAuthorization.disabled() : authorization;
    }

    /**
     * Marks the captured candidate confirmed with the exact safe review binding.
     *
     * @param project project scope, rechecked against the candidate row
     * @param candidateIri full candidate IRI of the real captured row
     * @param bindingComment exact {@code projecta-approved-candidate/v1|...} comment
     * @param ontologyVersion released manual ontology version, rechecked against the row
     */
    public void applyConfirmedBinding(
            ProjectId project, String candidateIri, String bindingComment, String ontologyVersion) {
        authorization.requireEnabled();
        if (project == null || candidateIri == null || bindingComment == null || ontologyVersion == null) {
            throw new IllegalArgumentException("project, candidate, binding, and ontology version are required");
        }
        var expectedPrefix = BASE + project.value() + "/candidate/";
        if (!candidateIri.startsWith(expectedPrefix)) {
            throw new IllegalArgumentException("candidate is outside the project scope");
        }
        if (!bindingComment.startsWith("projecta-approved-candidate/v1|")) {
            throw new IllegalArgumentException("candidate review binding is incomplete");
        }
        dataset.begin(ReadWrite.WRITE);
        try {
            var candidates =
                    dataset.getNamedModel(router.route(project, GraphRole.CANDIDATES).toString());
            var candidate = candidates.getResource(candidateIri);
            if (!candidates.containsResource(candidate)) {
                throw new IllegalStateException("candidate is not in the trusted project graph");
            }
            var status = ResourceFactory.createProperty(PROJECTA + "candidateStatus");
            var validated = ResourceFactory.createResource(PROJECTA + "validated");
            var confirmed = ResourceFactory.createResource(PROJECTA + "confirmed");
            if (!candidates.contains(candidate, status, validated)) {
                throw new IllegalStateException("candidate is not validated for review binding");
            }
            var belongsToProject = ResourceFactory.createProperty(PROJECTA + "belongsToProject");
            var projectResource = ResourceFactory.createResource(BASE + project.value());
            if (!candidates.contains(candidate, belongsToProject, projectResource)) {
                throw new IllegalStateException("candidate is outside the project scope");
            }
            if (!candidates.contains(
                    candidate,
                    ResourceFactory.createProperty(PROJECTA + "proposedOntologyVersion"),
                    ontologyVersion)) {
                throw new IllegalStateException("candidate ontology version does not match the plan");
            }
            candidates.removeAll(candidate, status, null);
            candidate.addProperty(status, confirmed);
            candidate.addProperty(RDFS.comment, bindingComment);
            dataset.commit();
        } catch (RuntimeException exception) {
            dataset.abort();
            throw exception;
        } finally {
            dataset.end();
        }
    }

    /** Builds the materializer over the same dataset with empty released shapes. */
    public ApprovedAssertionMaterializationService materializer(MaterializationAuthorization materialization) {
        var shapes = ModelFactory.createDefaultModel();
        return new ApprovedAssertionMaterializationService(
                dataset, router, new CandidateValidationService(dataset, router, shapes), shapes, materialization, () -> {
                });
    }
}
