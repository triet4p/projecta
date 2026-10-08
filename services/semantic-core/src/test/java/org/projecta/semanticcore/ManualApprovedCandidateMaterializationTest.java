package org.projecta.semanticcore;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.net.URI;
import java.net.http.HttpClient;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.LocalDate;
import java.util.HexFormat;
import java.util.List;
import org.apache.jena.query.Dataset;
import org.apache.jena.query.DatasetFactory;
import org.apache.jena.query.QueryExecutionFactory;
import org.apache.jena.query.QueryFactory;
import org.apache.jena.query.ResultSetFormatter;
import org.apache.jena.rdf.model.Model;
import org.apache.jena.rdf.model.ModelFactory;
import org.apache.jena.rdf.model.ResourceFactory;
import org.apache.jena.update.UpdateExecutionFactory;
import org.apache.jena.update.UpdateFactory;
import org.apache.jena.vocabulary.RDF;
import org.apache.jena.vocabulary.RDFS;
import org.junit.jupiter.api.Test;

/**
 * S13-02 connected slice on the Core side: a real {@code QuickNoteCaptureService}
 * Note capture flows through the production {@code FusekiQueryService}
 * validation/source-context path, the test-only {@code ManualApprovedReviewBinding}
 * applies the human-approval confirmed transition to that same captured row,
 * and the real {@code ApprovedAssertionMaterializationService} transacts the
 * asserted materialization only under {@code enabledForTest()}.
 *
 * <p>No RDF row is hand-seeded: the candidate under test is the row the capture
 * service itself persisted (extracted), promoted to validated by the query
 * service, then to confirmed by the test-only binding. No repository fixture
 * file is read; the review binding under test is built from fixed
 * receipt/evidence digests and the real source version resolved from the
 * captured Note text, mirroring the Python approval-side plan math.
 * Production stays locked: the disabled authorization fails closed with zero
 * asserted writes, and this test never wires the materializer into
 * {@code SemanticCoreApplication}.
 */
class ManualApprovedCandidateMaterializationTest {
    private static final String PROJECT = "project-alpha";
    private static final String SOURCE = "sv_abababababababababababababababababababababababababababababababab";
    private static final String RECEIPT = "sha256:1111111111111111111111111111111111111111111111111111111111111111";
    private static final String EVIDENCE = "sha256:2222222222222222222222222222222222222222222222222222222222222222";
    private static final String CANDIDATE = "https://w3id.org/projecta/data/project/project-alpha/candidate/note-1-1";
    private static final String ASSERTED =
            "https://w3id.org/projecta/data/project/project-alpha/requirement/req-manual-1";
    private static final String REVIEWER = "https://w3id.org/projecta/data/project/project-alpha/person/reviewer-1";
    private static final String ACTIVITY =
            "https://w3id.org/projecta/data/project/project-alpha/activity/materialize/manual-1";

    @Test
    void pythonPlanDigestMatchesJavaPlanDigest() {
        var plan = plan("parity-key-1", "Parity assertion label");

        assertEquals("sha256:529948d4c8a5d7efb4df2416d2a7b9b15e9e918a367443871cb9593851a223d9", plan.bodyDigest());
        assertEquals(
                "projecta-approved-candidate/v1|candidateRevision=1|sourceVersionId=" + SOURCE
                        + "|sourceVersionRevision=1|reviewReceiptDigest=" + RECEIPT
                        + "|evidenceDigest=" + EVIDENCE
                        + "|constrainedRelationContractVersion=manual-entity-capture.v1"
                        + "|evidenceSelectionVersion=text-anchor.v1",
                ApprovedAssertionPlan.metadataComment(plan.candidates().getFirst()));
    }

