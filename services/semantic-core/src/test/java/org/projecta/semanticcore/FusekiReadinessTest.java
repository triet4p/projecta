package org.projecta.semanticcore;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.sun.net.httpserver.HttpServer;
import java.net.InetSocketAddress;
import java.net.http.HttpClient;
import java.util.Map;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.jupiter.api.Test;

class FusekiReadinessTest {
    @Test
    void reportsReadyWhenTheConfiguredDatasetAnswersAnAskQuery() throws Exception {
        var rawQuery = new AtomicReference<String>();
        var server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/projecta/query", exchange -> {
            rawQuery.set(exchange.getRequestURI().getRawQuery());
            exchange.sendResponseHeaders(200, -1);
            exchange.close();
        });
        server.start();
        try {
            var configuration = SemanticCoreConfiguration.fromEnvironment(Map.of(
                    "FUSEKI_BASE_URL", "http://127.0.0.1:" + server.getAddress().getPort() + "/projecta"));
            var readiness = new FusekiReadiness(HttpClient.newHttpClient(), configuration);

            assertTrue(readiness.isReady());
            assertEquals("query=ASK%7B%7D", rawQuery.get());
        } finally {
            server.stop(0);
        }
    }

    @Test
    void reportsUnreadyWhenTheConfiguredDatasetCannotAnswer() throws Exception {
        var server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/projecta/query", exchange -> {
            exchange.sendResponseHeaders(503, -1);
            exchange.close();
        });
        server.start();
        try {
            var configuration = SemanticCoreConfiguration.fromEnvironment(Map.of(
                    "FUSEKI_BASE_URL", "http://127.0.0.1:" + server.getAddress().getPort() + "/projecta"));
            var readiness = new FusekiReadiness(HttpClient.newHttpClient(), configuration);

            assertFalse(readiness.isReady());
        } finally {
            server.stop(0);
        }
    }
}
