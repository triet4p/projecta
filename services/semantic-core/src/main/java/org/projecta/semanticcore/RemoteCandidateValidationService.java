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

/** Runs the released candidate, evidence, and approved v0.4 M3 SHACL shapes against Fuseki data. */
public final class RemoteCandidateValidationService {
    private static final String ONTOLOGY_GRAPH = "https://w3id.org/projecta/data/ontology/dev/";
    private static final String PROPOSED_VERSION = "https://w3id.org/projecta/ontology/proposedOntologyVersion";
    private static final Set<String> LEGACY_VERSIONS = Set.of("0.1.0", "0.2.0", "0.3.0");
    private final FusekiGateway gateway;
    private final GraphIriRouter router;
    private final Model legacyShapes;
    private final Model m2Shapes;
    private final Model m3Shapes;

    public RemoteCandidateValidationService(FusekiGateway gateway, GraphIriRouter router, Path shapesDirectory) {
        this.gateway = gateway;
        this.router = router;
        if (!Files.isRegularFile(shapesDirectory.resolve("candidate-shapes.ttl"))
                || !Files.isRegularFile(shapesDirectory.resolve("evidence-shapes.ttl"))
                || !Files.isRegularFile(shapesDirectory.resolve("source-shapes.ttl"))
                || !Files.isRegularFile(shapesDirectory.resolve("llm-extraction-draft-shapes.ttl"))) {
            throw new IllegalStateException("released candidate SHACL shapes are unavailable");
        }
        this.legacyShapes = loadShapes(shapesDirectory, "candidate-shapes.ttl", "source-shapes.ttl");
        this.m2Shapes = ModelFactory.createDefaultModel().add(legacyShapes);
        RDFDataMgr.read(
                this.m2Shapes,
                shapesDirectory.resolve("evidence-shapes.ttl").toUri().toString());
        this.m3Shapes = ModelFactory.createDefaultModel().add(this.m2Shapes);
        RDFDataMgr.read(this.m3Shapes, shapesDirectory.resolve("llm-extraction-draft-shapes.ttl").toUri().toString());
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
        addTargetClosure(data, candidates, gateway.graph(router.route(project, GraphRole.ASSERTED).toString()), candidate);
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
        var candidateModel = ModelFactory.createDefaultModel();
        parse(candidateModel, candidateTurtle);
        data.add(candidateModel);
        addTargetClosure(data, candidateModel, gateway.graph(router.route(project, GraphRole.ASSERTED).toString()), null);
        var provenanceModel = ModelFactory.createDefaultModel();
        parse(provenanceModel, provenanceTurtle);
        data.add(provenanceModel);
        var report = ShaclValidator.get()
                .validate(shapesForCapture(candidateModel, provenanceModel).getGraph(), data.getGraph());
        List<CandidateValidationResult.Violation> violations = report.getEntries().stream()
                .map(entry -> new CandidateValidationResult.Violation(
                        entry.source() == null ? null : entry.source().toString(),
                        entry.resultPath() == null ? null : entry.resultPath().toString(),
                        entry.message()))
                .toList();
        return new CandidateValidationResult(report.conforms(), violations);
    }

    private Model shapesForCapture(Model candidates, Model provenance) {
        var proposedVersion = candidates.createProperty(PROPOSED_VERSION);
        var schemaVersion = candidates.createProperty("https://w3id.org/projecta/ontology/schemaVersion");
        var hasM3Candidate = false;
        var candidateVersions = candidates.listObjectsOfProperty(null, proposedVersion);
        while (candidateVersions.hasNext()) {
            var node = candidateVersions.next();
            if (node.isLiteral() && "0.4.0".equals(node.asLiteral().getString())) {
                hasM3Candidate = true;
                break;
            }
        }
        var hasM3Activity = false;
        var activityVersions = provenance.listObjectsOfProperty(null, schemaVersion);
        while (activityVersions.hasNext()) {
            var node = activityVersions.next();
            if (node.isLiteral() && "m3.v1".equals(node.asLiteral().getString())) {
                hasM3Activity = true;
                break;
            }
        }
        return hasM3Candidate || hasM3Activity ? m3Shapes : m2Shapes;
    }

    private static void parse(org.apache.jena.rdf.model.Model target, String turtle) {
        RDFParser.fromString(turtle, Lang.TURTLE).parse(target);
    }

    private static void addTargetClosure(Model data, Model candidates, Model asserted, Resource focus) {
        var relationSource = candidates.createProperty("https://w3id.org/projecta/ontology/relationSource");
        var relationTarget = candidates.createProperty("https://w3id.org/projecta/ontology/relationTarget");
        var linkTarget = candidates.createProperty("https://w3id.org/projecta/ontology/linkTarget");
        var resources = new java.util.ArrayList<Resource>();
        var subjects = focus == null ? candidates.listSubjects().toList() : List.of(focus);
        for (var subject : subjects) {
            candidates.listObjectsOfProperty(subject, relationSource)
                    .filterKeep(org.apache.jena.rdf.model.RDFNode::isResource)
                    .forEachRemaining(node -> resources.add(node.asResource()));
            candidates.listObjectsOfProperty(subject, relationTarget)
                    .filterKeep(org.apache.jena.rdf.model.RDFNode::isResource)
                    .forEachRemaining(node -> resources.add(node.asResource()));
            candidates.listObjectsOfProperty(subject, linkTarget)
                    .filterKeep(org.apache.jena.rdf.model.RDFNode::isResource)
                    .forEachRemaining(node -> resources.add(node.asResource()));
        }
        resources.forEach(resource -> data.add(asserted.listStatements(resource, null, (org.apache.jena.rdf.model.RDFNode) null).toList()));
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
        return m3Shapes;
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
