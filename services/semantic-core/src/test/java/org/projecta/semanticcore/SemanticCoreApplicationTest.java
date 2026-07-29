package org.projecta.semanticcore;

import static org.junit.jupiter.api.Assertions.assertEquals;

import org.junit.jupiter.api.Test;

class SemanticCoreApplicationTest {
    @Test
    void exposesTheServiceIdentity() {
        assertEquals("semantic-core", SemanticCoreApplication.serviceName());
    }
}
