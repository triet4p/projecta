# M3 LLM Extraction Competency Questions

**Status:** HUMAN_APPROVED (2026-08-02)
**Scope:** Sprint 5 S5-03; questions only, no ontology change.

All answers are scoped to trusted project `P`, and preserve source, candidate,
asserted, inferred, and provenance graph separation. Model output is a proposal
and never an asserted fact.

| ID | Competency question | Required answer / evidence |
|---|---|---|
| CQ-M3-SRC-001 | What immutable source note and exact Unicode spans produced extraction run `E`? | Note, canonical raw text, `[startOffset,endOffset)`, recomputed evidence text, and source project. |
| CQ-M3-PROV-001 | Which model/provider-neutral configuration generated candidate `C`? | Extraction activity, gateway/model ID, model version, prompt version, schema version, ontology version, and recorded time. |
| CQ-M3-PROV-002 | What usage and execution metadata belongs to extraction run `E` without exposing payloads? | Correlation ID, latency, token/usage counters when supplied, attempt count, result counts, and normalized error class. |
| CQ-M3-CAND-001 | Which typed entity candidates did run `E` propose, and what evidence supports each? | Candidate ID, allowlisted class, label/mention, confidence, exact source span, lifecycle state, and provenance. |
| CQ-M3-REL-001 | Which relation candidates were proposed between valid candidate or existing entities? | Candidate relation, allowlisted predicate, source/target IDs, same-project proof, confidence, evidence, and lifecycle state. |
| CQ-M3-LINK-001 | Which entity-link proposals resolve a mention to an existing project entity? | Mention evidence, bounded target ID/type/label, link confidence, extraction provenance, and abstention when no bounded target is adequate. |
| CQ-M3-LINK-002 | Can any extraction proposal link to an entity outside project `P` or to a fabricated ID? | No; invalid, unknown, or cross-project targets are rejected before persistence and reported by stable error class. |
| CQ-M3-REVIEW-001 | What review result was recorded for candidate `C`? | Validation/review activities, reviewer, decision, timestamp, reason, and candidate-to-source evidence chain. |
| CQ-M3-SCOPE-001 | Are all source, candidate, relation, link, and provenance records for run `E` inside project `P`? | Yes; every traversed record has project scope and named-graph placement consistent with its role. |
| CQ-M3-SAFE-001 | Did a malformed, unsupported, unsafe, or failed extraction mutate semantic state? | No; source/candidate/provenance writes are absent or fully rolled back, and the normalized error is queryable in safe operational telemetry. |
| CQ-M3-EMPTY-001 | Did the model abstain, and was abstention distinguished from provider failure? | Explicit abstention reason with zero candidates and successful activity, versus a failure class with no semantic mutation. |
| CQ-M3-REPLAY-001 | Does replaying the same project-scoped canonical request duplicate extraction outcome or graph records? | No; original opaque result is returned and no duplicate semantic entities or provenance are written. |

## Semantic Commitment Gate

These questions reuse released `Candidate`, `Note`, `NoteItem`, provenance,
lifecycle, evidence, project-scope, and named-graph semantics. They do not
require a new class, property, controlled individual, SHACL shape, rule, or
IRI. Provider, prompt, schema, usage, and error details are treated as
extraction activity metadata; whether any new metadata terms are needed is
deferred to S5-04's reuse/gap audit.

## Query Status

SPARQL query blocks are drafted in `llm-extraction-queries.rq`. They target a
future versioned M3 fixture and are not added to the released regression count
until the semantic contract and fixture are reviewed.