    @Test
    void capturedNoteConfirmsThroughTestBindingAndMaterializesOnlyUnderTestOptIn() throws Exception {
        // Connected path, all inside this isolated dataset: the real capture
        // service persists the Note row, the production query service promotes
        // it to validated, the test-only binding applies the human-approval
        // confirmed transition to that same row, and the real materializer
        // transacts the asserted write only under the test opt-in.
        var dataset = DatasetFactory.createTxnMem();
        var router = new GraphIriRouter();
        var project = new ProjectId(PROJECT);
        var gateway = new InDatasetGateway(dataset);
        var capture = new QuickNoteCaptureService(
                gateway,
                router,
                (candidateProject, sources, candidates, provenance) -> new CandidateValidationResult(true, List.of()));
        var rawText = "Plan \uD83D\uDE80 rollout";
        var captured = capture.capture(
                project,
                "reviewer-1",
                "manual-note-1",
                new QuickNoteCaptureService.CaptureRequest(
                        "Planning", rawText, List.of(new QuickNoteCaptureService.Segment("task", 0, 14, rawText))));
        var candidateId = captured.candidates().getFirst().id();
        var candidateIri = "https://w3id.org/projecta/data/project/" + PROJECT + "/candidate/" + candidateId;

        var queries = new FusekiQueryService(gateway, router, null);
        // Capture-time SHACL is accepted by the capture validator above; the
        // promotion here is the production extracted→validated transition.
        queries.markValidated(project, candidateId, "reviewer-1");
        var sourceContext = queries.manualCaptureSourceContext(project, candidateId);
        assertEquals("validated", sourceContext.get("candidateStatus"));
        assertEquals(rawText, sourceContext.get("evidenceText"));

        // Approval-side binding: the real source version for the captured Note
        // text (same derivation as the Python SourceVersion primitive) plus the
        // persisted confirm receipt digest recorded for this candidate.
        var sourceVersionId = "sv_5d00d380821b27a7dbdfae90a345c2c2bd72e9f1d6ac044408fb5edda2d6c164";
        var receiptDigest = sha256Hex("s13-02-manual-approval:" + candidateIri);
        var evidenceDigest = sha256Hex(rawText);
        var candidate = new ApprovedAssertionPlan.ApprovedCandidate(
                PROJECT,
                candidateIri,
                1,
                sourceVersionId,
                1,
                receiptDigest,
                evidenceDigest,
                "0.3.0",
                "manual-entity-capture.v1",
                "text-anchor.v1",
                ASSERTED,
                REVIEWER,
                rawText,
                LocalDate.of(2026, 9, 27));
        var plan = new ApprovedAssertionPlan(
                PROJECT,
                sourceVersionId,
                1,
                List.of(candidate),
                "0.3.0",
                "manual-entity-capture.v1",
                "text-anchor.v1",
                ApprovedAssertionMaterializationService.graphRevision(dataset.getNamedModel(
                        router.route(project, GraphRole.ASSERTED).toString())),
                ACTIVITY,
                "manual-plan-1");
        var bindingComment = ApprovedAssertionPlan.metadataComment(candidate);

        new ManualApprovedReviewBinding(dataset, router)
                .applyConfirmedBinding(project, candidateIri, bindingComment, "0.3.0");

        var disabled = service(dataset, router, MaterializationAuthorization.disabled(), () -> {});
        assertThrows(IllegalStateException.class, () -> disabled.materialize(plan));
        assertEquals(
                0,
                dataset.getNamedModel(router.route(project, GraphRole.ASSERTED).toString())
                        .size());

        var result = service(dataset, router, MaterializationAuthorization.enabledForTest(), () -> {})
                .materialize(plan);
        assertEquals("accepted", result.outcome());
        assertEquals(plan.bodyDigest(), result.bodyDigest());
        assertTrue(result.materializationRevision().startsWith("sha256:"));
        // The asserted graph now holds the approved item derived from the real Note.
        assertTrue(
                dataset.getNamedModel(router.route(project, GraphRole.ASSERTED).toString())
                        .containsResource(ResourceFactory.createResource(ASSERTED)));
        assertEquals(
                "asserted",
                dataset.getNamedModel(
                                router.route(project, GraphRole.CANDIDATES).toString())
                        .getResource(candidateIri)
                        .getProperty(
                                ResourceFactory.createProperty("https://w3id.org/projecta/ontology/candidateStatus"))
                        .getResource()
                        .getLocalName());
        // Exact replay is idempotent: no duplicate asserted writes.
        var replay = service(dataset, router, MaterializationAuthorization.enabledForTest(), () -> {})
                .materialize(plan);
        assertEquals("replayed", replay.outcome());
        assertEquals(result.materializationRevision(), replay.materializationRevision());
    }

