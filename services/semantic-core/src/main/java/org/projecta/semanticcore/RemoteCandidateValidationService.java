package org.projecta.semanticcore;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Set;
import org.apache.jena.rdf.model.Model;
import org.apache.jena.rdf.model.ModelFactory;
import org.apache.jena.rdf.model.Resource;
import org.apache.jena.riot.Lang;
import org.apache.jena.riot.RDFDataMgr;
import org.apache.jena.riot.RDFParser;
import org.apache.jena.shacl.ShaclValidator;

/** Runs the released candidate and source-evidence SHACL shapes against Fuseki data. */
public final class RemoteCandidateValidationService {
    // The local M2 runtime validates against the approved-but-unpublished draft loaded by bootstrap_fuseki.py.
    private static final String ONTOLOGY_GRAPH = "https://w3id.org/projecta/data/ontology/dev/";
    private static final String PROPOSED_VERSION = "https://w3id.org/projecta/ontology/proposedOntologyVersion";
    private static final Set<String> LEGACY_VERSIONS = Set.of("0.1.0", "0.2.0");
    private final FusekiGateway gateway;
    private final GraphIriRouter router;
    private final Model legacyShapes;
    private final Model m2Shapes;

    public RemoteCandidateValidationService(FusekiGateway gateway, GraphIriRouter router, Path shapesDirectory) {
        this.gateway = gateway;
        this.router = router;
        if (!Files.isRegularFile(shapesDirectory.resolve("candidate-shapes.ttl"))
                || !Files.isRegularFile(shapesDirectory.resolve("evidence-shapes.ttl"))
                || !Files.isRegularFile(shapesDirectory.resolve("source-shapes.ttl"))) {
            throw new IllegalStateException("released candidate SHACL shapes are unavailable");
        }
        this.legacyShapes = loadShapes(shapesDirectory, "candidate-shapes.ttl", "source-shapes.ttl");
        this.m2Shapes = ModelFactory.createDefaultModel().add(legacyShapes);
        RDFDataMgr.read(
                this.m2Shapes,
                shapesDirectory.resolve("evidence-shapes.ttl").toUri().toString());
    }

    /**
     * Validates only the requested candidate, its direct project closure, and released ontology terms.
     *
     * @throws CandidateNotFoundException when the candidate is absent from the trusted project graph
     */
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
        var sources = gateway.graph(router.route(project, GraphRole.SOURCES).toString());
        candidates
                .listObjectsOfProperty(candidate, candidates.createProperty("http://www.w3.org/ns/prov#wasDerivedFrom"))
                .filterKeep(org.apache.jena.rdf.model.RDFNode::isResource)
                .forEachRemaining(source -> {
                    var sourceResource = source.asResource();
                    data.add(sources.listStatements(sourceResource, null, (org.apache.jena.rdf.model.RDFNode) null)
                            .toList());
                    sources.listObjectsOfProperty(
                                    sourceResource,
                                    sources.createProperty("https://w3id.org/projecta/ontology/isItemOf"))
                            .filterKeep(org.apache.jena.rdf.model.RDFNode::isResource)
                            .forEachRemaining(note -> {
                                var noteResource = note.asResource();
                                data.add(sources.listStatements(
                                                noteResource, null, (org.apache.jena.rdf.model.RDFNode) null)
                                        .toList());
                                sources.listObjectsOfProperty(
                                                noteResource,
                                                sources.createProperty("https://w3id.org/projecta/ontology/authoredBy"))
                                        .filterKeep(org.apache.jena.rdf.model.RDFNode::isResource)
                                        .forEachRemaining(person -> data.add(sources.listStatements(
                                                        person.asResource(), null, (org.apache.jena.rdf.model.RDFNode)
                                                                null)
                                                .toList()));
                                sources.listObjectsOfProperty(
                                                noteResource,
                                                sources.createProperty(
                                                        "https://w3id.org/projecta/ontology/belongsToProject"))
                                        .filterKeep(org.apache.jena.rdf.model.RDFNode::isResource)
                                        .forEachRemaining(projectResource -> data.add(sources.listStatements(
                                                        projectResource.asResource(),
                                                        null,
                                                        (org.apache.jena.rdf.model.RDFNode) null)
                                                .toList()));
                                sources.listObjectsOfProperty(
                                                noteResource,
                                                sources.createProperty(
                                                        "https://w3id.org/projecta/ontology/hasNoteItem"))
                                        .filterKeep(org.apache.jena.rdf.model.RDFNode::isResource)
                                        .forEachRemaining(item -> data.add(sources.listStatements(
                                                        item.asResource(), null, (org.apache.jena.rdf.model.RDFNode)
                                                                null)
                                                .toList()));
                            });
                });
        var report = ShaclValidator.get()
                .validate(shapesForCandidate(candidates, candidate).getGraph(), data.getGraph());
        List<CandidateValidationResult.Violation> violations = report.getEntries().stream()
                .map(entry -> new CandidateValidationResult.Violation(
                        entry.source() == null ? null : entry.source().toString(),
                        entry.resultPath() == null ? null : entry.resultPath().toString(),
                        entry.message()))
                .toList();
        return new CandidateValidationResult(report.conforms(), violations);
    }

    /** Validates the complete source/candidate/provenance payload before capture commits it. */
    public CandidateValidationResult validateCapture(
            ProjectId project, String sourceTurtle, String candidateTurtle, String provenanceTurtle) {
        var data = ModelFactory.createDefaultModel();
        data.add(gateway.graph(ONTOLOGY_GRAPH));
        parse(data, sourceTurtle);
        parse(data, candidateTurtle);
        parse(data, provenanceTurtle);
        var report = ShaclValidator.get().validate(m2Shapes.getGraph(), data.getGraph());
        List<CandidateValidationResult.Violation> violations = report.getEntries().stream()
                .map(entry -> new CandidateValidationResult.Violation(
                        entry.source() == null ? null : entry.source().toString(),
                        entry.resultPath() == null ? null : entry.resultPath().toString(),
                        entry.message()))
                .toList();
        return new CandidateValidationResult(report.conforms(), violations);
    }

    private static void parse(org.apache.jena.rdf.model.Model target, String turtle) {
        RDFParser.fromString(turtle, Lang.TURTLE).parse(target);
    }

    private static Model loadShapes(Path shapesDirectory, String... filenames) {
        var loaded = ModelFactory.createDefaultModel();
        for (var filename : filenames) {
            RDFDataMgr.read(loaded, shapesDirectory.resolve(filename).toUri().toString());
        }
        return loaded;
    }

    private Model shapesForCandidate(Model candidates, Resource candidate) {
        var versions = candidates
                .listObjectsOfProperty(candidate, candidates.createProperty(PROPOSED_VERSION))
                .filterKeep(org.apache.jena.rdf.model.RDFNode::isLiteral)
                .mapWith(node -> node.asLiteral().getString())
                .toList();
        if (versions.size() == 1 && LEGACY_VERSIONS.contains(versions.get(0))) {
            return legacyShapes;
        }
        return m2Shapes;
    }

    /** Convenience predicate for callers that do not need SHACL violation details. */
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
