# Sprint 12 Core-Quality Audit — S12-R01

**Status:** `G3.1_REMEDIATION_REQUIRED_G5_PAUSED`

This audit binds the observed atomic/scenario corpora, historical measurement
contracts, runtime baseline, evaluator implementation, and immutable S12-f-08
evidence. It is a new diagnostic artifact; it does not rewrite a historical
report, approval, registry, or aggregate.

## Findings

- The runtime contract is useful evidence: the f08 Stage A completed all 96
  case-runs with zero hard-gate failures, zero supersession false positives,
  no held-out inspection, and no candidate selection.
- On the 16-case Stage A slice, control and candidate both recorded entity
  macro F1 `0.9167` and abstention accuracy `0.9792`. Positive relation exact
  F1 was `0.0476` for both arms; candidate relation macro F1 was lower than
  control (`0.5625` versus `0.5833`).
- The atomic v2 corpus has 160 agent-authored synthetic cases, 98 abstention
  cases, 20 relation-positive cases, and artificial evidence markers in every
  case. The audit records the direct template/leakage findings without
  treating the current validator pass as semantic independence.
- The scenario v2 corpus contains 18 scenarios but only six unique source
  sequences, each reused three times with unexplained gold-effect variation.
  It is therefore not sufficient evidence for longitudinal business quality.
- A diagnostic decomposition of the f08 relation cases found 21 gold
  relations per arm: one exact match, 19 predicate-and-endpoint matches with
  a different evidence span, and one missing relation. The resulting semantic
  F1 estimates are explicitly diagnostic and not official scores until
  G3.1-A freezes the repaired metric contract.

## Decision boundary

The audit keeps Sprint 12 open and blocks provider execution, prompt sweeps,
candidate selection, validation, and G6 until measurement remediation and
dataset v3 pass their gates. The next authorized experiment, S12-f-09, must
change the deterministic relation-evidence tool dimension only.

The machine-readable binding and all source digests are in
[`core-quality-audit.v1.json`](core-quality-audit.v1.json).
