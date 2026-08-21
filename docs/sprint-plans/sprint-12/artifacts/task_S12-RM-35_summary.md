# Task Summary: S12-RM-35 — Owner Authorization Review for Exact v8 Stage A

**Task:** S12-RM-35  
**Date:** 2026-08-22  
**Status:** complete; one bounded execution authorized, pending RM-36

## Immutable decision artifacts

- `evaluation/sprint-12/optimization/s12-f-12-rm35-owner-review.v1.json`
- `evaluation/sprint-12/optimization/s12-f-12-rm35-authorization.v8.json`
- `evaluation/sprint-12/optimization/s12-f-12-rm35-authorization-transition.v1.json`

RM-35 independently reviewed the corrected RM-34 preparation and issued one
exact v8 development Stage A authorization. The authorization binds execution
commit `005a35e3be3fbff40fcdae02dfdf79145c76934b`, the RM-32 package and
technical freeze, the canonical report-schema Git blob, the v8 output path and
the `$10.00` ceiling.

## Current authority

- `providerExecutionAuthorized=true`;
- `newAuthorizationIssued=true`;
- `authorizedExecutions=1`;
- `authorizedProviderCalls=144`;
- `providerCallsPerformed=0`;
- `stageAReportExists=false`;
- retry, overwrite, validation, held-out, Stage B, selection and promotion
  remain false.

The authorized run is exactly 144 provider calls and 96 relation branches,
with no retry and no output overwrite. The safe pre-execution preflight is
`scripts/preflight_sprint12_f12_rm35.py`; it performs zero provider calls and
returns `F12_RM35_AUTHORIZED_ZERO_CALL_PRECHECK`.

## Historical boundary and next gates

The v7 execution remains separately spent and immutable: 144 provider calls,
96 relation branches, zero retries, and v6 report digest
`sha256:419ac3c7aa7fad06287b231432d1ae167990ece45ca11ef94882fb6139569233`.
The RM-25 authorization and v7 lineage are not reused.

RM-36 must execute the exact v8 Stage A once. RM-37 must independently review
the immutable v8 report afterward. Authorization itself establishes no
quality-improvement, business-quality or tenant-readiness claim.
