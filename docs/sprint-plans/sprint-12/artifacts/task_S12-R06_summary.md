# S12-R06 — Language metadata validation

Status: complete

S12-R06 adds `s12.language-validator.v2`, a conservative offline language
metadata audit. It uses Japanese script detection, Vietnamese diacritic and
lexical signals, and a bounded English vocabulary after removing artificial
generator-marker clauses. It reports case-level declared/inferred mismatches
using hashes for diagnostic evidence and never emits raw source text.

The validator rejects test payload input, binds the existing QA report, and
marks all language slices ineligible because the repository-visible review is
owner-delegated AI review with `humanEvidence: false` and no independent
labels. The historical v1/v2 datasets remain unchanged; this is a gate report,
not a silent metadata rewrite.

Changed artifacts:

- `scripts/sprint12_language_validator.py`
- `scripts/tests/test_sprint12_language_validator_v2.py`
- `evaluation/sprint-12/corpus/validation/language-report.v2.json`
- `evaluation/sprint-12/README.md`
- `docs/sprint-plans/sprint-12.md`

Validation: language validator fixtures, full `scripts/tests` suite, Ruff, and
`git diff --check`. No provider execution or held-out access was used.
