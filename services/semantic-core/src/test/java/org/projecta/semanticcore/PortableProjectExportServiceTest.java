package org.projecta.semanticcore;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.ByteArrayOutputStream;
import java.net.URI;
import java.net.http.HttpClient;
import java.nio.charset.StandardCharsets;
import java.util.List;
import org.apache.jena.fuseki.main.FusekiServer;
import org.apache.jena.query.Dataset;
import org.apache.jena.query.DatasetFactory;
import org.apache.jena.query.ReadWrite;
import org.apache.jena.rdf.model.ResourceFactory;
import org.junit.jupiter.api.Test;

class PortableProjectExportServiceTest {
    private static final String PROJECTA = "https://w3id.org/projecta/ontology/";

    @Test
    void streamsPopulatedGraphsInCanonicalRoleOrder() {
        var router = new GraphIriRouter();
        var project = new ProjectId("ecommerce-checkout");
        Dataset dataset = DatasetFactory.createTxnMem();
        dataset.begin(ReadWrite.WRITE);
        try {
            dataset.getNamedModel(router.route(project, GraphRole.SOURCES).toString())
                    .add(
                            ResourceFactory.createResource(
                                    "https://w3id.org/projecta/data/project/ecommerce-checkout/note/n1"),
                            ResourceFactory.createProperty(PROJECTA + "exportMarker"),
                            ResourceFactory.createStringLiteral("source marker"));
            dataset.getNamedModel(router.route(project, GraphRole.CANDIDATES).toString())
                    .add(
                            ResourceFactory.createResource(
                                    "https://w3id.org/projecta/data/project/ecommerce-checkout/candidate/c1"),
                            ResourceFactory.createProperty(PROJECTA + "exportMarker"),
                            ResourceFactory.createStringLiteral("candidate marker"));
            dataset.commit();
        } finally {
            dataset.end();
        }

        var server = FusekiServer.create()
                .loopback(true)
                .port(0)
                .add("/projecta", dataset)
                .build();
        try {
            server.start();
            var gateway = new FusekiGateway(
                    HttpClient.newHttpClient(), URI.create("http://127.0.0.1:" + server.getPort() + "/projecta"));
            var output = new ByteArrayOutputStream();

            var tripleCount =
                    new PortableProjectExportService(gateway, router).writeTriG(project, output, ignored -> {});

            assertEquals(2L, tripleCount);
            var trig = output.toString(StandardCharsets.UTF_8);
            assertTrue(trig.contains("source marker"), trig);
            assertTrue(trig.contains("candidate marker"), trig);
            var graphOrder = List.of(
                    GraphRole.SOURCES,
                    GraphRole.CANDIDATES,
                    GraphRole.ASSERTED,
                    GraphRole.INFERRED,
                    GraphRole.PROVENANCE);
            var previous = -1;
            for (var role : graphOrder) {
                var position = trig.indexOf("<" + router.route(project, role) + "> {");
                assertTrue(position > previous, trig);
                previous = position;
            }
        } finally {
            server.stop();
            dataset.close();
        }
    }
}
