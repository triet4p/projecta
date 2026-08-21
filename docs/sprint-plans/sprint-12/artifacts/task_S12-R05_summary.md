# S12-R05 — Strengthened leakage validation

Status: complete

S12-R05 adds `s12.leakage-validator.v2`. The validator canonicalizes Unicode
text, generator-marker clauses, identifiers, numeric values, punctuation, and
whitespace before comparing semantic templates. It also checks exact content
digests and groups scenario source manifests into lineage hashes, detecting
reused lineages and conflicting scenario gold.

The validator is fail-closed around custody: it rejects an accidentally
supplied test payload and never reads held-out source or gold. Reports contain
only split counts, case/scenario identifiers, and hashes—never raw source text
or canonicalized text. The historical v1/v2 corpus is intentionally reported
as blocked because it contains generator markers, normalized-template overlap,
reused scenario lineages, and conflicting scenario gold.

Changed artifacts:

- `scripts/sprint12_leakage_validator.py`
- `scripts/tests/test_sprint12_leakage_validator_v2.py`
- `evaluation/sprint-12/corpus/validation/leakage-report.v2.json`
- `evaluation/sprint-12/README.md`
- `docs/sprint-plans/sprint-12.md`

Validation: leakage validator fixtures, full `scripts/tests` suite, Ruff, and
`git diff --check`. No provider execution or held-out access was used.
