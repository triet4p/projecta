# Modeling and Impact Checklist

Read this file after completing `semantic-commitment-interview.md` and before adding or changing ontology vocabulary.

## Choose the correct semantic artifact

### Class

Use a class when instances share durable domain meaning and the distinction supports queries, validation, or inference.

“Durable domain meaning” describes the semantic category, not an assumption that every instance or its membership exists forever. If an entity can leave the category without losing its identity, model and compare role/state/phase/relation alternatives explicitly.

Avoid a class when the concept is:

- Merely a display grouping.
- A workflow status value.
- A one-off named entity.
- Reliably represented by an existing class plus properties.

### Individual

Use an individual for a concrete entity or a governed vocabulary value. Decide whether a status should be an individual, SKOS concept, or application enum based on existing Projecta conventions.

Do not treat two external identities as the same `Person` solely because their labels match.

### Object property

Use an object property when both ends are resources with identity and lifecycle.

Check:

- Direction and readable inverse.
- Domain/range entailment.
- Whether it crosses project boundaries.
- Whether the relationship needs provenance or temporal metadata.
- Whether inverse, symmetric, transitive, functional, or inverse-functional semantics are universally true.

Do not declare strong OWL characteristics merely because they hold in the current sample data.

### Datatype property

Use a datatype property for literal values. Specify datatype, normalization, units, language behavior, and cardinality in SHACL where required.

Do not encode a resource with provenance or identity as a string.

### SHACL shape

Use SHACL for application-level closed-world validity:

- Required fields.
- Cardinality.
- Datatype/class constraints.
- Allowed status transitions.
- Cross-entity or cross-project checks.
- Candidate evidence requirements.

Do not misuse OWL restrictions as input-form validation.

### Rule

Use a rule only for deterministic, explainable derivation. Give each rule an identifier, version, tests, dependency facts, and derivation provenance. Materialize output only in the inferred graph.

Do not use a rule to hide missing human confirmation.

## Naming and definition

- Keep released IRIs stable.
- Follow the repository namespace and naming convention.
- Give every public term an unambiguous definition.
- Add labels in the languages required by the project convention.
- Define what is included and excluded.
- Avoid synonyms as parallel properties; use labels or mappings.
- Reuse PROV-O for provenance rather than creating Projecta duplicates.

If the base IRI has not been approved, do not invent a permanent-looking production IRI.

## Open-world and closed-world review

Ask:

- Does absence mean false, unknown, or invalid?
- Is the statement an OWL entailment or a SHACL validation rule?
- Could domain/range infer an unintended type?
- Could a cardinality axiom imply identity rather than report invalid data?
- Does disjointness reflect domain truth or only the current application UI?

## Knowledge-status review

For every generated or stored statement, identify:

- Source/evidence graph.
- Candidate graph.
- Asserted graph.
- Inferred graph.
- Provenance graph.
- Verification state.
- Actor/model/rule responsible.

No similarity score or LLM confidence establishes truth.

## Temporal and lifecycle review

Ask whether the change affects:

- `validFrom`, `validTo`, or `recordedAt`.
- Supersession, retraction, or deprecation.
- Historical competency queries.
- Inference invalidation/rebuild.
- Projection or search-index rebuild.

Never overwrite semantic history merely to simplify the current view.

## Isolation and authorization review

Verify:

- Every project entity has project context as required.
- Relations are same-project unless explicitly designed otherwise.
- Named graph routing cannot mix tenant/project/status.
- Named graphs do not replace authorization.
- Source visibility is not broader than fact visibility.

## Compatibility impact matrix

Inspect all applicable consumers:

| Consumer | Questions |
|---|---|
| Ontology modules | Import, hierarchy, inverse, domain/range impact? |
| SHACL | New valid or invalid data? |
| Rules | New derivations or invalidation conditions? |
| SPARQL queries | Result shape or query semantics changed? |
| Existing RDF data | Migration, backfill, or deprecation needed? |
| Semantic Core | Routing or lifecycle code affected? |
| Python contracts | Enum/schema/tool contract affected? |
| Connectors | Mapping behavior affected? |
| UI/projections | Display, filtering, or rebuild affected? |
| Permissions | Project/tenant/source visibility affected? |
| Evaluation | Extraction labels or expected results affected? |

State “no impact found” only after searching the repository.

## Minimum test matrix

For a new or changed term, include as applicable:

- Positive example.
- Boundary example.
- Invalid example.
- Competency query.
- Existing-query regression.
- SHACL conformance and intended violation.
- Rule fires and rule does not fire.
- Provenance completeness.
- Cross-project rejection.
- Migration before/after fixture.
