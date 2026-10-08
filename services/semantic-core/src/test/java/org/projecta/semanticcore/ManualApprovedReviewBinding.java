package org.projecta.semanticcore;

import org.apache.jena.query.Dataset;

/**
 * Test-only composition for the S13-02 connected slice: applies the human-approval lifecycle
 * transition to the real {@code QuickNoteCaptureService} candidate row.
 *
 * <p>This is a thin test-only alias over the production {@code ApprovedCandidateBindingService}
 * domain logic (same validated-to-confirmed transition and exact
 * {@code projecta-approved-candidate/v1} safe review binding, constructed here only with
 * {@code MaterializationAuthorization.enabledForTest()}). Production
 * {@code SemanticCoreApplication} never constructs either class; the production domain logic
 * stays unwired and disabled by default.
 */
final class ManualApprovedReviewBinding {
    private final ApprovedCandidateBindingService delegate;

    ManualApprovedReviewBinding(Dataset dataset, GraphIriRouter router) {
        this.delegate =
                new ApprovedCandidateBindingService(dataset, router, MaterializationAuthorization.enabledForTest());
    }

    /**
     * Marks the captured candidate confirmed with the exact safe review binding.
     *
     * @param project project scope, rechecked against the candidate row
     * @param candidateIri full candidate IRI of the real captured row
     * @param bindingComment exact {@code projecta-approved-candidate/v1|...} comment
     * @param ontologyVersion released manual ontology version, rechecked against the row
     */
    void applyConfirmedBinding(ProjectId project, String candidateIri, String bindingComment, String ontologyVersion) {
        delegate.applyConfirmedBinding(project, candidateIri, bindingComment, ontologyVersion);
    }

    /** Builds the materializer over the same dataset with empty released shapes. */
    ApprovedAssertionMaterializationService materializer(MaterializationAuthorization authorization) {
        return delegate.materializer(authorization);
    }
}
