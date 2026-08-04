package org.projecta.semanticcore;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.net.URI;
import java.net.http.HttpClient;
import java.util.Map;
import org.junit.jupiter.api.Test;

class M4SemanticServiceTest {
    @Test
    void mapsFusekiRowsToOpaqueEvidenceBackedFacts() {
        var gateway = new StubGateway("""
                {"results":{"bindings":[
                  {"item":{"value":"https://w3id.org/projecta/data/project/checkout/requirement/req-1"},"label":{"value":"Use MFA"},"source":{"value":"https://w3id.org/projecta/data/project/checkout/source/note-1"},"sourceText":{"value":"Use MFA"},"startOffset":{"value":"0"},"endOffset":{"value":"7"}}
                ]}}
                """);
        var service = new M4SemanticService(gateway, new GraphIriRouter(), new M4QueryTemplateRegistry());
        var result = service.retrieve(new ProjectId("checkout"), "current-requirements", Map.of("limit", 10));
        var items = (java.util.List<?>) result.get("items");
        var item = (Map<?, ?>) items.getFirst();
        assertTrue(String.valueOf(item.get("id")).startsWith("id-"));
        assertTrue(String.valueOf(((java.util.List<?>) item.get("citationIds")).getFirst())
                .startsWith("evidence-"));
    }

    @Test
    void inferenceRebuildIsOneDeleteAndRuleMaterializationRequest() {
        var gateway = new StubGateway("{\"results\":{\"bindings\":[]}}");
        var service = new M4SemanticService(gateway, new GraphIriRouter(), new M4QueryTemplateRegistry());
        service.rebuildInference(new ProjectId("checkout"));
        assertTrue(gateway.lastUpdate.contains("DELETE"));
        assertTrue(gateway.lastUpdate.contains("m4.unresolved-dependency"));
        assertTrue(gateway.lastUpdate.contains("m4.delivery-risk"));
        assertTrue(gateway.lastUpdate.contains("m4.impact-review"));
        assertTrue(gateway.lastUpdate.contains("<https://w3id.org/projecta/ontology/implements>"));
        assertTrue(!gateway.lastUpdate.contains("NOW()"));
        String first = gateway.lastUpdate;
        service.rebuildInference(new ProjectId("checkout"));
        assertEquals(first, gateway.lastUpdate);
    }

    private static final class StubGateway extends FusekiGateway {
        private final String selectResponse;
        private String lastUpdate = "";

        private StubGateway(String selectResponse) {
            super(HttpClient.newHttpClient(), URI.create("http://localhost:3030/projecta"));
            this.selectResponse = selectResponse;
        }

        @Override
        public String select(String query) {
            return selectResponse;
        }

        @Override
        public void update(String update) {
            lastUpdate = update;
        }
    }
}
