# Sprint 5 S5-06 — M3 Semantic Boundary Review

**Task status:** COMPLETED — approval gate bypassed under the user instruction
for this Sprint 5 execution.

## Reviewed Boundary

- M3 use case: `docs/use-cases/llm-candidate-extraction.md`.
- Error taxonomy: `docs/architecture/llm-extraction-errors.md`.
- Competency questions: `ontology/competency-questions/llm-extraction.md`.
- v0.3 reuse/gap audit: `docs/ontology/llm-extraction-v0.3-reuse-gap.md`.
- v0.4 draft proposal: `ontology/llm-extraction-v04.ttl` and its shapes,
  fixtures, queries, and review packet.

## Boundary Decision Used for Implementation

The application may call a provider-neutral gateway and propose zero or more
typed entity, relation, and bounded same-project link candidates. It must
normalize and validate all model output before calling Semantic Core. Semantic
Core is the sole RDF mutator; candidates remain in the candidates graph and
human review remains required before assertion. Unsupported classes,
predicates, links, evidence, and cross-project references fail closed.

The v0.4 terms are approved as the Sprint 5 implementation ontology contract.
The approval is additive, does not change existing asserted data, and does not
authorize automatic assertion of extracted candidates.

## Gate Record

The user explicitly approved the Sprint 5 ontology proposal on 2026-08-02.
Accordingly, the v0.4 vocabulary, shapes, fixtures, and competency queries are
recorded as `HUMAN_APPROVED`; the approval record is maintained in
`s5-05-review-packet.md`.
