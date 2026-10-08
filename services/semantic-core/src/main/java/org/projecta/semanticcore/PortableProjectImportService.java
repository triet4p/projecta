package org.projecta.semanticcore;

import java.io.ByteArrayOutputStream;
import java.io.FilterInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import org.apache.jena.graph.Node;
import org.apache.jena.graph.NodeFactory;
import org.apache.jena.query.Dataset;
import org.apache.jena.query.DatasetFactory;
import org.apache.jena.query.ReadWrite;
import org.apache.jena.riot.Lang;
import org.apache.jena.riot.RDFParser;
import org.apache.jena.sparql.core.Quad;

/**
 * Validates and applies one projecta-portable.v1 TriG payload as project state.
 *
 * <p>Import writes the archived state as state. It never calls capture,
 * validation-to-approved, receipt-recording, confirmation, assertion-materialization,
 * inference-rebuild, extraction, model/provider, connector, retry, webhook, or other
 * external-action operations. The inferred graph and its snapshot are copied exactly.
 */
public final class PortableProjectImportService {
    public static final long MAX_TRIPLES = PortableProjectExportService.MAX_TRIPLES;

    private static final String PROJECTA = "https://w3id.org/projecta/ontology/";
    private static final String RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type";

    private static final Map<String, String> M4_DERIVED_RULES = Map.of(
            PROJECTA + "UnresolvedBlocker", "m4.unresolved-dependency",
            PROJECTA + "DeliveryRisk", "m4.delivery-risk",
            PROJECTA + "ImpactReview", "m4.impact-review");
    private static final String BELONGS_TO_PROJECT = PROJECTA + "belongsToProject";
    private static final String DERIVED_FROM_ASSERTION = PROJECTA + "derivedFromAssertion";
    private static final String ABOUT_TASK = PROJECTA + "aboutTask";
    private static final String SOURCE_REVISION = PROJECTA + "sourceRevision";
    private static final String RULE_IDENTIFIER = PROJECTA + "ruleIdentifier";
    private static final String RULE_VERSION = PROJECTA + "ruleVersion";
    private static final String INFERENCE_SNAPSHOT = PROJECTA + "InferenceSnapshot";
    private static final Set<String> FORBIDDEN_IMPORT_PREDICATES = Set.of(
            "secret",
            "secretreference",
            "secretreferencedigest",
            "token",
            "accesstoken",
            "refreshtoken",
            "oauthtoken",
            "providertoken",
            "clientsecret",
            "apikey",
            "privatekey",
            "signingkey",
            "password",
            "ciphertext",
            "credential",
            "credentials",
            "session",
            "sessiontoken",
            "masterkey",
            "setuphandle",
            "authorization");

    private final FusekiGateway gateway;
    private final GraphIriRouter router;
    private final RemoteCandidateValidationService validation;

    public PortableProjectImportService(
            FusekiGateway gateway, GraphIriRouter router, RemoteCandidateValidationService validation) {
        this.gateway = gateway;
        this.router = router;
        this.validation = validation;
    }

    /** Read-only destination check used before the owner confirms apply. */
    public Map<String, Object> validate(
            ProjectId project, String placeholderName, String projectName, InputStream trig) {
        var staged = parseStaged(project, projectName, trig);
        var destination = destinationState(project, placeholderName);
        var result = new LinkedHashMap<String, Object>();
        result.put("destinationState", destination);
        result.put("tripleCount", staged.tripleCount());
        result.put("candidateIds", staged.candidateIds());
        return result;
    }