    @Test
    void confirmedManualCandidateWithSafeBindingMaterializesOnlyUnderTestOptIn() {
        var dataset = DatasetFactory.createTxnMem();
        var router = new GraphIriRouter();
        var plan = seed(dataset, router, "manual-key-1", "Parity assertion label");
        var disabled = service(dataset, router, MaterializationAuthorization.disabled(), () -> {});

        assertThrows(IllegalStateException.class, () -> disabled.materialize(plan));
        assertEquals(
                0,
                dataset.getNamedModel(router.route(new ProjectId(PROJECT), GraphRole.ASSERTED)
                                .toString())
                        .size());

        var result = service(dataset, router, MaterializationAuthorization.enabledForTest(), () -> {})
                .materialize(plan);

        assertEquals("accepted", result.outcome());
        assertEquals(plan.bodyDigest(), result.bodyDigest());
        assertTrue(result.materializationRevision().startsWith("sha256:"));
        assertTrue(dataset.getNamedModel(router.route(new ProjectId(PROJECT), GraphRole.ASSERTED)
                                .toString())
                        .size()
                > 0);
        assertEquals(
                "asserted",
                dataset.getNamedModel(router.route(new ProjectId(PROJECT), GraphRole.CANDIDATES)
                                .toString())
                        .getResource(CANDIDATE)
                        .getProperty(
                                ResourceFactory.createProperty("https://w3id.org/projecta/ontology/candidateStatus"))
                        .getResource()
                        .getLocalName());
    }

    @Test
    void mismatchedBindingOrUnconfirmedCandidateCannotMaterialize() {
        var tamperedDataset = DatasetFactory.createTxnMem();
        var tamperedRouter = new GraphIriRouter();
        var tampered = seed(tamperedDataset, tamperedRouter, "manual-key-tampered", "Parity assertion label");
        var tamperedCandidates = tamperedDataset.getNamedModel(tamperedRouter
                .route(new ProjectId(PROJECT), GraphRole.CANDIDATES)
                .toString());
        tamperedCandidates.removeAll(tamperedCandidates.getResource(CANDIDATE), RDFS.comment, null);
        tamperedCandidates
                .getResource(CANDIDATE)
                .addProperty(RDFS.comment, "projecta-approved-candidate/v1|candidateRevision=9");
        assertThrows(
                IllegalArgumentException.class,
                () -> service(tamperedDataset, tamperedRouter, MaterializationAuthorization.enabledForTest(), () -> {})
                        .materialize(tampered));
        assertEquals(
                0,
                tamperedDataset
                        .getNamedModel(tamperedRouter
                                .route(new ProjectId(PROJECT), GraphRole.ASSERTED)
                                .toString())
                        .size());

        var unconfirmedDataset = DatasetFactory.createTxnMem();
        var unconfirmedRouter = new GraphIriRouter();
        var unconfirmed = seed(unconfirmedDataset, unconfirmedRouter, "manual-key-unconfirmed", "Parity label");
        var unconfirmedCandidates = unconfirmedDataset.getNamedModel(unconfirmedRouter
                .route(new ProjectId(PROJECT), GraphRole.CANDIDATES)
                .toString());
        var status = ResourceFactory.createProperty("https://w3id.org/projecta/ontology/candidateStatus");
        unconfirmedCandidates.removeAll(unconfirmedCandidates.getResource(CANDIDATE), status, null);
        unconfirmedCandidates
                .getResource(CANDIDATE)
                .addProperty(status, ResourceFactory.createResource("https://w3id.org/projecta/ontology/extracted"));
        assertThrows(
                IllegalStateException.class,
                () -> service(
                                unconfirmedDataset,
                                unconfirmedRouter,
                                MaterializationAuthorization.enabledForTest(),
                                () -> {})
                        .materialize(unconfirmed));
        assertEquals(
                0,
                unconfirmedDataset
                        .getNamedModel(unconfirmedRouter
                                .route(new ProjectId(PROJECT), GraphRole.ASSERTED)
                                .toString())
                        .size());
    }

