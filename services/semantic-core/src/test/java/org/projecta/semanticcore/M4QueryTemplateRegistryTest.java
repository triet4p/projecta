package org.projecta.semanticcore;

import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.Map;
import org.junit.jupiter.api.Test;

class M4QueryTemplateRegistryTest {
    @Test
    void acceptsOnlyVersionedBoundedQueries() {
        var registry = new M4QueryTemplateRegistry();
        assertTrue(registry.queryIds().contains("current-requirements"));
        registry.validate("current-requirements", Map.of("limit", 10));
        assertThrows(IllegalArgumentException.class, () -> registry.validate("arbitrary", Map.of()));
        assertThrows(
                IllegalArgumentException.class, () -> registry.validate("current-requirements", Map.of("graph", "x")));
        assertThrows(
                IllegalArgumentException.class,
                () -> registry.validate("current-requirements", Map.of("requirementId", "req-1")));
        assertThrows(
                IllegalArgumentException.class, () -> registry.validate("requirement-history", Map.of("limit", 10)));
    }
}