    /** Atomically installs the archived five-graph state for one project. */
    public Map<String, Object> apply(
            ProjectId project, String placeholderName, String projectName, boolean adoptPlaceholder, InputStream trig) {
        if (projectName == null
                || projectName.isBlank()
                || projectName.length() > 128
                || projectName.strip().length() != projectName.length()) {
            throw new IllegalArgumentException("import project name is invalid");
        }
        var staged = parseStaged(project, projectName, trig);
        var destination = destinationState(project, placeholderName);
        if (adoptPlaceholder) {
            if (!"pristine-placeholder".equals(destination)) {
                throw new IllegalStateException("import destination is not a pristine placeholder");
            }
        } else if (!"absent".equals(destination)) {
            throw new IllegalStateException("import destination already has project state");
        }
        var graphs = canonicalGraphs(project);
        var deleteData = new StringBuilder();
        if (adoptPlaceholder) {
            var asserted = graphs.get(GraphRole.ASSERTED);
            var projectIri = "https://w3id.org/projecta/data/project/" + project.value();
            deleteData
                    .append("DELETE WHERE { GRAPH <")
                    .append(asserted)
                    .append("> { <")
                    .append(projectIri)
                    .append("> ?p ?o } }; ");
        }
        var insertData = new StringBuilder();
        for (var role : GraphRole.values()) {
            var quads = staged.byGraph().get(role);
            if (quads == null || quads.isEmpty()) {
                continue;
            }
            insertData.append("INSERT DATA { GRAPH <").append(graphs.get(role)).append("> { ");
            for (var quad : quads) {
                insertData.append(sparqlTerm(quad.getSubject()));
                insertData.append(' ');
                insertData.append(sparqlTerm(quad.getPredicate()));
                insertData.append(' ');
                insertData.append(sparqlTerm(quad.getObject()));
                insertData.append(" . ");
            }
            insertData.append("} }; ");
        }
        var update = deleteData.toString() + insertData.toString();
        if (update.isBlank()) {
            throw new IllegalStateException("import payload has no project triples");
        }
        if (adoptPlaceholder) {
            var projectIri = "https://w3id.org/projecta/data/project/" + project.value();
            var asserted = graphs.get(GraphRole.ASSERTED);
            var rename = "DELETE { GRAPH <"
                    + asserted
                    + "> { <"
                    + projectIri
                    + "> <"
                    + PROJECTA
                    + "name> ?old } } INSERT { GRAPH <"
                    + asserted
                    + "> { <"
                    + projectIri
                    + "> <"
                    + PROJECTA
                    + "name> "
                    + quoted(projectName)
                    + " } } WHERE { GRAPH <"
                    + asserted
                    + "> { <"
                    + projectIri
                    + "> <"
                    + PROJECTA
                    + "name> ?old } }; ";
            update = update + rename;
        }
        gateway.update(update);
        var after = destinationState(project, placeholderName);
        if (!"populated".equals(after)) {
            throw new IllegalStateException("import apply did not publish project state");
        }
        var result = new LinkedHashMap<String, Object>();
        result.put("tripleCount", staged.tripleCount());
        result.put("candidateHandles", staged.candidateHandles());
        return result;
    }

    /** Removes only the exact state installed by {@link #apply}; never clears unrelated project data. */
    public void rollback(
            ProjectId project,
            String placeholderName,
            String projectName,
            boolean restorePlaceholder,
            InputStream trig) {
        var destination = destinationState(project, placeholderName);
        if ("absent".equals(destination) && !restorePlaceholder) {
            return;
        }
        if ("pristine-placeholder".equals(destination) && restorePlaceholder) {
            return;
        }
        if (!"populated".equals(destination)) {
            throw new IllegalStateException("import rollback destination does not match its journal");
        }
        var staged = parseStaged(project, projectName, trig);
        for (var role : GraphRole.values()) {
            var current = gateway.graph(canonicalGraphs(project).get(role));
            var expected = stagedDatasetModel(staged, role);
            try {
                if (!current.isIsomorphicWith(expected)) {
                    throw new IllegalStateException("import rollback state does not match the staged package");
                }
            } finally {
                current.close();
                expected.close();
            }
        }
        var graphs = canonicalGraphs(project);
        var update = new StringBuilder();
        for (var role : GraphRole.values()) {
            update.append("DELETE WHERE { GRAPH <").append(graphs.get(role)).append("> { ?s ?p ?o } }; ");
        }
        if (restorePlaceholder) {
            var projectIri = "https://w3id.org/projecta/data/project/" + project.value();
            var asserted = graphs.get(GraphRole.ASSERTED);
            update.append("INSERT DATA { GRAPH <")
                    .append(asserted)
                    .append("> { <")
                    .append(projectIri)
                    .append("> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <")
                    .append(PROJECTA)
                    .append("Project> ; <")
                    .append(PROJECTA)
                    .append("name> ")
                    .append(quoted(placeholderName))
                    .append(" . } }; ");
        }
        gateway.update(update.toString());
    }

