# M2 Quick Note Competency Questions

**Status:** HUMAN_APPROVED
**Scope:** Sprint 4 S4-02; no ontology change is made by this document.

The questions below define M2 acceptance. Every answer is project-scoped and
must preserve the distinction between source, candidate, asserted, inferred,
and provenance graphs.

| ID | Competency question | Required answer / evidence |
|---|---|---|
| CQ-M2-SRC-001 | What raw note was captured for project P, by whom, and when? | Note identity, canonical raw text, project, author, and `recordedAt`. |
| CQ-M2-SRC-002 | Which ordered typed segments came from note N, and what exact range in its raw text supports each? | NoteItem, released type, text, `[startOffset, endOffset)`, and equality to the note substring. |
| CQ-M2-CAND-001 | Which candidate was deterministically created from source segment S? | Candidate identity, source NoteItem, generator, ontology version, generated time, and lifecycle state. |
| CQ-M2-CAND-002 | Can a candidate’s evidence chain be traversed to the original note, author, and exact source range without crossing projects? | Candidate → NoteItem → Note → author plus same-project proof and offsets. |
| CQ-M2-REV-001 | What review decision was made for candidate C, by whom, when, and why when rejected? | Lifecycle activity, reviewer, decision, timestamp, and rejection reason where applicable. |
| CQ-M2-ASSERT-001 | Which current asserted results in project P came from confirmed Quick Note candidates? | Current asserted item, released type, candidate, reviewer, and full source chain. |
| CQ-M2-ASSERT-002 | Did a rejected candidate create an asserted item? | No; rejection is visible in candidate history only. |
| CQ-M2-PROV-001 | Does a capture replay create duplicate source, candidate, or provenance entities? | No; same project, key, and canonical request return the original outcome. This is operational/idempotency evidence, not an ontology query. |
| CQ-M2-ISO-001 | Can any M2 read or mutation traverse another project’s source, candidate, assertion, or provenance? | No; project-scoped routing and isolation validation reject it. |

## Inference Boundary

Inference output is explicitly not an M2 acceptance criterion. The inferred
graph must remain empty for this slice. A future rule needs its own competency
question, deterministic derivation provenance, negative test, semantic
proposal, and human approval.

## Query and Test Status

The complete nine-question M2 query inventory is implemented in
`quick-note-m2-queries.rq` and runs against the released v0.3 fixture. These
are release regression checks approved with S4-24 on 2026-08-01.
