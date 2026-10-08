package org.projecta.semanticcore;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.nio.file.Paths;
import java.util.Map;
import org.junit.jupiter.api.Test;

class SemanticCoreConfigurationTest {
    @Test
    void requiresFusekiUrl() {
        assertThrows(IllegalArgumentException.class, () -> SemanticCoreConfiguration.fromEnvironment(Map.of()));
    }

    @Test
    void derivesFusekiReadinessUrlAndDefaultPort() {
        var configuration =
                SemanticCoreConfiguration.fromEnvironment(Map.of("FUSEKI_BASE_URL", "http://fuseki:3030/projecta"));

        assertEquals(8080, configuration.port());
        assertEquals("0.0.0.0", configuration.host());
        assertEquals(
                "http://fuseki:3030/projecta/query?query=ASK%7B%7D",
                configuration.fusekiReadinessUrl().toString());
        assertEquals(Paths.get("/ontology/shapes"), configuration.shapesDirectory());
    }

    @Test
    void acceptsLoopbackHostForNativeRuntime() {
        var configuration = SemanticCoreConfiguration.fromEnvironment(
                Map.of("FUSEKI_BASE_URL", "http://127.0.0.1:18303/projecta", "SEMANTIC_CORE_HOST", "127.0.0.1"));

        assertEquals("127.0.0.1", configuration.host());
    }

    @Test
    void acceptsPackagedShapesDirectoryForWindowsNativeRuntime() {
        var configuration = SemanticCoreConfiguration.fromEnvironment(Map.of(
                "FUSEKI_BASE_URL",
                "http://127.0.0.1:18303/projecta",
                "PROJECTA_SHAPES_DIRECTORY",
                "C:\\Projecta\\package\\projecta\\ontology\\shapes"));

        assertEquals(Paths.get("C:\\Projecta\\package\\projecta\\ontology\\shapes"), configuration.shapesDirectory());
    }

    @Test
    void rejectsBlankShapesDirectory() {
        assertThrows(
                IllegalArgumentException.class,
                () -> SemanticCoreConfiguration.fromEnvironment(
                        Map.of("FUSEKI_BASE_URL", "http://fuseki:3030/projecta", "PROJECTA_SHAPES_DIRECTORY", "   ")));
    }

    @Test
    void rejectsHostsOutsideApprovedBindAddresses() {
        assertThrows(
                IllegalArgumentException.class,
                () -> SemanticCoreConfiguration.fromEnvironment(
                        Map.of("FUSEKI_BASE_URL", "http://fuseki:3030/projecta", "SEMANTIC_CORE_HOST", "192.168.1.4")));
    }

    @Test
    void rejectsInvalidPort() {
        assertThrows(
                IllegalArgumentException.class,
                () -> SemanticCoreConfiguration.fromEnvironment(
                        Map.of("FUSEKI_BASE_URL", "http://fuseki:3030/projecta", "SEMANTIC_CORE_PORT", "0")));
    }
}
