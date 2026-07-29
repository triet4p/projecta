package org.projecta.semanticcore;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import org.junit.jupiter.api.Test;

class GraphIriRouterTest {
    @Test
    void routesOnlyCanonicalProjectGraphs() {
        var graph = new GraphIriRouter().route(new ProjectId("ecommerce-checkout"), GraphRole.ASSERTED);

        assertEquals("https://w3id.org/projecta/data/project/ecommerce-checkout/asserted/", graph.toString());
    }

    @Test
    void rejectsPathTraversalAndCrossProjectInput() {
        assertThrows(IllegalArgumentException.class, () -> new ProjectId("../other-project"));
        assertThrows(IllegalArgumentException.class, () -> new ProjectId("project/other"));
    }
}
