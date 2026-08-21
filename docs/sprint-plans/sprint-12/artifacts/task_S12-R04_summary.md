# S12-R04 — Sanitized diagnostic signatures

Status: complete

S12-R04 extends the current relation instrumentation to v4. Each scored case
now persists separate gold and predicted relation signatures containing only:

- predicate;
- canonical endpoint offsets and released entity types, or a missing status;
- evidence offsets, or a missing status;
- the mutually exclusive diagnostic error class.

Entity IDs, candidate IDs, raw source text, and payload fields are not emitted.
The existing reconciliation totals remain authoritative and are covered by
fixtures for wrong spans, missing relations, and extra relations.

Changed artifacts:

- `scripts/sprint12_evaluator.py`
- `scripts/tests/test_sprint12_sanitized_signatures.py`
- `scripts/tests/test_sprint12_relation_instrumentation_v3.py`
- `scripts/tests/test_sprint12_f07_execution_contract.py`
- `evaluation/sprint-12/harness/README.md`
- `docs/sprint-plans/sprint-12.md`

Validation: targeted S12 relation tests, full `scripts/tests` suite, Ruff, and
`git diff --check`. No provider execution or held-out access was used.
