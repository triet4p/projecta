package org.projecta.semanticcore;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.io.ByteArrayInputStream;
import java.net.URI;
import java.net.http.HttpClient;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import org.apache.jena.fuseki.main.FusekiServer;
import org.apache.jena.query.DatasetFactory;
import org.junit.jupiter.api.Test;

class PortableProjectImportServiceTest {
    private static final String PROJECTA = "https://w3id.org/projecta/ontology/";
    private static final String PROJECT_BASE = "https://w3id.org/projecta/data/project/";
    private static final String PROJECT_NAME = "Imported Project";

    @Test
    void validatesM4StateAndAppliesThenRollsBackFiveGraphPackage() {
        var router = new GraphIriRouter();
        var dataset = DatasetFactory.createTxnMem();
        var server = FusekiServer.create()
                .loopback(true)
                .port(0)
                .add("/projecta", dataset)
                .build();
        try {
            server.start();
            var gateway = new FusekiGateway(
                    HttpClient.newHttpClient(), URI.create("http://127.0.0.1:" + server.getPort() + "/projecta"));
            var validator = new RemoteCandidateValidationService(gateway, router, Path.of("../../ontology/shapes"));
            var importer = new PortableProjectImportService(gateway, router, validator);

            var plainProject = new ProjectId("portable-import-rollback");
            var plainPackage = trig(router, plainProject, projectIdentity(plainProject), "");
            var preview = importer.validate(plainProject, "Placeholder", PROJECT_NAME, input(plainPackage));
            assertEquals("absent", preview.get("destinationState"));
            importer.apply(plainProject, "Placeholder", PROJECT_NAME, false, input(plainPackage));
            assertEquals(
                    "populated",
                    importer.validate(plainProject, "Placeholder", PROJECT_NAME, input(plainPackage))
                            .get("destinationState"));
            importer.rollback(plainProject, "Placeholder", PROJECT_NAME, false, input(plainPackage));
            assertEquals(
                    "absent",
                    importer.validate(plainProject, "Placeholder", PROJECT_NAME, input(plainPackage))
                            .get("destinationState"));

            var m4Project = new ProjectId("portable-import-m4");
            var task = PROJECT_BASE + m4Project.value() + "/task/t1";
            var requirement = PROJECT_BASE + m4Project.value() + "/requirement/r1";
            var asserted = projectIdentity(m4Project)
                    + "<" + task + "> a <" + PROJECTA + "Task> .\n"
                    + "<" + requirement + "> a <" + PROJECTA + "Requirement> .\n";
            var validInference = inference(m4Project, task, requirement, "source-r1", true);
            var m4Package = trig(router, m4Project, asserted, validInference);
            var validPreview = importer.validate(m4Project, "Placeholder", PROJECT_NAME, input(m4Package));
            assertEquals("absent", validPreview.get("destinationState"));

            var unresolvedProject = new ProjectId("portable-import-unresolved");
            var unresolvedTask = PROJECT_BASE + unresolvedProject.value() + "/task/t1";
            var unresolvedRequirement = PROJECT_BASE + unresolvedProject.value() + "/requirement/r1";
            var unresolvedArchive = trig(
                    router,
                    unresolvedProject,
                    projectIdentity(unresolvedProject)
                            + "<" + unresolvedTask + "> a <" + PROJECTA + "Task> .\n"
                            + "<" + unresolvedRequirement + "> a <" + PROJECTA + "Requirement> .\n",
                    inference(unresolvedProject, unresolvedTask, unresolvedRequirement, "source-r1", false));
            assertThrows(
                    IllegalArgumentException.class,
                    () -> importer.validate(unresolvedProject, "Placeholder", PROJECT_NAME, input(unresolvedArchive)));

            var malformedProject = new ProjectId("portable-import-shacl");
            var malformedTask = PROJECT_BASE + malformedProject.value() + "/task/t1";
            var malformedRequirement = PROJECT_BASE + malformedProject.value() + "/requirement/r1";
            var malformedInference = inference(malformedProject, malformedTask, malformedRequirement, "source-r1", true)
                    .replace("<" + PROJECTA + "ruleVersion> \"1\" ;", "");
            var malformedArchive = trig(
                    router,
                    malformedProject,
                    projectIdentity(malformedProject)
                            + "<" + malformedTask + "> a <" + PROJECTA + "Task> .\n"
                            + "<" + malformedRequirement + "> a <" + PROJECTA + "Requirement> .\n",
                    malformedInference);
            assertThrows(
                    IllegalArgumentException.class,
                    () -> importer.validate(malformedProject, "Placeholder", PROJECT_NAME, input(malformedArchive)));
            var secretProject = new ProjectId("portable-import-secret");
            var secretSourceGraph = "<" + router.route(secretProject, GraphRole.SOURCES) + "> {\n}\n";
            var secretPackage = trig(router, secretProject, projectIdentity(secretProject), "")
                    .replace(
                            secretSourceGraph,
                            "<" + router.route(secretProject, GraphRole.SOURCES) + "> {\n"
                                    + "  <" + PROJECT_BASE + secretProject.value() + "/source/s1> <"
                                    + PROJECTA + "secretReference> \"excluded\" .\n"
                                    + "}\n");
            assertThrows(
                    IllegalArgumentException.class,
                    () -> importer.validate(secretProject, "Placeholder", PROJECT_NAME, input(secretPackage)));
            var unexpectedGraph = PROJECT_BASE + secretProject.value() + "/extra";
            var alternateEmptyGraphPackage = trig(router, secretProject, projectIdentity(secretProject), "") + "GRAPH <"
                    + unexpectedGraph + "> { }\n";
            assertThrows(
                    IllegalArgumentException.class,
                    () -> importer.validate(
                            secretProject, "Placeholder", PROJECT_NAME, input(alternateEmptyGraphPackage)));
            var spacedEmptyGraphPackage = trig(router, secretProject, projectIdentity(secretProject), "") + "<"
                    + unexpectedGraph + "> # graph labels may span lines\n{ }\n";
            assertThrows(
                    IllegalArgumentException.class,
                    () -> importer.validate(
                            secretProject, "Placeholder", PROJECT_NAME, input(spacedEmptyGraphPackage)));
        } finally {
            server.stop();
            dataset.close();
        }
    }

