# Sprint 12 G5 RM-32 Offline Lineage Preparation v20

**Role:** non-authoritative offline next-state preparation

**Current authoritative packet remains:**
`evaluation/sprint-12/optimization/g5-packet.v19.json`

RM-32 prepared a new versioned v8 f12 preregistration, execution package,
technical freeze and provider-neutral zero-call preflight under the RM-31
approval boundary. The package binds the corrected RM-30 diagnostic/report
contracts and the guarded v6 runner at exact repository digests.

## Prepared artifacts

- `evaluation/sprint-12/optimization/s12-f-12-rm32-preregistration.v8.json`
- `evaluation/sprint-12/optimization/s12-f-12-rm32-execution-package.v8.json`
- `evaluation/sprint-12/optimization/s12-f-12-rm32-technical-freeze.v8.json`
- `scripts/preflight_sprint12_f12_rm32.py`

The preflight result is `F12_RM32_READY_ZERO_CALL` with `providerCalls=0`.
The new output is reserved at
`evaluation/sprint-12/optimization/s12-f-12-stage-a-report.v8.json`; the
immutable v6 report remains untouched.

## Governance boundary

Preparation flags are true, but `preregistrationIssued=false`,
`technicalFreezeIssued=false`, `providerExecutionAuthorized=false`,
`newAuthorizationIssued=false`, and validation, held-out access, Stage B,
selection and promotion remain false. RM-33 must review and issue the prepared
artifacts; a separate exact-commit authorization is required before execution.
