package org.projecta.semanticcore;

import com.fasterxml.jackson.core.JsonFactory;
import com.fasterxml.jackson.core.JsonParser;
import com.fasterxml.jackson.core.JsonToken;
import io.javalin.Javalin;
import java.io.BufferedWriter;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.io.OutputStreamWriter;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.function.LongConsumer;
import org.apache.jena.datatypes.TypeMapper;
import org.apache.jena.graph.Node;
import org.apache.jena.graph.NodeFactory;
import org.apache.jena.riot.out.NodeFmtLib;

/** Streams one typed, project-scoped five-graph snapshot from a single Fuseki SELECT. */
public final class PortableProjectExportService {
    public static final long MAX_TRIPLES = 1_000_000L;

    private static final JsonFactory JSON = JsonFactory.builder().build();

    public static String javaRuntimeVersion() {
        return System.getProperty("java.runtime.version", "unknown");
    }

    public static String fusekiVersion() {
        return packageVersion(org.apache.jena.fuseki.main.FusekiServer.class);
    }

    public static String jenaVersion() {
        return packageVersion(org.apache.jena.riot.RDFParser.class);
    }

    public static String javalinVersion() {
        return packageVersion(Javalin.class);
    }

    private static String packageVersion(Class<?> type) {
        var version = type.getPackage().getImplementationVersion();
        return version == null ? "unknown" : version;
    }

    private final FusekiGateway gateway;
    private final GraphIriRouter graphRouter;

    public PortableProjectExportService(FusekiGateway gateway, GraphIriRouter graphRouter) {
        this.gateway = gateway;
        this.graphRouter = graphRouter;
    }

    /**
     * Writes UTF-8 TriG containing every triple in the five canonical project graphs.
     * The callback runs after the aggregate count is known but before the first output byte.
     */
    public long writeTriG(ProjectId projectId, OutputStream destination, LongConsumer beforeBody) {
        var graphs = List.of(
                graphRouter.route(projectId, GraphRole.SOURCES).toString(),
                graphRouter.route(projectId, GraphRole.CANDIDATES).toString(),
                graphRouter.route(projectId, GraphRole.ASSERTED).toString(),
                graphRouter.route(projectId, GraphRole.INFERRED).toString(),
                graphRouter.route(projectId, GraphRole.PROVENANCE).toString());
        var graphIndexes = new HashMap<String, Integer>();
        for (int index = 0; index < graphs.size(); index++) {
            graphIndexes.put(graphs.get(index), index);
        }
        var values =
                String.join(" ", graphs.stream().map(graph -> "<" + graph + ">").toList());
        var orderedGraphValues = new StringBuilder();
        for (int index = 0; index < graphs.size(); index++) {
            if (index > 0) orderedGraphValues.append(' ');
            orderedGraphValues
                    .append('(')
                    .append(index)
                    .append(" <")
                    .append(graphs.get(index))
                    .append(">)");
        }
        var query = "SELECT ?tripleCount ?g ?s ?p ?o WHERE { "
                + "{ SELECT (COUNT(*) AS ?tripleCount) WHERE { VALUES ?countGraph { " + values
                + " } GRAPH ?countGraph { ?countS ?countP ?countO } } } "
                + "OPTIONAL { VALUES (?graphIndex ?g) { " + orderedGraphValues + " } GRAPH ?g { ?s ?p ?o } } "
                + "} ORDER BY ?graphIndex ?s ?p ?o";
        return gateway.selectStream(query, input -> writeRows(input, destination, graphs, graphIndexes, beforeBody));
    }

    private static long writeRows(
            InputStream input,
            OutputStream destination,
            List<String> graphs,
            Map<String, Integer> graphIndexes,
            LongConsumer beforeBody) {
        try (var parser = JSON.createParser(input)) {
            var results = new BindingsReader(parser);
            var row = results.next();
            if (row == null) throw new IllegalStateException("semantic export query returned no count");
            long declaredCount = row.tripleCount();
            if (declaredCount < 0) throw new IllegalStateException("semantic export count is invalid");
            if (declaredCount > MAX_TRIPLES) throw new ExportTooLargeException();
            beforeBody.accept(declaredCount);

            var writer = new BufferedWriter(new OutputStreamWriter(destination, StandardCharsets.UTF_8));
            long observedCount = 0;
            int graphIndex = 0;
            writeGraphStart(writer, graphs.get(graphIndex));
            while (row != null) {
                if (row.graph() == null) {
                    if (row.subject() != null
                            || row.predicate() != null
                            || row.object() != null
                            || declaredCount != 0) {
                        throw new IllegalStateException("semantic export contains an incomplete row");
                    }
                    row = results.next();
                    continue;
                }
                Integer nextGraphIndex = graphIndexes.get(row.graph());
                if (nextGraphIndex == null
                        || nextGraphIndex < graphIndex
                        || row.subject() == null
                        || row.predicate() == null
                        || row.object() == null
                        || row.tripleCount() != declaredCount) {
                    throw new IllegalStateException("semantic export row is outside the typed snapshot");
                }
                while (graphIndex < nextGraphIndex) {
                    writer.write("}\n");
                    graphIndex++;
                    writeGraphStart(writer, graphs.get(graphIndex));
                }
                writer.write("  ");
                writer.write(NodeFmtLib.strNT(row.subject()));
                writer.write(' ');
                writer.write(NodeFmtLib.strNT(row.predicate()));
                writer.write(' ');
                writer.write(NodeFmtLib.strNT(row.object()));
                writer.write(" .\n");
                observedCount++;
                row = results.next();
            }
            while (graphIndex < graphs.size()) {
                writer.write("}\n");
                graphIndex++;
                if (graphIndex < graphs.size()) writeGraphStart(writer, graphs.get(graphIndex));
            }
            if (observedCount != declaredCount) {
                throw new IllegalStateException("semantic export count changed during the snapshot");
            }
            writer.flush();
            return observedCount;
        } catch (IOException exception) {
            throw new IllegalStateException("semantic export response could not be read", exception);
        }
    }

