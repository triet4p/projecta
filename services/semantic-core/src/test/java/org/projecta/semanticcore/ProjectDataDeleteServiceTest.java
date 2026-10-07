package org.projecta.semanticcore;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.net.URI;
import java.net.http.HttpClient;
import org.apache.jena.fuseki.main.FusekiServer;
import org.apache.jena.query.DatasetFactory;
import org.junit.jupiter.api.Test;

class ProjectDataDeleteServiceTest {
    @Test
    void countsAndDeletesExactlyOneProjectScope() {
        var router = new GraphIriRouter();
        var dataset = DatasetFactory.createTxnMem();
        var server = FusekiServer.create().loopback(true).port(0).add("/projecta", dataset).build();
        try {
            server.start();
            var gateway = new FusekiGateway(
                    HttpClient.newHttpClient(), URI.create("http://127.0.0.1:" + server.getPort() + "/projecta"));
            var service = new ProjectDataDeleteService(gateway, router);
            var victim = new ProjectId("delete-victim");
            var survivor = new ProjectId("delete-survivor");

            gateway.update("INSERT DATA { GRAPH <" + router.route(victim, GraphRole.SOURCES) + "> { "
                    + "<https://w3id.org/projecta/data/project/delete-victim/source/s1> "
                    + "<https://w3id.org/projecta/ontology/name> \"v\" . } "
                    + "GRAPH <" + router.route(victim, GraphRole.ASSERTED) + "> { "
                    + "<https://w3id.org/projecta/data/project/delete-victim/task/t1> "
                    + "<https://w3id.org/projecta/ontology/name> \"t\" . } "
                    + "GRAPH <" + router.route(survivor, GraphRole.ASSERTED) + "> { "
                    + "<https://w3id.org/projecta/data/project/delete-survivor/task/t9> "
                    + "<https://w3id.org/projecta/ontology/name> \"keep\" . } }");

            var before = service.counts(victim);
            assertEquals(2L, ((Number) before.get("total")).longValue());
            assertEquals(1L, ((Number) service.counts(survivor).get("total")).longValue());

            var removed = service.delete(victim);
            assertEquals(2L, ((Number) removed.get("total")).longValue());
            var after = service.counts(victim);
            assertEquals(0L, ((Number) after.get("total")).longValue());
            // Survivor scope is byte-identical: exactly one triple remains.
            assertEquals(1L, ((Number) service.counts(survivor).get("total")).longValue());

            // Deleting an already-absent scope refuses instead of reporting a purge.
            assertThrows(IllegalStateException.class, () -> service.delete(victim));

            // A foreign graph outside the canonical five refuses fail-closed.
            gateway.update("INSERT DATA { GRAPH <https://w3id.org/projecta/data/project/delete-victim/custom/> { "
                    + "<https://w3id.org/projecta/data/project/delete-victim/source/s2> "
                    + "<https://w3id.org/projecta/ontology/name> \"x\" . } }");
            assertThrows(IllegalStateException.class, () -> service.delete(victim));
            assertTrue(gateway.ask("ASK { GRAPH <https://w3id.org/projecta/data/project/delete-victim/custom/> { ?s ?p ?o } }"));
        } finally {
            server.stop();
        }
    }
}
