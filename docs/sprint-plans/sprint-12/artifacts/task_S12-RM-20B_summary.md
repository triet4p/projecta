# S12-RM-20B summary

## Outcome

Completed the offline remediation for the RM-21 v2 findings without modifying
the v1 or v2 packages. The superseding v3 scorer separates endpoint absence
from endpoint drift and consumes server-derived trigger occurrence, sentence
and clause boundaries.

## Controls added

- `missingEndpointRate` counts absent candidate-table endpoint slots over two
  slots per gold relation; drifted and wrong-entity resolutions remain separate.
- Evidence support fails closed unless exactly one server-derived trigger
  occurrence is inside both the selected sentence and clause and is contained
  by the evidence span.
- Preflight requires the exact non-empty binding set and rejects removed or
  unexpected bindings, in addition to digest mismatch and missing-file tests.

## Validation

- `6 passed` for RM-20B scorer and preflight tests.
- Preflight: `OFFLINE_CONTRACTS_READY_ZERO_CALL_V3`.
- Ruff: pass.
- `git diff --check`: pass.
- Provider calls: `0`; held-out access: `false`.

## Governance boundary

RM-21A owner re-review is pending. No preregistration, execution freeze,
authorization or provider execution was issued.
