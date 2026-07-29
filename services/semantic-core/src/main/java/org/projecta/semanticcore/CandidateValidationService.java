package org.projecta.semanticcore;

import java.util.List;
import org.apache.jena.query.Dataset;
import org.apache.jena.rdf.model.Model;
import org.apache.jena.shacl.ShaclValidator;
import org.apache.jena.shacl.validation.ReportEntry;

/** Validates a project's candidate graph without mutating any lifecycle graph. */
public final class CandidateValidationService {
    private final Dataset dataset;
    private final GraphIriRouter graphRouter;
    private final Model releasedShapes;

    public CandidateValidationService(Dataset dataset, GraphIriRouter graphRouter, Model releasedShapes) {
        this.dataset = dataset;
        this.graphRouter = graphRouter;
        this.releasedShapes = releasedShapes;
    }

    public CandidateValidationResult validate(ProjectId projectId) {
        var candidates = dataset.getNamedModel(
                graphRouter.route(projectId, GraphRole.CANDIDATES).toString());
        var report = ShaclValidator.get().validate(releasedShapes.getGraph(), candidates.getGraph());
        List<CandidateValidationResult.Violation> violations = report.getEntries().stream()
                .map(ReportEntry::message)
                .map(CandidateValidationResult.Violation::new)
                .toList();
        return new CandidateValidationResult(report.conforms(), violations);
    }
}
