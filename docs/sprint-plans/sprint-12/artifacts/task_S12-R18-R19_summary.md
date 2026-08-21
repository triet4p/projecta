# S12-R18/R19 — deterministic relation evidence tool

Status: complete

The extraction server now has a pure deterministic materializer that accepts
canonical source/target entity spans, an allowlisted predicate and an optional
trigger quote, then returns the smallest unambiguous clause/sentence evidence
span. It preserves Unicode code-point offsets and source-slice equality. It
never trusts model-authored relation offsets.

The regression suite covers multilingual sentence punctuation, emoji/code
points, repeated mentions, multiple entity pairs, clause boundaries, invalid
spans, missing triggers and endpoints split across sentences. Invalid or
ambiguous context returns no materialization rather than guessing.

Changed artifacts:

- `apps/api/src/projecta_api/extraction/relation_evidence.py`
- `apps/api/tests/test_relation_evidence_materializer.py`
- `docs/sprint-plans/sprint-12.md`

Validation: materializer and relation-normalization tests, Ruff, and
`git diff --check`. The tool is not yet wired into a provider experiment; R20
preregistration remains pending.