    private static void writeGraphStart(BufferedWriter writer, String graph) {
        try {
            writer.write('<');
            writer.write(graph);
            writer.write("> {\n");
        } catch (IOException exception) {
            throw new IllegalStateException("semantic export output failed", exception);
        }
    }

    private record Binding(String type, String value, String datatype, String language) {
        Node node() {
            return switch (type) {
                case "uri" -> NodeFactory.createURI(value);
                case "bnode" -> NodeFactory.createBlankNode(value);
                case "literal", "typed-literal" -> literalNode();
                default -> throw new IllegalStateException("semantic export term type is unsupported");
            };
        }

        private Node literalNode() {
            if (language != null && !language.isBlank()) return NodeFactory.createLiteralLang(value, language);
            if (datatype != null && !datatype.isBlank()) {
                return NodeFactory.createLiteralDT(
                        value, TypeMapper.getInstance().getSafeTypeByName(datatype));
            }
            return NodeFactory.createLiteralString(value);
        }
    }

    private record Row(long tripleCount, String graph, Node subject, Node predicate, Node object) {}

    private static final class BindingsReader {
        private final JsonParser parser;
        private boolean bindingsStarted;
        private boolean finished;

        private BindingsReader(JsonParser parser) {
            this.parser = parser;
        }

        private Row next() throws IOException {
            if (finished) return null;
            if (!bindingsStarted) seekBindings();
            if (parser.nextToken() == JsonToken.END_ARRAY) {
                finished = true;
                return null;
            }
            if (parser.currentToken() != JsonToken.START_OBJECT) {
                throw new IllegalStateException("semantic export results are invalid");
            }
            var bindings = new HashMap<String, Binding>();
            while (parser.nextToken() != JsonToken.END_OBJECT) {
                if (parser.currentToken() != JsonToken.FIELD_NAME) {
                    throw new IllegalStateException("semantic export results are invalid");
                }
                String name = parser.currentName();
                if (parser.nextToken() != JsonToken.START_OBJECT) {
                    throw new IllegalStateException("semantic export binding is invalid");
                }
                bindings.put(name, readBinding());
            }
            Binding count = bindings.get("tripleCount");
            if (count == null || !("literal".equals(count.type()) || "typed-literal".equals(count.type()))) {
                throw new IllegalStateException("semantic export count binding is invalid");
            }
            long tripleCount;
            try {
                tripleCount = Long.parseLong(count.value());
            } catch (NumberFormatException exception) {
                throw new IllegalStateException("semantic export count binding is invalid", exception);
            }
            Binding graph = bindings.get("g");
            if (graph != null && !"uri".equals(graph.type())) {
                throw new IllegalStateException("semantic export graph binding is invalid");
            }
            return new Row(
                    tripleCount,
                    graph == null ? null : graph.value(),
                    node(bindings.get("s")),
                    node(bindings.get("p")),
                    node(bindings.get("o")));
        }

        private void seekBindings() throws IOException {
            while (parser.nextToken() != null) {
                if (parser.currentToken() == JsonToken.FIELD_NAME && "bindings".equals(parser.currentName())) {
                    if (parser.nextToken() != JsonToken.START_ARRAY) {
                        throw new IllegalStateException("semantic export bindings are invalid");
                    }
                    bindingsStarted = true;
                    return;
                }
            }
            throw new IllegalStateException("semantic export bindings are missing");
        }

        private Binding readBinding() throws IOException {
            String type = null;
            String value = null;
            String datatype = null;
            String language = null;
            while (parser.nextToken() != JsonToken.END_OBJECT) {
                if (parser.currentToken() != JsonToken.FIELD_NAME) {
                    throw new IllegalStateException("semantic export term is invalid");
                }
                String name = parser.currentName();
                if (parser.nextToken() != JsonToken.VALUE_STRING) {
                    throw new IllegalStateException("semantic export term is invalid");
                }
                String fieldValue = parser.getText();
                switch (name) {
                    case "type" -> type = fieldValue;
                    case "value" -> value = fieldValue;
                    case "datatype" -> datatype = fieldValue;
                    case "xml:lang", "lang" -> language = fieldValue;
                    default -> throw new IllegalStateException("semantic export term field is unsupported");
                }
            }
            if (type == null || value == null) {
                throw new IllegalStateException("semantic export term is incomplete");
            }
            return new Binding(type, value, datatype, language);
        }

        private static Node node(Binding binding) {
            return binding == null ? null : binding.node();
        }
    }

    public static final class ExportTooLargeException extends RuntimeException {
        public ExportTooLargeException() {
            super("semantic export exceeds its fixed triple limit");
        }
    }
}