    private StagedTriG parseStaged(ProjectId project, String projectName, InputStream trig) {
        var graphs = canonicalGraphs(project);
        Dataset staged = DatasetFactory.createTxnMem();
        var trackedInput = new GraphNameTrackingInputStream(trig, new HashSet<>(graphs.values()));
        try {
            RDFParser.create().source(trackedInput).lang(Lang.TRIG).parse(staged);
            trackedInput.finish();
            if (!trackedInput.graphNames().equals(new HashSet<>(graphs.values()))) {
                throw new IllegalArgumentException("import TriG must declare exactly the five project graphs");
            }
        } catch (Exception exception) {
            throw new IllegalArgumentException("import TriG payload is invalid", exception);
        }
        try {
            staged.begin(ReadWrite.READ);
            try {
                var byGraph = new HashMap<GraphRole, List<Quad>>();
                long tripleCount = 0;
                if (!staged.asDatasetGraph().getDefaultGraph().isEmpty()) {
                    throw new IllegalArgumentException("import TriG contains default-graph data");
                }
                for (var role : GraphRole.values()) {
                    var model = staged.getNamedModel(graphs.get(role));
                    var quads = new ArrayList<Quad>();
                    var iterator = model.listStatements();
                    while (iterator.hasNext()) {
                        var statement = iterator.next();
                        tripleCount++;
                        if (tripleCount > MAX_TRIPLES) {
                            throw new IllegalStateException("import TriG payload exceeds the triple limit");
                        }
                        quads.add(Quad.create(
                                NodeFactory.createURI(graphs.get(role)),
                                statement.getSubject().asNode(),
                                statement.getPredicate().asNode(),
                                statement.getObject().asNode()));
                        checkNodeProjectScope(statement.getSubject().asNode(), project);
                        checkNodeProjectScope(statement.getPredicate().asNode(), project);
                        checkNoSecretPredicate(statement.getPredicate().asNode());
                        checkNodeProjectScope(statement.getObject().asNode(), project);
                    }
                    byGraph.put(role, quads);
                }
                var graphNames = new HashSet<String>();
                var names = staged.listNames();
                while (names.hasNext()) {
                    graphNames.add(names.next());
                }
                if (!new HashSet<>(graphs.values()).containsAll(graphNames)) {
                    throw new IllegalArgumentException("import TriG contains a non-canonical project graph");
                }
                assertProjectIdentity(project, projectName, byGraph.get(GraphRole.ASSERTED));
                var semanticValidation = validation.validatePortableImport(
                        staged.getNamedModel(graphs.get(GraphRole.SOURCES)),
                        staged.getNamedModel(graphs.get(GraphRole.CANDIDATES)),
                        staged.getNamedModel(graphs.get(GraphRole.ASSERTED)),
                        staged.getNamedModel(graphs.get(GraphRole.INFERRED)),
                        staged.getNamedModel(graphs.get(GraphRole.PROVENANCE)));
                if (!semanticValidation.conforms()) {
                    throw new IllegalArgumentException("import TriG violates the released semantic shapes");
                }
                validateInferenceSemantics(project, byGraph.get(GraphRole.ASSERTED), byGraph.get(GraphRole.INFERRED));
                var candidateIds = candidateIds(byGraph.get(GraphRole.CANDIDATES));
                var candidateHandles = new LinkedHashMap<String, String>();
                for (var id : candidateIds) {
                    candidateHandles.put(id, "candidate-h-" + OpaqueIds.opaqueHandle(id));
                }
                return new StagedTriG(tripleCount, byGraph, candidateIds, candidateHandles);
            } finally {
                staged.end();
            }
        } finally {
            try {
                trig.close();
            } catch (IOException ignored) {
            }
            staged.close();
        }
    }

    private record TripleIndex(Map<Node, Map<Node, List<Node>>> bySubject) {}

