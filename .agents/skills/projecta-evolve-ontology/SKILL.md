---
name: projecta-evolve-ontology
description: Propose, implement, review, and revise incremental Projecta ontology changes under human governance. Use for creating or changing ontology modules, RDF/OWL classes, object or datatype properties, controlled individuals, SHACL shapes, inference rules, competency questions, example graphs, ontology versions, deprecations, or migrations in the Projecta repository. Also use when assessing whether a domain concept belongs in the ontology. Produce reviewable local artifacts and validation evidence, but never treat agent output as approved production ontology.
---

# Evolve the Projecta Ontology

Develop the ontology incrementally from competency questions and governance needs. Treat every agent-authored change as a proposal until a human explicitly approves it.

## Establish Project Context

1. Locate the Projecta repository root.
2. Read repository instructions such as `AGENTS.md` when present.
3. Read `references/projecta-source-map.md`.
4. Read every project document marked mandatory for the requested operation. Read `docs/initialization/05-Ontology-Design.md` completely on every invocation.
5. Inspect current ontology, shapes, rules, examples, competency questions, migrations, tests, and pending working-tree changes before designing anything.

Stop and report the missing prerequisite if the Projecta initialization documents cannot be found. Do not reconstruct project governance from this skill alone.

## Select the Operation

Use the least expansive operation that satisfies the request:

- **Explore/propose:** Analyze a domain need and return a semantic proposal without changing ontology artifacts.
- **Draft implementation:** Edit version-controlled ontology artifacts and tests for human review.
- **Revise:** Apply reviewer feedback while preserving unresolved alternatives and provenance.
- **Prepare release:** Update versioning and migration artifacts only after explicit human approval of the semantic design.

Default to draft implementation when the user asks to create, add, change, fix, or remove ontology elements. Default to explore/propose when the request is exploratory or the base IRI, module boundary, or business meaning is materially ambiguous.

Never interpret silence, prior approval of this skill, or approval of a different change as approval of the current ontology change.

## Run the Change Workflow

### 1. Define the semantic need

Write:

- The business/use-case justification.
- One or more competency questions.
- Positive examples.
- Counterexamples or boundary cases.
- The project/governance requirement served.
- Explicit non-goals.

Reject ontology additions that serve neither a competency question nor a governance requirement.

### 2. Discover and reuse

Search for:

- An existing class, property, individual, shape, or rule with the intended meaning.
- Existing module and naming conventions.
- Existing external vocabulary already used by Projecta.
- Queries, fixtures, migrations, or projections affected by the change.

Prefer extending or reusing stable semantics over introducing near-duplicates. Do not merge identities using names alone and do not introduce `owl:sameAs` without strong, reviewed identity evidence.

### 3. Classify the artifact

Run two separate gates:

1. **Competency gate:** What project question becomes answerable, more precise, or governable?
2. **Semantic commitment gate:** What kind of thing must exist in the model for that answer to be valid?

Determine whether the concept is:

- A class.
- An individual or controlled vocabulary value.
- An object property.
- A datatype property.
- An assertion/relationship instance rather than TBox vocabulary.
- A SHACL constraint.
- A deterministic inference rule.
- Operational state that belongs in PostgreSQL rather than the ontology.
- Retrieval or UI projection data that must not become domain truth.

Before proposing a new or materially changed class or property:

1. Read `references/semantic-commitment-interview.md`.
2. Answer every mandatory question for that term.
3. Include the answers in the human review packet.
4. Keep the result `PROPOSAL_ONLY` if identity, lifecycle, superclass, relation arity, domain/range, or temporal/provenance semantics remain materially unresolved.

A class does not mean “something that exists forever.” Distinguish the stability of the vocabulary term from the lifecycle and class membership of its instances. If the same entity can stop being a member while retaining its identity, evaluate whether the concept is a role, phase, state, assignment, or time-qualified relation rather than an essential type.

