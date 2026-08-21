# S12-R07 — Scenario semantic consistency validation

Status: complete

S12-R07 adds `s12.scenario-validator.v2`. The validator verifies event/source
lineage shape and compares repeated source sequences across four independent
dimensions: temporal effects, review dispositions, graph checkpoints, and
competency answers. It records only lineage/scenario identifiers and hashes;
raw scenario payload and gold fields are not emitted in the report.

Conflicting dimensions are considered explained only when the lineage carries
a non-empty `semanticVariationRationale`. The historical scenario v2 corpus
contains six repeated lineages with unexplained conflicts, so the report is
blocked and no longitudinal business-quality claim is authorized. The
historical corpus is not rewritten, and test payloads remain sealed.

Changed artifacts:

- `scripts/sprint12_scenario_validator.py`
- `scripts/tests/test_sprint12_scenario_validator_v2.py`
- `evaluation/sprint-12/corpus/validation/scenario-report.v2.json`
- `evaluation/sprint-12/README.md`
- `docs/sprint-plans/sprint-12.md`

Validation: scenario validator fixtures, full `scripts/tests` suite, Ruff, and
`git diff --check`. No provider execution or held-out access was used.
