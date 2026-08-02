# Task Summary: S5-03 — Define M3 competency questions

**Sprint:** Sprint 5
**Task:** S5-03

## Summary of Work

Defined twelve M3 questions covering source/evidence traversal, extraction
provenance, entity and relation candidates, bounded links, review outcomes,
project scope, safe failure, abstention, and replay idempotency. The questions
explicitly reuse released lifecycle and graph boundaries and defer any semantic
term decision to S5-04.

## Files Modified

- `ontology/competency-questions/llm-extraction.md` — question inventory and semantic commitment gate.
- `ontology/competency-questions/llm-extraction-queries.rq` — draft query blocks.

## Testing

- **Test File:** M3 competency queries are now covered by the approved v0.4 fixture and canonical ontology suite.
- **Status:** Query execution and v0.4 release validation are complete through S5-31.
- **Execution Command:** `git -c safe.directory=F:/ai-ml/projecta diff --check`

## Ontology Governance Review Packet

- **Status at completion:** `HUMAN_APPROVED` (2026-08-02; approved after Sprint 5 ontology review)
- **Business need:** Make extraction provenance, evidence, links, review, scope, and safe failure auditable.
- **Semantic outcome:** Reuse released terms where possible; no ontology artifact is changed by S5-03.
- **Resolution:** S5-05 approved the additive v0.4 vocabulary and extraction-activity metadata.
