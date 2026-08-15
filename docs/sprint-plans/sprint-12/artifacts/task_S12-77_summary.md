# S12-77 — Model comparisons

Preregistered S12-77 / `s12-f-05` against the same dataset, guarded prompt,
evaluator, budget and baseline configuration digest. Stage A is fixed at 16
development cases × 3 paired control/candidate runs with no retry. It includes
the two unstable cases `s12-a-0153` and `s12-a-0187`, positive entity/relation
cases and abstention cases.

The candidate model is intentionally unbound and execution is not authorized
until the owner supplies the comparison model. No comparison is claimed
without runtime-backed runs.

## Testing

The Phase F suite confirms all five dimensions are represented and the persisted
registry v2 passes the executable validator. The candidate model was later
bound through preregistration v2 before execution.

## Stage A result

The candidate model was bound as `deepseek-v4-pro` and Stage A completed with
the preregistered 16-case paired protocol, 3 runs per model, and no retry.
Stage B is not authorized:

- Control `deepseek-v4-flash`: 1 `invalid_evidence`, 1 missing output.
- Candidate `deepseek-v4-pro`: 2 `schema_invalid`, 1 `cross_project_link`,
  3 missing outputs.
- Candidate deltas: entity macro F1 `-0.0235`, abstention `-0.0101`,
  hallucination reduction `-0.0056`, relation macro F1 `+0.0030`.
- Cost accounting remains unavailable because no provider price configuration
  is bound.

The immutable Stage A result is `STAGE_A_NOT_ELIGIBLE_FOR_STAGE_B`; validation,
full 160-case execution and candidate freeze remain locked.

## Targeted follow-up

One no-retry diagnostic attempt was run on `s12-a-0121` and `s12-a-0176` with
`deepseek-v4-pro`. Both cases scored successfully and the diagnostic reported
`failureCounts = {}`. This is recorded as stochastic non-reproduction only;
the Stage A hard-invariant failure and the Stage B lock remain unchanged.
