package org.projecta.semanticcore;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.util.Map;
import org.junit.jupiter.api.Test;

class SemanticCoreConfigurationTest {
    @Test
    void requiresFusekiUrl() {
        assertThrows(IllegalArgumentException.class, () -> SemanticCoreConfiguration.fromEnvironment(Map.of()));
    }

    @Test
    void derivesFusekiPingUrlAndDefaultPort() {
        var configuration =
                SemanticCoreConfiguration.fromEnvironment(Map.of("FUSEKI_BASE_URL", "http://fuseki:3030/projecta"));

        assertEquals(8080, configuration.port());
        assertEquals("http://fuseki:3030/$/ping", configuration.fusekiPingUrl().toString());
    }

    @Test
    void rejectsInvalidPort() {
        assertThrows(
                IllegalArgumentException.class,
                () -> SemanticCoreConfiguration.fromEnvironment(
                        Map.of("FUSEKI_BASE_URL", "http://fuseki:3030/projecta", "SEMANTIC_CORE_PORT", "0")));
    }
}