    private static void validateInferenceSemantics(ProjectId project, List<Quad> asserted, List<Quad> inferred) {
        var type = NodeFactory.createURI(RDF_TYPE);
        var snapshotSubjects = new HashSet<Node>();
        var derivedRules = new HashMap<Node, String>();
        for (var quad : inferred) {
            if (!type.equals(quad.getPredicate()) || !quad.getObject().isURI()) {
                continue;
            }
            var typeIri = quad.getObject().getURI();
            if (INFERENCE_SNAPSHOT.equals(typeIri)) {
                snapshotSubjects.add(quad.getSubject());
            }
            var expectedRule = M4_DERIVED_RULES.get(typeIri);
            if (expectedRule != null) {
                var previousRule = derivedRules.putIfAbsent(quad.getSubject(), expectedRule);
                if (previousRule != null && !previousRule.equals(expectedRule)) {
                    throw new IllegalArgumentException("import inference item has conflicting rule types");
                }
            }
        }
        if (snapshotSubjects.size() > 1 || (!derivedRules.isEmpty() && snapshotSubjects.size() != 1)) {
            throw new IllegalArgumentException("import inference snapshot is missing or ambiguous");
        }
        if (snapshotSubjects.isEmpty()) {
            return;
        }

        var projectIri = "https://w3id.org/projecta/data/project/" + project.value();
        var snapshot = snapshotSubjects.iterator().next();
        if (!snapshot.isURI() || !snapshot.getURI().equals(projectIri + "/inferred/snapshot-m4-v1")) {
            throw new IllegalArgumentException("import inference snapshot identifier is invalid");
        }
        var assertedIndex = indexBySubject(asserted);
        var inferredIndex = indexBySubject(inferred);
        var projectNode = NodeFactory.createURI(projectIri);
        assertExactlyOneUri(inferredIndex, snapshot, BELONGS_TO_PROJECT, projectNode);
        assertExactlyOneLiteral(inferredIndex, snapshot, RULE_VERSION, "m4.v1");
        var snapshotRevision = exactlyOne(inferredIndex, snapshot, SOURCE_REVISION);
        if (!snapshotRevision.isLiteral()) {
            throw new IllegalArgumentException("import inference snapshot revision is invalid");
        }

        for (var entry : derivedRules.entrySet()) {
            var derived = entry.getKey();
            assertExactlyOneUri(inferredIndex, derived, BELONGS_TO_PROJECT, projectNode);
            assertExactlyOneLiteral(inferredIndex, derived, RULE_IDENTIFIER, entry.getValue());
            assertExactlyOneLiteral(inferredIndex, derived, RULE_VERSION, "1");
            if (!snapshotRevision.equals(exactlyOne(inferredIndex, derived, SOURCE_REVISION))) {
                throw new IllegalArgumentException("import inference item does not match its snapshot revision");
            }
            var task = exactlyOne(inferredIndex, derived, ABOUT_TASK);
            if (!task.isURI() || !hasType(assertedIndex, task, PROJECTA + "Task")) {
                throw new IllegalArgumentException("import inference task reference is unresolved");
            }
            var assertions = objects(inferredIndex, derived, DERIVED_FROM_ASSERTION);
            if (assertions.size() < 2
                    || assertions.stream()
                            .anyMatch(node ->
                                    !node.isURI() || !assertedIndex.bySubject().containsKey(node))) {
                throw new IllegalArgumentException("import inference assertion reference is unresolved");
            }
        }
    }

    private static TripleIndex indexBySubject(List<Quad> quads) {
        var result = new HashMap<Node, Map<Node, List<Node>>>();
        for (var quad : quads) {
            result.computeIfAbsent(quad.getSubject(), ignored -> new HashMap<>())
                    .computeIfAbsent(quad.getPredicate(), ignored -> new ArrayList<>())
                    .add(quad.getObject());
        }
        return new TripleIndex(result);
    }

    private static List<Node> objects(TripleIndex index, Node subject, String predicate) {
        var properties = index.bySubject().get(subject);
        if (properties == null) {
            return List.of();
        }
        return properties.getOrDefault(NodeFactory.createURI(predicate), List.of());
    }

    private static Node exactlyOne(TripleIndex index, Node subject, String predicate) {
        var values = objects(index, subject, predicate);
        if (values.size() != 1) {
            throw new IllegalArgumentException("import inference field is missing or ambiguous");
        }
        return values.get(0);
    }

    private static void assertExactlyOneUri(TripleIndex index, Node subject, String predicate, Node expected) {
        var value = exactlyOne(index, subject, predicate);
        if (!value.isURI() || !expected.equals(value)) {
            throw new IllegalArgumentException("import inference project reference is invalid");
        }
    }

    private static void assertExactlyOneLiteral(TripleIndex index, Node subject, String predicate, String expected) {
        var value = exactlyOne(index, subject, predicate);
        if (!value.isLiteral() || !expected.equals(value.getLiteralLexicalForm())) {
            throw new IllegalArgumentException("import inference version or rule is invalid");
        }
    }

    private static boolean hasType(TripleIndex index, Node subject, String type) {
        return objects(index, subject, RDF_TYPE).contains(NodeFactory.createURI(type));
    }

