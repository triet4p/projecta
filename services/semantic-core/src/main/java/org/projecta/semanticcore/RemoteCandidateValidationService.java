package org.projecta.semanticcore;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import org.apache.jena.rdf.model.ModelFactory;
import org.apache.jena.riot.RDFDataMgr;
import org.apache.jena.shacl.ShaclValidator;

/** Runs the released Candidate SHACL shape against the candidate graph in Fuseki. */
public final class RemoteCandidateValidationService {
    private static final String ONTOLOGY_GRAPH = "https://w3id.org/projecta/data/ontology/v/0.2/";
    private final FusekiGateway gateway;
    private final GraphIriRouter router;
    private final org.apache.jena.rdf.model.Model shapes;

    public RemoteCandidateValidationService(FusekiGateway gateway, GraphIriRouter router, Path shapesDirectory) {
        this.gateway = gateway;
        this.router = router;
        if (!Files.isRegularFile(shapesDirectory.resolve("candidate-shapes.ttl"))) {
            throw new IllegalStateException("released candidate SHACL shapes are unavailable");
        }
        this.shapes = ModelFactory.createDefaultModel();
        RDFDataMgr.read(
                this.shapes,
                shapesDirectory.resolve("candidate-shapes.ttl").toUri().toString());
    }

    public CandidateValidationResult validate(ProjectId project, String candidateId) {
        var candidateIri = candidateIri(project, candidateId);
        var candidates =
                gateway.graph(router.route(project, GraphRole.CANDIDATES).toString());
        var candidate = candidates.createResource(candidateIri);
        if (!candidates.containsResource(candidate)) {
            throw new CandidateNotFoundException();
        }
        var data = ModelFactory.createDefaultModel();
        data.add(gateway.graph(ONTOLOGY_GRAPH));
        data.add(candidates
                .listStatements(candidate, null, (org.apache.jena.rdf.model.RDFNode) null)
                .toList());
        candidates
                .listObjectsOfProperty(
                        candidate, candidates.createProperty("https://w3id.org/projecta/ontology/belongsToProject"))
                .filterKeep(org.apache.jena.rdf.model.RDFNode::isResource)
                .forEachRemaining(projectNode -> data.add(candidates
                        .listStatements(projectNode.asResource(), null, (org.apache.jena.rdf.model.RDFNode) null)
                        .toList()));
        var report = ShaclValidator.get().validate(shapes.getGraph(), data.getGraph());
        List<CandidateValidationResult.Violation> violations = report.getEntries().stream()
                .map(entry -> new CandidateValidationResult.Violation(
                        entry.source() == null ? null : entry.source().toString(),
                        entry.resultPath() == null ? null : entry.resultPath().toString(),
                        entry.message()))
                .toList();
        return new CandidateValidationResult(report.conforms(), violations);
    }

    public boolean conforms(ProjectId project, String candidateId) {
        return validate(project, candidateId).conforms();
    }

    private static String candidateIri(ProjectId project, String candidateId) {
        if (candidateId == null || !candidateId.matches("[a-z0-9][a-z0-9-]{0,62}")) {
            throw new IllegalArgumentException("candidate ID is invalid");
        }
        return "https://w3id.org/projecta/data/project/" + project.value() + "/candidate/" + candidateId;
    }
}
