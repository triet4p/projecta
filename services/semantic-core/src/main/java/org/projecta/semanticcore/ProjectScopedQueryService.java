package org.projecta.semanticcore;

import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Optional;
import org.apache.jena.query.Dataset;
import org.apache.jena.query.ReadWrite;
import org.apache.jena.rdf.model.Resource;
import org.apache.jena.rdf.model.ResourceFactory;
import org.apache.jena.vocabulary.RDF;
import org.apache.jena.vocabulary.RDFS;

/** Provides the finite, project-bound read views defined by the Semantic Core API contract. */
public final class ProjectScopedQueryService {
    private static final String PROJECTA = "https://w3id.org/projecta/ontology/";
    private static final String PROV = "http://www.w3.org/ns/prov#";
    private final Dataset dataset;
    private final GraphIriRouter router;

    public ProjectScopedQueryService(Dataset dataset, GraphIriRouter router) {
        this.dataset = dataset;
        this.router = router;
    }

    public List<KnowledgeItem> currentKnowledgeItems(ProjectId projectId, Optional<String> type) {
        if (type.isPresent() && !type.get().equals("Requirement")) {
            throw new IllegalArgumentException("knowledge-item type is not allowlisted");
        }
        dataset.begin(ReadWrite.READ);
        try {
            var asserted = dataset.getNamedModel(
                    router.route(projectId, GraphRole.ASSERTED).toString());
            var items = asserted.listResourcesWithProperty(RDF.type, resource(PROJECTA + "KnowledgeItem"));
            return items.filterKeep(item ->
                            type.isEmpty() || asserted.contains(item, RDF.type, resource(PROJECTA + type.get())))
                    .mapWith(item -> knowledgeItem(asserted, item))
                    .toList();
        } finally {
            dataset.end();
        }
    }

    public CandidateHistory candidateHistory(ProjectId projectId, String candidateId) {
        dataset.begin(ReadWrite.READ);
        try {
            var candidates = dataset.getNamedModel(
                    router.route(projectId, GraphRole.CANDIDATES).toString());
            var candidate = findResource(candidates, candidateId);
            var status = candidates.getProperty(candidate, property(PROJECTA + "candidateStatus"));
            var provenance = dataset.getNamedModel(
                    router.route(projectId, GraphRole.PROVENANCE).toString());
            var activities = provenance
                    .listResourcesWithProperty(property(PROV + "used"), candidate)
                    .filterKeep(activity -> provenance.contains(activity, RDF.type, resource(PROV + "Activity")))
                    .mapWith(activity -> lifecycleActivity(provenance, activity))
                    .toList();
            return new CandidateHistory(candidateId, status.getResource().getLocalName(), activities);
        } finally {
            dataset.end();
        }
    }

    public Evidence evidence(ProjectId projectId, String itemId) {
        dataset.begin(ReadWrite.READ);
        try {
            var asserted = dataset.getNamedModel(
                    router.route(projectId, GraphRole.ASSERTED).toString());
            var item = findResource(asserted, itemId);
            var candidate = asserted.getProperty(item, property(PROV + "wasDerivedFrom"))
                    .getResource();
            var candidates = dataset.getNamedModel(
                    router.route(projectId, GraphRole.CANDIDATES).toString());
            if (!candidates.containsResource(candidate)) {
                throw new ResourceNotFoundException("knowledge-item evidence is outside the trusted project");
            }
            var source = candidates
                    .getProperty(candidate, property(PROV + "wasDerivedFrom"))
                    .getResource();
            var sources = dataset.getNamedModel(
                    router.route(projectId, GraphRole.SOURCES).toString());
            if (!sources.containsResource(source)) {
                throw new ResourceNotFoundException("knowledge-item evidence is outside the trusted project");
            }
            var reviewer = asserted.getProperty(item, property(PROV + "wasAttributedTo"))
                    .getResource();
            return new Evidence(itemId, localName(candidate), localName(source), localName(reviewer));
        } finally {
            dataset.end();
        }
    }

    private KnowledgeItem knowledgeItem(org.apache.jena.rdf.model.Model model, Resource item) {
        var type = item.listProperties(RDF.type)
                .mapWith(statement -> statement.getResource())
                .filterKeep(value -> !value.getURI().equals(PROJECTA + "KnowledgeItem"))
                .next();
        var label = model.getProperty(item, RDFS.label).getString();
        var validFrom =
                model.getProperty(item, property(PROJECTA + "validFrom")).getString();
        return new KnowledgeItem(localName(item), type.getLocalName(), label, LocalDate.parse(validFrom));
    }

    private LifecycleActivity lifecycleActivity(org.apache.jena.rdf.model.Model model, Resource activity) {
        var decision = model.getProperty(activity, property(PROJECTA + "reviewDecision"));
        var reviewer = model.getProperty(activity, property(PROV + "wasAssociatedWith"));
        var endedAt = model.getProperty(activity, property(PROV + "endedAtTime"));
        return new LifecycleActivity(
                localName(activity),
                decision == null ? null : decision.getResource().getLocalName(),
                reviewer == null ? null : localName(reviewer.getResource()),
                endedAt == null ? null : OffsetDateTime.parse(endedAt.getString()));
    }

    private Resource findResource(org.apache.jena.rdf.model.Model model, String id) {
        if (id == null || !id.matches("[a-z0-9][a-z0-9-]{0,62}")) {
            throw new IllegalArgumentException("resource ID must be a lowercase kebab-case identifier");
        }
        var resources = model.listSubjects()
                .filterKeep(resource -> id.equals(localName(resource)))
                .toList();
        if (resources.size() != 1) {
            throw new ResourceNotFoundException("resource is not visible in the trusted project");
        }
        return resources.getFirst();
    }

    private static String localName(Resource resource) {
        return resource.getLocalName();
    }

    private static Resource resource(String iri) {
        return ResourceFactory.createResource(iri);
    }

    private static org.apache.jena.rdf.model.Property property(String iri) {
        return ResourceFactory.createProperty(iri);
    }

    public record KnowledgeItem(String id, String type, String label, LocalDate validFrom) {}

    public record CandidateHistory(String candidateId, String currentStatus, List<LifecycleActivity> activities) {}

    public record LifecycleActivity(String id, String decision, String reviewerId, OffsetDateTime endedAt) {}

    public record Evidence(String itemId, String candidateId, String sourceId, String reviewerId) {}

    public static final class ResourceNotFoundException extends RuntimeException {
        public ResourceNotFoundException(String message) {
            super(message);
        }
    }
}
