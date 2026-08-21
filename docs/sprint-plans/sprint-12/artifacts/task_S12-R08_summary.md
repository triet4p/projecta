# S12-R08 — G3.1-A measurement readiness

Status: complete

S12-R08 publishes `s12.g31-a-readiness.v1`, binding the v2 metric contract,
current evaluator/instrumentation v4, sanitized relation signatures, the
leakage/language/scenario validators, their diagnostic reports, and the
offline contract tests. The readiness packet proves that the measurement
layer is ready for the repaired dataset track.

The gate is deliberately scoped: `providerExecutionAuthorized: false`,
`providerCallsPerformed: false`, and `heldOutInspected: false`. The current v2
dataset remains blocked by the R05–R07 findings, so G3.1-B/G3.1-C and G5-R
remain closed. This packet does not authorize prompt optimization, candidate
selection, validation, or test access.

Changed artifacts:

- `scripts/sprint12_g31_measurement_readiness.py`
- `scripts/tests/test_sprint12_g31_measurement_readiness.py`
- `evaluation/sprint-12/gates/g3.1-a-measurement-readiness.v1.json`
- `evaluation/sprint-12/README.md`
- `docs/sprint-plans/sprint-12.md`

Validation: readiness fixtures, full `scripts/tests` suite, Ruff, and
`git diff --check`. No provider execution or held-out access was used.
