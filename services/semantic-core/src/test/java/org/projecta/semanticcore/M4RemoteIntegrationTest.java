package org.projecta.semanticcore;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.net.URI;
import java.net.http.HttpClient;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.Assumptions;
import org.junit.jupiter.api.Test;

class M4RemoteIntegrationTest {
    private static final String ONTOLOGY = "https://w3id.org/projecta/ontology/";
    private static final String RDFS = "http://www.w3.org/2000/01/rdf-schema#";

    @Test
    void rebuildsAllRulesDeterministicallyAndDetectsEveryStaleSnapshot() {
        var endpoint = System.getenv("FUSEKI_BASE_URL");
        Assumptions.assumeTrue(
                endpoint != null && !endpoint.isBlank(), "remote Fuseki is only required in the system suite");
        var project = new ProjectId("m4-" + UUID.randomUUID().toString().substring(0, 8));
        var router = new GraphIriRouter();
        var gateway = new FusekiGateway(HttpClient.newHttpClient(), URI.create(endpoint));
        var service = new M4SemanticService(gateway, router, new M4QueryTemplateRegistry());
        var base = "https://w3id.org/projecta/data/project/" + project.value();
        var asserted = router.route(project, GraphRole.ASSERTED);
        var inferred = router.route(project, GraphRole.INFERRED);
        var provenance = router.route(project, GraphRole.PROVENANCE);

        gateway.update("""
                INSERT DATA { GRAPH <%s> {
                  <%s/requirement/req-old> a <%sRequirement> ; <%slabel> "Old requirement" ;
                    <%svalidFrom> "2026-08-01" ; <%ssupersededBy> <%s/requirement/req-new> .
                  <%s/requirement/req-new> a <%sRequirement> ; <%slabel> "New requirement" ;
                    <%svalidFrom> "2026-08-02" .
                  <%s/task/task-1> a <%sTask> ; <%shasWorkStatus> <%sBlocked> ;
                    <%simplements> <%s/requirement/req-old> .
                  <%s/question/question-1> a <%sQuestion> ; <%slabel> "Open question" ;
                    <%shasWorkStatus> <%sOpen> ; <%sblocks> <%s/task/task-1> .
                } GRAPH <%s> { <%s/inferred/obsolete> a <%sDeliveryRisk> . }
                GRAPH <%s> { <%s/activity/m4-obsolete> a <http://www.w3.org/ns/prov#Activity> . } }
                """.formatted(
                        asserted,
                        base,
                        ONTOLOGY,
                        RDFS,
                        ONTOLOGY,
                        ONTOLOGY,
                        base,
                        base,
                        ONTOLOGY,
                        RDFS,
                        ONTOLOGY,
                        base,
                        ONTOLOGY,
                        ONTOLOGY,
                        ONTOLOGY,
                        ONTOLOGY,
                        base,
                        base,
                        ONTOLOGY,
                        RDFS,
                        ONTOLOGY,
                        ONTOLOGY,
                        ONTOLOGY,
                        base,
                        inferred,
                        base,
                        ONTOLOGY,
                        provenance,
                        base));

        Map<String, Object> first = service.rebuildInference(project);
        assertEquals(
                List.of("m4.delivery-risk", "m4.impact-review", "m4.unresolved-dependency"),
                first.get("materializedRuleIds"));
        assertFalse(gateway.ask("ASK { GRAPH <" + inferred + "> { <" + base + "/inferred/obsolete> ?p ?o } }"));
        assertFalse(gateway.ask(
                "ASK { GRAPH <" + provenance + "> { ?activity <http://www.w3.org/ns/prov#endedAtTime> ?time } }"));
        assertTrue(gateway.ask("ASK { GRAPH <" + inferred + "> { <" + base
                + "/inferred/snapshot-m4-v1> a <" + ONTOLOGY + "InferenceSnapshot> ; <" + ONTOLOGY
                + "sourceRevision> ?revision } }"));

        Map<String, Object> second = service.rebuildInference(project);
        assertEquals(first.get("sourceRevision"), second.get("sourceRevision"));
        assertEquals(first.get("materializationRevision"), second.get("materializationRevision"));

        gateway.update("DELETE DATA { GRAPH <" + asserted + "> { <" + base + "/requirement/req-old> <" + RDFS
                + "label> \"Old requirement\" } }; INSERT DATA { GRAPH <" + asserted + "> { <" + base
                + "/requirement/req-old> <" + RDFS + "label> \"Changed requirement\" } }");
        assertTrue(meta(service.retrieve(project, "unresolved-blockers", Map.of("limit", 50)))
                .get("stale")
                .equals(true));

        service.rebuildInference(project);
        assertEquals(
                false,
                meta(service.retrieve(project, "unresolved-blockers", Map.of("limit", 50)))
                        .get("stale"));

        gateway.update("CLEAR GRAPH <" + inferred + ">");
        Map<String, Object> empty = service.retrieve(project, "unresolved-blockers", Map.of("limit", 50));
        assertTrue(((List<?>) empty.get("items")).isEmpty());
        assertEquals(true, meta(empty).get("stale"));

        gateway.update("INSERT DATA { GRAPH <" + inferred + "> { <" + base + "/inferred/sentinel> <" + RDFS
                + "label> \"retained\" } }");
        assertThrows(
                IllegalStateException.class,
                () -> gateway.update(
                        "DELETE WHERE { GRAPH <" + inferred + "> { ?s ?p ?o } }; THIS IS NOT VALID SPARQL"));
        assertTrue(gateway.ask("ASK { GRAPH <" + inferred + "> { <" + base + "/inferred/sentinel> <" + RDFS
                + "label> \"retained\" } }"));
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> meta(Map<String, Object> result) {
        return (Map<String, Object>) result.get("meta");
    }
}