    private static ApprovedAssertionMaterializationService service(
            Dataset dataset, GraphIriRouter router, MaterializationAuthorization authorization, Runnable hook) {
        var shapes = ModelFactory.createDefaultModel();
        return new ApprovedAssertionMaterializationService(
                dataset, router, new CandidateValidationService(dataset, router, shapes), shapes, authorization, hook);
    }

    private static ApprovedAssertionPlan seed(Dataset dataset, GraphIriRouter router, String key, String label) {
        var plan = plan(key, label);
        seedFixture(
                dataset,
                router,
                plan,
                ApprovedAssertionPlan.metadataComment(plan.candidates().getFirst()));
        return plan;
    }

    private static void seedFixture(
            Dataset dataset, GraphIriRouter router, ApprovedAssertionPlan plan, String bindingComment) {
        var seeded = plan.candidates().getFirst();
        var candidates = dataset.getNamedModel(router.route(new ProjectId(seeded.project()), GraphRole.CANDIDATES)
                .toString());
        var candidate = candidates.createResource(seeded.candidateIri());
        var project = ResourceFactory.createResource("https://w3id.org/projecta/data/project/" + seeded.project());
        candidate.addProperty(RDF.type, ResourceFactory.createResource("https://w3id.org/projecta/ontology/Candidate"));
        candidate.addProperty(
                ResourceFactory.createProperty("https://w3id.org/projecta/ontology/belongsToProject"), project);
        candidate.addProperty(
                ResourceFactory.createProperty("https://w3id.org/projecta/ontology/candidateStatus"),
                ResourceFactory.createResource("https://w3id.org/projecta/ontology/confirmed"));
        candidate.addLiteral(
                ResourceFactory.createProperty("https://w3id.org/projecta/ontology/proposedOntologyVersion"),
                seeded.ontologyVersion());
        candidate.addProperty(RDFS.comment, bindingComment);
    }

    private static ApprovedAssertionPlan plan(String key, String label) {
        var candidate = new ApprovedAssertionPlan.ApprovedCandidate(
                PROJECT,
                CANDIDATE,
                1,
                SOURCE,
                1,
                RECEIPT,
                EVIDENCE,
                "0.3.0",
                "manual-entity-capture.v1",
                "text-anchor.v1",
                ASSERTED,
                REVIEWER,
                label,
                LocalDate.of(2026, 9, 27));
        return new ApprovedAssertionPlan(
                PROJECT,
                SOURCE,
                1,
                List.of(candidate),
                "0.3.0",
                "manual-entity-capture.v1",
                "text-anchor.v1",
                ApprovedAssertionMaterializationService.graphRevision(ModelFactory.createDefaultModel()),
                ACTIVITY,
                key);
    }

    private static String sha256Hex(String value) throws Exception {
        return "sha256:"
                + HexFormat.of()
                        .formatHex(MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8)));
    }

    /** Executes service-authored SPARQL against the test dataset instead of a remote Fuseki. */
    private static final class InDatasetGateway extends FusekiGateway {
        private final Dataset dataset;

        private InDatasetGateway(Dataset dataset) {
            super(HttpClient.newHttpClient(), URI.create("http://localhost:1/projecta"));
            this.dataset = dataset;
        }

        @Override
        public void update(String update) {
            UpdateExecutionFactory.create(UpdateFactory.create(update), dataset).execute();
        }

        @Override
        public boolean ask(String query) {
            try (var execution = QueryExecutionFactory.create(QueryFactory.create(query), dataset)) {
                return execution.execAsk();
            }
        }

        @Override
        public String select(String query) {
            try (var execution = QueryExecutionFactory.create(QueryFactory.create(query), dataset)) {
                var out = new java.io.ByteArrayOutputStream();
                ResultSetFormatter.outputAsJSON(out, execution.execSelect());
                return out.toString(StandardCharsets.UTF_8);
            }
        }

        @Override
        public Model graph(String graphIri) {
            var model = ModelFactory.createDefaultModel();
            model.add(dataset.getNamedModel(graphIri));
            return model;
        }
    }
}