Read `references/modeling-and-impact-checklist.md` after the interview and before adding or changing semantic vocabulary.

### 4. Design the smallest coherent change

Produce at least two alternatives when the semantic choice has meaningful trade-offs. Select one and explain why it best answers the competency questions.

Do not create a class or property merely because a noun or verb appears in source text. Every new term must pass both gates in step 3.

Define as applicable:

- Stable IRI and human-readable labels/definitions.
- Module ownership.
- Superclass/subproperty relationships.
- Domain and range, considering their entailment effects.
- Inverse, cardinality, disjointness, or property characteristics only when logically true.
- SHACL constraints for closed-world application validation.
- Provenance and verification-state requirements.
- Temporal validity and supersession behavior.
- Project/tenant boundary behavior.
- Backward compatibility and migration.

Do not silently settle an unresolved architecture decision such as the production base IRI or RDF-star versus reification. Propose the decision and keep committed production artifacts unchanged until a human selects it.

### 5. Implement a reviewable vertical change

When drafting implementation, update the complete minimum artifact set:

- Ontology Turtle module.
- SHACL shapes when application validity changes.
- Deterministic rules when derived behavior changes.
- Example RDF/TriG data.
- Competency SPARQL query and expected result.
- Negative validation fixture where a new constraint is introduced.
- Migration/deprecation artifact for incompatible changes.
- Version metadata or changelog when the repository convention requires it.

Use existing repository structure and commands. If the ontology tree does not yet exist, follow the structure in initialization documents and scaffold only the files needed for the requested vertical slice.

Keep source/evidence, candidate, asserted, inferred, and provenance graph semantics separate. Never write a candidate directly into asserted data.

### 6. Validate

Run every available relevant check:

- RDF/Turtle/TriG syntax parsing.
- Ontology consistency checks supported by the repository.
- SHACL conformance on positive fixtures.
- SHACL failure on intended negative fixtures.
- Competency query expected-result tests.
- Rule output and derivation tests.
- Cross-project and provenance completeness tests.
- Regression tests for existing competency questions.

If tooling is absent, say exactly which validations were not executable. Do not report conceptual inspection as a passing automated test.

### 7. Hand off for human review

End every change with the review packet defined in `references/review-packet.md`.

Set status to exactly one of:

- `PROPOSAL_ONLY`
- `PENDING_HUMAN_REVIEW`
- `HUMAN_APPROVED_PENDING_IMPLEMENTATION`
- `IMPLEMENTED_PENDING_RELEASE_APPROVAL`
- `BLOCKED`

Only use a status containing `HUMAN_APPROVED` when the human explicitly approved this exact semantic proposal.

## Enforce Hard Guardrails

- Do not publish, deploy, or mutate a remote/runtime ontology or RDF dataset without explicit authorization.
- Do not run data migration against shared or production data while drafting a change.
- Do not let an LLM create production predicates dynamically from source text.
- Do not bypass SHACL, Semantic Core, policy, project scope, or provenance requirements.
- Do not model retry counts, sync cursors, UI preferences, or transient agent state as domain ontology.
- Do not overwrite requirement or relation history; use temporal validity, supersession, retraction, or deprecation.
- Do not delete or reuse a released IRI. Deprecate it and provide migration guidance.
- Do not put inferred facts in asserted graphs or present them as human-confirmed.
- Preserve unrelated user changes in a dirty working tree.

## Interpret Removal Requests

Treat “remove” as a compatibility-sensitive operation:

1. Find all ontology, data, query, shape, rule, UI, and integration usages.
2. Prefer deprecation over physical deletion for released IRIs.
3. Define replacement semantics when applicable.
4. Supply a migration and rollback plan.
5. Require explicit human approval before destructive data migration or release.

## Keep Outputs Focused

Lead with the proposed semantic outcome. Show exact files changed, validation evidence, unresolved decisions, and the human review questions. Avoid presenting broad ontology theory unless it directly explains a design trade-off.
