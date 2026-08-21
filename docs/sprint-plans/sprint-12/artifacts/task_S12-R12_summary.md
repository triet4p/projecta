# S12-R12 — v3 pilot quality gate

Status: complete

The offline G3.1-B pilot gate passes the six required visible-data checks:
schema, provenance, code-point span integrity, language metadata,
scenario consistency, and development/validation leakage. The gate binds the
R11 adjudication packet and reports no diagnostic failures. Test payloads remain
sealed and uninspected; this gate does not authorize provider execution.

Coverage is published by business journey and split, not only by total case
count. The report includes every released entity type and relation predicate,
relation-positive and relation-negative case counts, abstention required versus
not required, entity/relation totals, and scenario counts for J1–J6. The pilot
contains 48 cases (32 development / 16 validation), 15 relation-positive cases,
33 relation-negative cases, and six required abstentions.

The language gate explicitly treats code-switched notes as `mixed` only when
Vietnamese signal and an ASCII code-switch token are both present. Four
English-only notes were corrected from the authored `mixed` metadata before
the gate; the historical v1/v2 datasets remain unchanged.

Changed artifacts:

- `scripts/sprint12_v3_pilot_quality_gate.py`
- `scripts/tests/test_sprint12_v3_pilot_quality_gate.py`
- `evaluation/sprint-12/gates/g3.1-b-v3-pilot-quality.v1.json`
- `evaluation/sprint-12/corpus/v3/atomic-deep-pilot.v1.json`
- `evaluation/sprint-12/corpus/v3/manifest.v1.json`
- `evaluation/sprint-12/README.md`
- `docs/sprint-plans/sprint-12.md`

Validation: all gate diagnostics, tamper fixtures, full `scripts/tests` suite,
Ruff, and `git diff --check`. R13 review and approval remains pending.