    private static org.apache.jena.rdf.model.Model stagedDatasetModel(StagedTriG staged, GraphRole role) {
        var model = org.apache.jena.rdf.model.ModelFactory.createDefaultModel();
        for (var quad : staged.byGraph().get(role)) {
            model.getGraph()
                    .add(org.apache.jena.graph.Triple.create(quad.getSubject(), quad.getPredicate(), quad.getObject()));
        }
        return model;
    }

    private static void assertProjectIdentity(ProjectId project, String projectName, List<Quad> asserted) {
        var projectIri = "https://w3id.org/projecta/data/project/" + project.value();
        var typeCount = 0;
        var nameCount = 0;
        for (var quad : asserted) {
            if (!quad.getSubject().isURI()
                    || !projectIri.equals(quad.getSubject().getURI())) {
                continue;
            }
            if (quad.getPredicate().isURI()
                    && RDF_TYPE.equals(quad.getPredicate().getURI())) {
                typeCount++;
                if (!quad.getObject().isURI()
                        || !(PROJECTA + "Project").equals(quad.getObject().getURI())) {
                    throw new IllegalArgumentException("import project identity is invalid");
                }
            }
            if (quad.getPredicate().isURI()
                    && (PROJECTA + "name").equals(quad.getPredicate().getURI())) {
                nameCount++;
                if (!quad.getObject().isLiteral()
                        || !projectName.equals(
                                quad.getObject().getLiteralValue().toString())) {
                    throw new IllegalArgumentException("import project name does not match its manifest");
                }
            }
        }
        if (typeCount != 1 || nameCount != 1) {
            throw new IllegalArgumentException("import project identity is missing or ambiguous");
        }
    }

    private List<String> candidateIds(List<Quad> candidates) {
        var ids = new ArrayList<String>();
        if (candidates == null) {
            return ids;
        }
        for (var quad : candidates) {
            if (quad.getPredicate().isURI()
                    && RDF_TYPE.equals(quad.getPredicate().getURI())
                    && quad.getObject().isURI()
                    && (PROJECTA + "Candidate").equals(quad.getObject().getURI())
                    && quad.getSubject().isURI()) {
                ids.add(quad.getSubject().getURI());
            }
        }
        return ids;
    }

    private String destinationState(ProjectId project, String placeholderName) {
        var graphs = canonicalGraphs(project);
        if (hasForeignProjectGraphs(project, graphs)) {
            return "foreign";
        }
        var counts = new HashMap<GraphRole, Long>();
        long total = 0;
        for (var role : GraphRole.values()) {
            var count = countTriples(graphs.get(role));
            counts.put(role, count);
            total += count;
        }
        if (total == 0) {
            return "absent";
        }
        if (isPristinePlaceholder(project, placeholderName, counts)) {
            return "pristine-placeholder";
        }
        return "populated";
    }

    private boolean isPristinePlaceholder(ProjectId project, String placeholderName, Map<GraphRole, Long> counts) {
        for (var entry : counts.entrySet()) {
            if (entry.getKey() == GraphRole.ASSERTED) {
                if (entry.getValue() != 2L) {
                    return false;
                }
            } else if (entry.getValue() != 0L) {
                return false;
            }
        }
        var projectIri = "https://w3id.org/projecta/data/project/" + project.value();
        var asserted = canonicalGraphs(project).get(GraphRole.ASSERTED);
        var response = gateway.select("SELECT ?name ?type WHERE { GRAPH <"
                + asserted
                + "> { <"
                + projectIri
                + "> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> ?type ; <"
                + PROJECTA
                + "name> ?name . } }");
        try {
            var bindings = new com.fasterxml.jackson.databind.ObjectMapper()
                    .readTree(response)
                    .path("results")
                    .path("bindings");
            if (bindings.size() != 1) {
                return false;
            }
            var row = bindings.get(0);
            var type = row.path("type").path("value").asText();
            var name = row.path("name").path("value").asText();
            return (PROJECTA + "Project").equals(type) && placeholderName.equals(name);
        } catch (Exception exception) {
            throw new IllegalStateException("semantic project state response was invalid", exception);
        }
    }