    private static String projectIdentity(ProjectId project) {
        var iri = PROJECT_BASE + project.value();
        return "<" + iri + "> a <" + PROJECTA + "Project> ; <" + PROJECTA + "name> \"" + PROJECT_NAME + "\" .\n";
    }

    private static String inference(
            ProjectId project, String task, String requirement, String revision, boolean resolved) {
        var base = PROJECT_BASE + project.value();
        var assertionReference = resolved ? task : base + "/task/missing";
        return "<" + base + "/inferred/snapshot-m4-v1> a <" + PROJECTA + "InferenceSnapshot> ;\n"
                + "  <" + PROJECTA + "belongsToProject> <" + base + "> ;\n"
                + "  <" + PROJECTA + "sourceRevision> \"" + revision + "\" ;\n"
                + "  <" + PROJECTA + "ruleVersion> \"m4.v1\" .\n"
                + "<" + base + "/inferred/blocker-t1> a <" + PROJECTA + "UnresolvedBlocker> ;\n"
                + "  <" + PROJECTA + "belongsToProject> <" + base + "> ;\n"
                + "  <" + PROJECTA + "aboutTask> <" + task + "> ;\n"
                + "  <" + PROJECTA + "derivedFromAssertion> <" + assertionReference + ">, <" + requirement + "> ;\n"
                + "  <" + PROJECTA + "ruleIdentifier> \"m4.unresolved-dependency\" ;\n"
                + "  <" + PROJECTA + "ruleVersion> \"1\" ;\n"
                + "  <" + PROJECTA + "sourceRevision> \"" + revision + "\" .\n";
    }

    private static String trig(GraphIriRouter router, ProjectId project, String asserted, String inferred) {
        return "<" + router.route(project, GraphRole.SOURCES) + "> {\n}\n"
                + "<" + router.route(project, GraphRole.CANDIDATES) + "> {\n}\n"
                + "<" + router.route(project, GraphRole.ASSERTED) + "> {\n" + asserted + "}\n"
                + "<" + router.route(project, GraphRole.INFERRED) + "> {\n" + inferred + "}\n"
                + "<" + router.route(project, GraphRole.PROVENANCE) + "> {\n}\n";
    }

    private static ByteArrayInputStream input(String trig) {
        return new ByteArrayInputStream(trig.getBytes(StandardCharsets.UTF_8));
    }
}
