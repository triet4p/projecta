package org.projecta.semanticcore;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.UUID;

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

    /** Validates one candidate in the trusted project's candidates graph. */
    public CandidateValidationResult validate(ProjectId project, String candidateId) {
        candidate(project, candidateId);
        return validation.validate(project, candidateId);
    }

    /** Validates and atomically promotes one conforming extracted candidate. */
    public CandidateValidationResult validateAndMarkValidated(ProjectId project, String candidateId, String actorId) {
        var result = validate(project, candidateId);
        if (result.conforms()) {
            markValidated(project, candidateId, actorId);
        }
        return result;
    }

    /** Marks a conforming extracted candidate ready for the released human-review operations. */
    public void markValidated(ProjectId project, String candidateId, String actorId) {
        var candidate = candidate(project, candidateId);
        if (actorId == null || !actorId.matches("[a-z0-9][a-z0-9-]{0,62}")) {
            throw new IllegalArgumentException("actor ID is invalid");
        }
        var projectIri = "https://w3id.org/projecta/data/project/" + project.value();
        var activity = projectIri + "/activity/validate-" + UUID.randomUUID();
        gateway.update(
                """
                DELETE { GRAPH <%s> { <%s> <%scandidateStatus> <%sextracted> } }
                INSERT {
                  GRAPH <%s> { <%s> <%scandidateStatus> <%svalidated> }
                  GRAPH <%s> { <%s> a <http://www.w3.org/ns/prov#Activity> ;
                    <http://www.w3.org/ns/prov#used> <%s> ;
                    <http://www.w3.org/ns/prov#wasAssociatedWith> <%s> ;
                    <http://www.w3.org/ns/prov#endedAtTime> "%s"^^<http://www.w3.org/2001/XMLSchema#dateTime> ;
                    <https://w3id.org/projecta/ontology/belongsToProject> <%s> ;
                    <http://www.w3.org/2000/01/rdf-schema#label> "candidate-validation" . }
                }
                WHERE { GRAPH <%s> { <%s> a <%sCandidate> ; <%scandidateStatus> <%sextracted> . } }
                """
                        .formatted(
                                router.route(project, GraphRole.CANDIDATES),
                                candidate,
                                PROJECTA,
                                PROJECTA,
                                router.route(project, GraphRole.CANDIDATES),
                                candidate,
                                PROJECTA,
                                PROJECTA,
                                router.route(project, GraphRole.PROVENANCE),
                                activity,
                                candidate,
                                "https://w3id.org/projecta/data/project/" + project.value() + "/person/" + actorId,
                                OffsetDateTime.now(),
                                projectIri,
                                router.route(project, GraphRole.CANDIDATES),
                                candidate,
                                PROJECTA,
                                PROJECTA,
                                PROJECTA));
    }

    /** Returns the finite current-knowledge view, optionally restricted to an allowlisted type. */
    public List<Map<String, String>> current(ProjectId project, String type) {
        if (type != null && !type.equals("Requirement"))
            throw new IllegalArgumentException("knowledge-item type is not allowlisted");
        var filter = type == null ? "" : " ; a <" + PROJECTA + type + ">";
        return rows(gateway.select("SELECT ?item ?label ?validFrom WHERE { GRAPH <"
                + router.route(project, GraphRole.ASSERTED) + "> { ?item a <" + PROJECTA + "KnowledgeItem>" + filter
                + " ; <http://www.w3.org/2000/01/rdf-schema#label> ?label ; <" + PROJECTA
                + "validFrom> ?validFrom . } }"));
    }

    /** Returns ordered reviewer decisions that used the specified project-scoped candidate. */
    public List<Map<String, String>> history(ProjectId project, String candidateId) {
        return rows(gateway.select("SELECT ?activity ?decision ?reviewer ?endedAt WHERE { GRAPH <"
                + router.route(project, GraphRole.PROVENANCE) + "> { ?activity <" + PROV + "used> <"
                + candidate(project, candidateId) + "> ; <" + PROJECTA + "reviewDecision> ?decision ; <" + PROV
                + "wasAssociatedWith> ?reviewer ; <" + PROV + "endedAtTime> ?endedAt . } } ORDER BY ?endedAt"));
    }

    /** Returns the asserted-item-to-candidate-to-exact-source reviewer evidence chain. */
    public List<Map<String, String>> evidence(ProjectId project, String itemId) {
        var item = "https://w3id.org/projecta/data/project/" + project.value() + "/requirement/" + itemId;
        return rows(gateway.select(
                "SELECT ?candidate ?source ?note ?rawText ?sourceText ?startOffset ?endOffset ?author ?reviewer WHERE { GRAPH <"
                        + router.route(project, GraphRole.ASSERTED)
                        + "> { <" + item + "> <" + PROV + "wasDerivedFrom> ?candidate ; <" + PROV
                        + "wasAttributedTo> ?reviewer . } GRAPH <" + router.route(project, GraphRole.CANDIDATES)
                        + "> { ?candidate <" + PROV + "wasDerivedFrom> ?source . } GRAPH <"
                        + router.route(project, GraphRole.SOURCES) + "> { ?source <" + PROJECTA
                        + "isItemOf> ?note ; <" + PROJECTA + "contentText> ?sourceText ; <" + PROJECTA
                        + "evidenceStartOffset> ?startOffset ; <" + PROJECTA + "evidenceEndOffset> ?endOffset . ?note <"
                        + PROJECTA + "rawText> ?rawText ; <" + PROJECTA + "authoredBy> ?author . } }"));
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
