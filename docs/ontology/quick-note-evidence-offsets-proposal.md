# Quick Note Evidence Offsets — Governed Ontology Proposal

**Status:** HUMAN_APPROVED
**Task:** S4-04 — Resolve the mandatory semantic gap
**Released target:** additive ontology v0.3.0

## Semantic Outcome

Allow a project-scoped Quick Note segment to identify an exact, reproducible
range of the canonical Note body. This makes candidate evidence traceable to a
specific source span rather than merely to a copied segment string.

## Justification

CQ-M2-SRC-002 requires the source range for each typed segment; CQ-M2-CAND-002
requires a candidate’s evidence chain to include that range. Existing
`contentText` represents the NoteItem text but no released term records the
parent Note body or the segment’s location in it. This is evidence memory, not
operational idempotency or a UI projection.

## Alternatives Considered

1. Store offsets only in the API/operational database. Rejected: graph evidence
   queries cannot prove what the candidate was derived from after the request
   expires or operational data is rebuilt.
2. Add a `TextSpan` class. Deferred: a span has no independent identity,
   lifecycle, actor, or relation beyond one NoteItem in M2; a class adds an
   unnecessary node.
3. Add a Note body and two NoteItem datatype properties. Proposed: it is the
   smallest stable evidence representation and supports the two CQs directly.

## Proposed Design

| Term | Kind | Proposed meaning |
|---|---|---|
| `projecta:rawText` | datatype property | The canonical, complete text body captured in a Note. `xsd:string`; exactly one per M2 Note. |
| `projecta:evidenceStartOffset` | datatype property | Inclusive zero-based Unicode-code-point offset where a NoteItem begins in its parent Note’s `rawText`. `xsd:nonNegativeInteger`; exactly one. |
| `projecta:evidenceEndOffset` | datatype property | Exclusive Unicode-code-point offset immediately after a NoteItem in its parent Note’s `rawText`. `xsd:positiveInteger`; exactly one. |

The proposal keeps the `NoteItem` as the evidence-bearing entity. The range is
same-project by construction through its required parent Note; it has no
cross-project meaning. Offsets are immutable because source evidence is
immutable. Corrections create a new source revision in a future governed
workflow, not an overwrite.

### Proposed SHACL Behavior

`NoteShape` gains exactly one non-empty `rawText`. `NoteItemShape` gains exactly
one start and end offset. A SPARQL constraint verifies start < end, both values
fall inside the parent Note’s `rawText`, and the code-point substring equals
the existing `contentText`. A dataset-level constraint rejects overlapping M2
items of the same Note. The application must use the same line-ending
normalization and Unicode-code-point algorithm before it calls the Semantic
Core.

## Semantic Commitment Answers

### `rawText`

- Meaning: the full canonical body recorded by the human in one Note capture.
- Need: CQ-M2-SRC-001/002 and source-evidence governance.
- Positive examples: a two-segment meeting note; a one-segment risk note.
  Counterexamples: a Note title; a candidate label; a connector payload hash.
- Existing term: `contentText` is scoped to `NoteItem`, not its parent Note.
- Classification: immutable source evidence; not asserted, inferred, or
  operational state. It is stable across manual and future connectors.
- Literal rationale: text has no independent identity or relations in this
  slice. `xsd:string`, canonical `\n` line endings, no language normalization.
- Provenance/scope: inherited from the project-scoped, authored, timestamped
  Note. Multiple competing values are invalid for one immutable capture.

### `evidenceStartOffset` and `evidenceEndOffset`

- Meaning: inclusive beginning and exclusive ending locations of a NoteItem’s
  exact text in its parent Note body.
- Need: CQ-M2-SRC-002 and CQ-M2-CAND-002.
- Positive examples: `[0, 31)` for the first sentence; `[32, 55)` for the
  second. Counterexamples: byte positions; a selection in a rendered UI after
  formatting; offsets into another Note.
- Existing term: none. `contentText` gives copied content, not location.
- Classification: immutable source-evidence literals. They are stable across
  projects/connectors when measured against canonical raw text.
- Literal rationale: locations are scalar values without independent identity.
  Use non-negative/positive integers, zero-based, end-exclusive, Unicode code
  points. SHACL—not OWL cardinality—enforces the closed-world rules.
- Provenance/scope: inherited from the NoteItem and its parent Note; no
  independent verification state or temporal lifecycle. Multiple values are
  invalid for one M2 NoteItem.

## Impact and Validation Plan

| Consumer | Impact |
|---|---|
| Ontology/shapes | Additive terms and source-shape constraints only; no released IRI changes. |
| Existing data | v0.1/v0.2 fixtures remain valid under versioned shapes; M2-created Notes require the new fields. No backfill or migration is proposed. |
| Queries | Add M2 source/evidence queries; existing query result shapes remain unchanged. |
| Semantic Core / API | Canonicalize line endings, validate offsets before mutation, and emit the three fields. |
| Candidates/assertions/inference | Candidate remains derived from NoteItem; no lifecycle or inference change. |
| Isolation/provenance | Existing graph routing and project provenance are reused. |

Before any implementation, create a positive range fixture, invalid range,
substring mismatch, overlap, and cross-project tests; execute existing query,
SHACL, and isolation regressions plus new M2 queries. No rule is proposed.

## Unresolved Human Decisions

1. Approve Unicode code-point offsets after LF normalization. This is portable
   across Python and RDF, but browser clients using UTF-16 must convert before
   submission. Selecting UTF-16 instead changes API and validation semantics.
2. Approve non-overlap for M2. Allowing overlap would support nested evidence
   later but needs an explicit use case and a changed source-validation rule.
3. Approve storing the raw Note body in RDF source evidence. Keeping it only in
   object storage would require a durable content-addressed reference and a
   different evidence-query design.

## Human Approval Recorded

The user approved the M2 contract at S4-05 on 2026-07-31. That approval covers
the boundary, competency questions, reuse/gap finding, deterministic extraction
semantics, inference deferral, and this smallest proposed resolution.

- [x] Approve semantic meaning
- [x] Approve vocabulary names and IRIs
- [x] Approve validation behavior
- [x] Approve inference behavior (no rule proposed)
- [x] Approve migration/deprecation plan (no migration proposed)
- [x] Authorize draft implementation and later release review

The user approved the validated implementation for release on 2026-08-01.
Ontology v0.3.0 and the M2 Quick Note slice are repository-local releases; no
shared or production dataset was mutated.
