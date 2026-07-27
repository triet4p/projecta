# Human Review Packet

End ontology work with this concise packet.

## Status

Use exactly one allowed skill status.

## Semantic outcome

State the domain meaning introduced or changed in plain language.

## Justification

- Use case/governance need.
- Competency questions answered.
- Initialization documents and existing terms used as evidence.

## Proposed design

List:

- Classes.
- Object properties.
- Datatype properties.
- Individuals/vocabularies.
- SHACL shapes.
- Rules.
- Deprecated/replaced terms.

Show stable IRIs when defined. Mark temporary identifiers clearly.

## Semantic commitment answers

For every new or materially changed class/property:

- Link it to the competency questions it enables.
- State its plain-language meaning.
- State why it is a class, individual, object property, datatype property, relation node, state/role, or non-ontology concern.
- Summarize identity, independence, lifecycle/membership, hierarchy, domain/range, arity, provenance, and temporal answers that apply.
- Mark every unknown and explain why implementation can or cannot proceed safely.

Do not omit this section because the proposed term appears intuitive.

## Alternatives considered

Explain meaningful alternatives and why the proposed model is preferred. Do not invent weak alternatives merely to fill the section.

## Artifact diff

List every created or changed file and its purpose. Distinguish:

- Semantic source.
- Validation.
- Rules.
- Examples/fixtures.
- Competency tests.
- Migration/version metadata.

## Validation evidence

Report commands/checks and outcomes. Separate:

- Passed automated checks.
- Failed checks.
- Checks not run because tooling or artifacts are absent.
- Manual semantic inspection.

## Compatibility and risk

Report impact on existing data, queries, inference, API/contracts, connectors, projections, isolation, and provenance.

## Unresolved questions

Ask only decisions requiring human domain authority. Make the consequence of each choice clear.

## Human actions requested

Use explicit checkboxes:

```text
[ ] Approve semantic meaning
[ ] Approve vocabulary names and IRIs
[ ] Approve validation behavior
[ ] Approve inference behavior
[ ] Approve migration/deprecation plan
[ ] Authorize implementation or release step
```

Do not pre-check an item unless the human explicitly approved that exact item.
