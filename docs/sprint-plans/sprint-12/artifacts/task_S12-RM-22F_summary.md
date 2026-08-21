# S12-RM-22F summary

## Outcome

Published superseding RM-22D execution lineage v7 after RM-23E withheld v6
issuance. RM-22D v6 remains historical and was not modified.

- Added runner `scripts/run_sprint12_f12_stage_a_v6.py` bound to package,
  preregistration, freeze and report output v6.
- Added closed authorization schema v2 with exact report output v6.
- Added report schema v6 with exact report artifact version v6.
- Added v7 preflight and bound all new execution files to exact commit
  `e047911e2e2d513f2b8751965dd702b2c1fe9d5a`.
- Added mocked authorized E2E coverage for zero-call unauthorized execution,
  `144 calls / 96 branches`, one persist, and no-overwrite/no-retry behavior.
- Provider authorization and held-out access remain locked.

## Artifacts

- `evaluation/sprint-12/optimization/s12-f-12-rm22d-issuance-draft.v7.json`
- `evaluation/sprint-12/optimization/s12-f-12-rm22d-execution-package.v7.json`
- `evaluation/sprint-12/optimization/s12-f-12-rm22d-technical-freeze.v7.json`
- `evaluation/sprint-12/harness/s12-f-12-authorization.schema.v2.json`
- `evaluation/sprint-12/harness/s12-f-12-stage-a-report.schema.v6.json`
- `scripts/run_sprint12_f12_stage_a_v6.py`
- `scripts/preflight_sprint12_f12_rm22d_v7.py`
- `scripts/tests/test_sprint12_f12_rm22e_execution.py`

## Validation

- Mocked guarded E2E: `3 passed`.
- Preflight: `F12_RM22D_READY_ZERO_CALL_V7`.
- Ruff, JSON validation and `git diff --check`: pass.
- Provider calls: `0`.
- Held-out access: `false`.

Next gate: `S12-RM-23F` owner issuance review. This remediation does not
issue preregistration, freeze approval or provider authorization.