    private boolean hasForeignProjectGraphs(ProjectId project, Map<GraphRole, String> graphs) {
        var allowed = String.join(
                ", ", graphs.values().stream().map(graph -> "<" + graph + ">").toList());
        var prefix = "https://w3id.org/projecta/data/project/" + project.value() + "/";
        return gateway.ask("ASK { GRAPH ?graph { ?s ?p ?o } FILTER(STRSTARTS(STR(?graph), "
                + quoted(prefix)
                + ")) FILTER(?graph NOT IN ("
                + allowed
                + ")) }");
    }

    private long countTriples(String graph) {
        var response = gateway.select("SELECT (COUNT(*) AS ?count) WHERE { GRAPH <" + graph + "> { ?s ?p ?o } }");
        try {
            var bindings = new com.fasterxml.jackson.databind.ObjectMapper()
                    .readTree(response)
                    .path("results")
                    .path("bindings");
            if (bindings.size() != 1) {
                throw new IllegalStateException("semantic count response was invalid");
            }
            return Long.parseLong(bindings.get(0).path("count").path("value").asText());
        } catch (IllegalStateException exception) {
            throw exception;
        } catch (Exception exception) {
            throw new IllegalStateException("semantic count response was invalid", exception);
        }
    }

    private Map<GraphRole, String> canonicalGraphs(ProjectId project) {
        var result = new HashMap<GraphRole, String>();
        for (var role : GraphRole.values()) {
            result.put(role, router.route(project, role).toString());
        }
        return result;
    }

    private void checkNodeProjectScope(org.apache.jena.graph.Node node, ProjectId project) {
        if (!node.isURI()) {
            return;
        }
        var iri = node.getURI();
        var prefix = "https://w3id.org/projecta/data/project/";
        if (iri.startsWith(prefix)) {
            var remainder = iri.substring(prefix.length());
            var segment = remainder.contains("/") ? remainder.substring(0, remainder.indexOf('/')) : remainder;
            if (!project.value().equals(segment)) {
                throw new IllegalArgumentException("import TriG has a cross-project reference");
            }
        }
    }

    private static void checkNoSecretPredicate(Node predicate) {
        if (!predicate.isURI()) {
            return;
        }
        var iri = predicate.getURI();
        var separator = Math.max(iri.lastIndexOf('/'), iri.lastIndexOf('#'));
        var localName =
                iri.substring(separator + 1).replace("_", "").replace("-", "").toLowerCase(Locale.ROOT);
        if (FORBIDDEN_IMPORT_PREDICATES.contains(localName)) {
            throw new IllegalArgumentException("import TriG contains a prohibited secret field");
        }
    }

    private static String sparqlTerm(org.apache.jena.graph.Node node) {
        return org.apache.jena.riot.out.NodeFmtLib.strNT(node);
    }

    private static String quoted(String value) {
        return "\"" + value.replace("\\", "\\\\").replace("\"", "\\\"") + "\"";
    }

    private static final class GraphNameTrackingInputStream extends FilterInputStream {
        private final Set<String> allowedGraphs;
        private final Set<String> graphNames = new HashSet<>();
        private final ByteArrayOutputStream token = new ByteArrayOutputStream();
        private String lastToken;
        private TokenKind lastTokenKind = TokenKind.OTHER;
        private boolean inComment;
        private boolean inIri;
        private boolean iriEscape;
        private boolean graphOpen;
        private char quote;
        private boolean longString;
        private boolean stringEscape;
        private int quoteRun;
        private char openingQuote;

        private GraphNameTrackingInputStream(InputStream input, Set<String> allowedGraphs) {
            super(input);
            this.allowedGraphs = Set.copyOf(allowedGraphs);
        }

        @Override
        public int read() throws IOException {
            var value = super.read();
            if (value >= 0) {
                accept(value);
            } else {
                finish();
            }
            return value;
        }

        @Override
        public int read(byte[] bytes, int offset, int length) throws IOException {
            var count = super.read(bytes, offset, length);
            if (count < 0) {
                finish();
                return count;
            }
            for (var index = offset; index < offset + count; index++) {
                accept(bytes[index] & 0xff);
            }
            return count;
        }

