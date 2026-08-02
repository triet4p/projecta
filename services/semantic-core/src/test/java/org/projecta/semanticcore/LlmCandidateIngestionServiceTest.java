package org.projecta.semanticcore;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.net.URI;
import java.net.http.HttpClient;
import java.util.List;
import org.apache.jena.rdf.model.ModelFactory;
import org.apache.jena.riot.Lang;
import org.apache.jena.riot.RDFParser;
import org.junit.jupiter.api.Test;

class LlmCandidateIngestionServiceTest {
    @Test
    void resolvesProgressClaimUsingItsCanonicalTypeRoute() {
        class TrustedGateway extends FusekiGateway {
            TrustedGateway() {
                super(HttpClient.newHttpClient(), URI.create("http://semantic-store.invalid/projecta"));
            }

            @Override
            public boolean ask(String query) {
                return query.contains("/progressclaim/claim-01>");
            }
        }
        var service = new LlmCandidateIngestionService(
                new TrustedGateway(), new GraphIriRouter(), null);

        assertEquals(
                "https://w3id.org/projecta/data/project/demo/progressclaim/claim-01",
                service.resolveEntityIri(new ProjectId("demo"), "ProgressClaim--claim-01"));
    }

    @Test
    void parsesReplayNoteFromStandardsCompliantSparqlJson() {
        var response = """
                {
                  "head" : { "vars" : [ "note" ] },
                  "results" : {
                    "bindings" : [ {
                      "note" : {
                        "type" : "uri",
                        "value" : "https://w3id.org/projecta/data/project/demo/note/note-1"
                      }
                    } ]
                  }
                }
                """;

        assertEquals(
                "https://w3id.org/projecta/data/project/demo/note/note-1",
                LlmCandidateIngestionService.replayedNote(response));
    }

    @Test
    void rejectsReplayResponseWithoutExactlyOneNoteBinding() {
        assertThrows(
                IllegalStateException.class,
                () -> LlmCandidateIngestionService.replayedNote("{\"results\":{\"bindings\":[]}}"));
    }

    @Test
    void rejectsUnsupportedEntityTypeBeforeMutation() {
        var service = new LlmCandidateIngestionService(
                null, new GraphIriRouter(), null);
        var request = new LlmCandidateIngestionService.IngestionRequest(
                "A note", "replay", "v1", "p1", "m3.v1",
                List.of(new LlmCandidateIngestionService.EntityProposal("Unknown", "x", "A", 0, 1, 0.5)),
                List.of(), List.of());

        assertThrows(IllegalArgumentException.class, () -> service.ingest(new ProjectId("project"), "actor", "key", request));
    }

    @Test
    void validatesExactEntityEvidenceIndependentlyFromProposedLabel() {
        var request = new LlmCandidateIngestionService.IngestionRequest(
                "Confirm the shipping address before payment.",
                "replay",
                "v1",
                "p1",
                "m3.v1",
                List.of(new LlmCandidateIngestionService.EntityProposal(
                        "Requirement",
                        "shipping address confirmation",
                        "Confirm the shipping address before payment.",
                        0,
                        44,
                        0.9)),
                List.of(),
                List.of());

        assertDoesNotThrow(() -> LlmCandidateIngestionService.validate(request, request.rawText()));
    }

    @Test
    void rejectsEntityEvidenceTextThatDoesNotMatchItsSourceSpan() {
        var request = new LlmCandidateIngestionService.IngestionRequest(
                "Confirm the shipping address before payment.",
                "replay",
                "v1",
                "p1",
                "m3.v1",
                List.of(new LlmCandidateIngestionService.EntityProposal(
                        "Requirement", "shipping address confirmation", "wrong", 0, 44, 0.9)),
                List.of(),
                List.of());

        assertThrows(
                IllegalArgumentException.class,
                () -> LlmCandidateIngestionService.validate(request, request.rawText()));
    }

    @Test
    void emitsParseableSourceCandidateAndProvenanceTurtleForEntityEvidence() {
        var raw = "Confirm the shipping address before payment.";
        var request = new LlmCandidateIngestionService.IngestionRequest(
                raw,
                "replay",
                "v1",
                "p1",
                "m3.v1",
                List.of(new LlmCandidateIngestionService.EntityProposal(
                        "Requirement", "shipping address confirmation", raw, 0, 44, 0.9)),
                List.of(),
                List.of());
        var project = new ProjectId("project");
        var projectIri = "https://w3id.org/projecta/data/project/project";
        var note = projectIri + "/note/note-1";
        var turtle = LlmCandidateIngestionService.sourceTriples(
                project, "actor", note, projectIri, raw, request, "2026-08-03T00:00:00Z");
        var service = new LlmCandidateIngestionService(null, new GraphIriRouter(), null);
        var candidates = service.candidateTriples(
                project, note, projectIri, request, "2026-08-03T00:00:00Z");
        var provenance = LlmCandidateIngestionService.provenanceTriples(
                project,
                "actor",
                note,
                projectIri,
                projectIri + "/capture-idempotency/key",
                "fingerprint",
                "attempt",
                request,
                "2026-08-03T00:00:00Z");

        assertDoesNotThrow(() -> RDFParser.fromString(turtle, Lang.TURTLE)
                .parse(ModelFactory.createDefaultModel()));
        assertDoesNotThrow(() -> RDFParser.fromString(candidates, Lang.TURTLE)
                .parse(ModelFactory.createDefaultModel()));
        assertDoesNotThrow(() -> RDFParser.fromString(provenance, Lang.TURTLE)
                .parse(ModelFactory.createDefaultModel()));
    }
}
