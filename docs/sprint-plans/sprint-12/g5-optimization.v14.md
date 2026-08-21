# Sprint 12 G5 Optimization Packet v14

> Historical gate snapshot. The authoritative current packet is
> [G5 Optimization Packet v17](g5-optimization.v17.md).

**Status:** `G5_F12_STAGE_A_COMPLETED_REJECTED_HARD_GATE_PENDING_OWNER_DECISION`

The single RM-25-authorized S12-f-12 development Stage A execution completed
once. The immutable v6 report is JSON-Schema-valid and records 144 provider
calls, 96 relation branches, 0 retries, 0 pricing failures and total cost
`$0.00592500` under the `$10.00` ceiling.

The report fails closed on `schemaInvalid=6` and `invalidEvidence=17`; the
registered threshold and slice gates also fail. Gold-relations integrity and
cost gates pass. This is a rejected Stage A result, not a candidate-quality or
accuracy-improvement claim.

## Bound evidence

- Report: `evaluation/sprint-12/optimization/s12-f-12-stage-a-report.v6.json`
  (committed blob `sha256:419ac3c7aa7fad06287b231432d1ae167990ece45ca11ef94882fb6139569233`)
- Execution transition:
  `evaluation/sprint-12/optimization/s12-f-12-stage-a-execution-transition.v1.json`
- Exact execution commit: `e047911e2e2d513f2b8751965dd702b2c1fe9d5a`

## Governance boundary

The report is preserved without retry or overwrite. Validation, held-out
access, Stage B, candidate selection and promotion remain unauthorized. The
next permitted action is a separate owner post-run decision on the immutable
report. Any rerun requires a superseding package and new owner authorization.
