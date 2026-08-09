package org.projecta.semanticcore;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import com.sun.net.httpserver.HttpServer;
import java.net.InetSocketAddress;
import java.net.URI;
import java.net.http.HttpClient;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.jupiter.api.Test;

class FusekiGatewayTest {
    @Test
    void acceptsOnlyBoundedCorrelationMetadata() {
        var gateway = new FusekiGateway(HttpClient.newHttpClient(), URI.create("http://fuseki:3030/projecta"));

        assertDoesNotThrow(() -> gateway.setCorrelation("req-1", "op-1"));
        assertDoesNotThrow(() -> gateway.setCorrelation(null, ""));
    }

    @Test
    void mapsUnavailableFusekiToOneSafeFailure() {
        var gateway = new FusekiGateway(HttpClient.newHttpClient(), URI.create("http://127.0.0.1:1/projecta"));

        var failure = assertThrows(IllegalStateException.class, () -> gateway.select("SELECT * WHERE {}"));

        assertEquals("semantic store request failed", failure.getMessage());
    }

    @Test
    void invalidFusekiResponseFailsBeforeAnyMutation() throws Exception {
        var updateCalls = new AtomicInteger();
        var server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/projecta/query", exchange -> {
            var body = "not-json".getBytes(StandardCharsets.UTF_8);
            exchange.sendResponseHeaders(200, body.length);
            try (var output = exchange.getResponseBody()) {
                output.write(body);
            }
        });
        server.createContext("/projecta/update", exchange -> {
            updateCalls.incrementAndGet();
            exchange.sendResponseHeaders(200, -1);
            exchange.close();
        });
        server.start();
        try {
            var gateway = new FusekiGateway(
                    HttpClient.newHttpClient(),
                    URI.create("http://127.0.0.1:" + server.getAddress().getPort() + "/projecta"));
            var service = new FusekiQueryService(gateway, new GraphIriRouter(), null);

            var failure = assertThrows(
                    IllegalStateException.class, () -> service.current(new ProjectId("ecommerce-checkout"), null));

            assertEquals("semantic store response was invalid", failure.getMessage());
            assertEquals(0, updateCalls.get());
        } finally {
            server.stop(0);
        }
    }
}
