package org.projecta.semanticcore;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/** Finite read and validation views backed by Fuseki; no client SPARQL crosses this boundary. */
public final class FusekiQueryService {
    private static final String PROJECTA = "https://w3id.org/projecta/ontology/";
    private static final String PROV = "http://www.w3.org/ns/prov#";
    private final FusekiGateway gateway;
    private final GraphIriRouter router;
    private final RemoteCandidateValidationService validation;
    private final ObjectMapper json = new ObjectMapper();

    public FusekiQueryService(
            FusekiGateway gateway, GraphIriRouter router, RemoteCandidateValidationService validation) {
        this.gateway = gateway;
        this.router = router;
        this.validation = validation;
    }

    public CandidateValidationResult validate(ProjectId project, String candidateId) {
        candidate(project, candidateId);
        return validation.validate(project, candidateId);
    }

    public List<Map<String, String>> current(ProjectId project, String type) {
        if (type != null && !type.equals("Requirement"))
            throw new IllegalArgumentException("knowledge-item type is not allowlisted");
        var filter = type == null ? "" : " ; a <" + PROJECTA + type + ">";
        return rows(gateway.select("SELECT ?item ?label ?validFrom WHERE { GRAPH <"
                + router.route(project, GraphRole.ASSERTED) + "> { ?item a <" + PROJECTA + "KnowledgeItem>" + filter
                + " ; <http://www.w3.org/2000/01/rdf-schema#label> ?label ; <" + PROJECTA
                + "validFrom> ?validFrom . } }"));
    }

    public List<Map<String, String>> history(ProjectId project, String candidateId) {
        return rows(gateway.select("SELECT ?activity ?decision ?reviewer ?endedAt WHERE { GRAPH <"
                + router.route(project, GraphRole.PROVENANCE) + "> { ?activity <" + PROV + "used> <"
                + candidate(project, candidateId) + "> ; <" + PROJECTA + "reviewDecision> ?decision ; <" + PROV
                + "wasAssociatedWith> ?reviewer ; <" + PROV + "endedAtTime> ?endedAt . } } ORDER BY ?endedAt"));
    }

    public List<Map<String, String>> evidence(ProjectId project, String itemId) {
        var item = "https://w3id.org/projecta/data/project/" + project.value() + "/requirement/" + itemId;
        return rows(gateway.select(
                "SELECT ?candidate ?source ?reviewer WHERE { GRAPH <" + router.route(project, GraphRole.ASSERTED)
                        + "> { <" + item + "> <" + PROV + "wasDerivedFrom> ?candidate ; <" + PROV
                        + "wasAttributedTo> ?reviewer . } GRAPH <" + router.route(project, GraphRole.CANDIDATES)
                        + "> { ?candidate <" + PROV + "wasDerivedFrom> ?source . } }"));
    }

    private List<Map<String, String>> rows(String body) {
        try {
            var result = new ArrayList<Map<String, String>>();
            for (JsonNode row : json.readTree(body).path("results").path("bindings")) {
                var values = new java.util.LinkedHashMap<String, String>();
                row.fields()
                        .forEachRemaining(entry -> values.put(
                                entry.getKey(), entry.getValue().path("value").asText()));
                result.add(values);
            }
            return result;
        } catch (Exception exception) {
            throw new IllegalStateException("semantic store response was invalid", exception);
        }
    }

    private String candidate(ProjectId project, String id) {
        if (id == null || !id.matches("[a-z0-9][a-z0-9-]{0,62}"))
            throw new IllegalArgumentException("candidate ID is invalid");
        return "https://w3id.org/projecta/data/project/" + project.value() + "/candidate/" + id;
    }
}