        private void accept(int value) {
            if (inComment) {
                if (value == '\n' || value == '\r') inComment = false;
                return;
            }
            if (inIri) {
                if (iriEscape) {
                    iriEscape = false;
                } else if (value == '\\') {
                    iriEscape = true;
                } else if (value == '>') {
                    inIri = false;
                    lastToken = token.toString(StandardCharsets.UTF_8);
                    token.reset();
                    lastTokenKind = TokenKind.IRI;
                } else {
                    append(value);
                }
                return;
            }
            if (openingQuote != 0) {
                if (value == openingQuote) {
                    quoteRun++;
                    if (quoteRun == 3) {
                        quote = openingQuote;
                        longString = true;
                        openingQuote = 0;
                        quoteRun = 0;
                    }
                    return;
                }
                if (quoteRun == 2) {
                    lastToken = null;
                    lastTokenKind = TokenKind.OTHER;
                    openingQuote = 0;
                    quoteRun = 0;
                    outside(value);
                    return;
                }
                quote = openingQuote;
                longString = false;
                openingQuote = 0;
                quoteRun = 0;
                insideString(value);
                return;
            }
            if (quote != 0) {
                insideString(value);
                return;
            }
            outside(value);
        }

        private void outside(int value) {
            if (isWhitespace(value)) {
                finishBare();
                return;
            }
            if (value == '#') {
                finishBare();
                inComment = true;
                return;
            }
            if (value == '"' || value == '\'') {
                finishBare();
                openingQuote = (char) value;
                quoteRun = 1;
                return;
            }
            if (value == '<') {
                finishBare();
                token.reset();
                inIri = true;
                iriEscape = false;
                return;
            }
            if (value == '{') {
                finishBare();
                if (graphOpen
                        || lastTokenKind != TokenKind.IRI
                        || lastToken == null
                        || !allowedGraphs.contains(lastToken)
                        || !graphNames.add(lastToken)) {
                    throw new IllegalArgumentException(
                            "import TriG declares a default, repeated, or non-canonical graph");
                }
                graphOpen = true;
                lastToken = null;
                lastTokenKind = TokenKind.OTHER;
                return;
            }
            if (value == '}') {
                finishBare();
                if (!graphOpen) {
                    throw new IllegalArgumentException("import TriG closes an undeclared graph");
                }
                graphOpen = false;
                lastToken = null;
                lastTokenKind = TokenKind.OTHER;
                return;
            }
            if (isPunctuation(value)) {
                finishBare();
                lastToken = null;
                lastTokenKind = TokenKind.OTHER;
                return;
            }
            append(value);
        }

        private void insideString(int value) {
            if (stringEscape) {
                stringEscape = false;
                return;
            }
            if (value == '\\') {
                stringEscape = true;
                return;
            }
            if (value != quote) {
                quoteRun = 0;
                return;
            }
            if (!longString) {
                quote = 0;
                lastToken = null;
                lastTokenKind = TokenKind.OTHER;
                return;
            }
            quoteRun++;
            if (quoteRun == 3) {
                quote = 0;
                longString = false;
                quoteRun = 0;
                lastToken = null;
                lastTokenKind = TokenKind.OTHER;
            }
        }

        private void append(int value) {
            if (token.size() >= 2048) {
                throw new IllegalArgumentException("import TriG token exceeds the supported length");
            }
            token.write(value);
        }

        private void finishBare() {
            if (token.size() == 0) return;
            lastToken = token.toString(StandardCharsets.UTF_8);
            lastTokenKind = TokenKind.OTHER;
            token.reset();
        }

        private void finish() {
            if (openingQuote != 0 && quoteRun == 2) {
                openingQuote = 0;
                quoteRun = 0;
                lastToken = null;
                lastTokenKind = TokenKind.OTHER;
            }
            if (quote != 0 || inIri || openingQuote != 0 || graphOpen) {
                throw new IllegalArgumentException("import TriG contains an incomplete declaration");
            }
            finishBare();
            if (!graphNames.equals(allowedGraphs)) {
                throw new IllegalArgumentException("import TriG must declare exactly the five project graphs");
            }
        }

        private Set<String> graphNames() {
            return Set.copyOf(graphNames);
        }

        private static boolean isWhitespace(int value) {
            return value == ' ' || value == '\t' || value == '\r' || value == '\n' || value == '\f';
        }

        private static boolean isPunctuation(int value) {
            return value == '.'
                    || value == ';'
                    || value == ','
                    || value == '('
                    || value == ')'
                    || value == '['
                    || value == ']'
                    || value == '^';
        }

        private enum TokenKind {
            IRI,
            OTHER
        }
    }

    private record StagedTriG(
            long tripleCount,
            Map<GraphRole, List<Quad>> byGraph,
            List<String> candidateIds,
            Map<String, String> candidateHandles) {}
}
