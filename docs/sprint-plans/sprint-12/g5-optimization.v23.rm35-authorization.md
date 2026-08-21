# Sprint 12 G5 — RM-35 v8 Authorization

**Status:** `G5_F12_V8_AUTHORIZED_PENDING_EXECUTION`

The authoritative machine packet is
`evaluation/sprint-12/optimization/g5-packet.v23.rm35-authorization.json`.
It supersedes the non-authoritative RM-34 preparation snapshot and records the
immutable RM-35 owner review, authorization and transition:

- owner review:
  `evaluation/sprint-12/optimization/s12-f-12-rm35-owner-review.v1.json`
- authorization:
  `evaluation/sprint-12/optimization/s12-f-12-rm35-authorization.v8.json`
- transition:
  `evaluation/sprint-12/optimization/s12-f-12-rm35-authorization-transition.v1.json`

RM-35 authorizes exactly one development Stage A execution against execution
commit `005a35e3be3fbff40fcdae02dfdf79145c76934b`, the RM-32 v8 package and
technical freeze, the canonical report-schema Git blob, the v8 output path and
the `$10.00` ceiling. The bound execution is exactly 144 provider calls and 96
relation branches, with no retry and no output overwrite.

The safe pre-execution preflight is
`scripts/preflight_sprint12_f12_rm35.py`, returning
`F12_RM35_AUTHORIZED_ZERO_CALL_PRECHECK`. It validates the v8 authorization
schema, RM-35 digests, all 22 exact runtime Git blobs, the absent v8 output and
the immutable v6 digest. It performs no provider call and does not invoke the
live runner.

The historical v7 execution remains separately recorded as the sole spent
historical execution: 144 provider calls, 96 relation branches, zero retries,
and immutable report digest
`sha256:419ac3c7aa7fad06287b231432d1ae167990ece45ca11ef94882fb6139569233`.
The current v8 lineage has authorization for one execution but has performed
zero calls and has no report yet.

Validation and held-out access, Stage B, candidate selection, promotion,
retry and overwrite remain closed. RM-36 is the next permitted action; RM-37
must perform a separate owner post-run decision after the immutable v8 report
exists. Authorization establishes no quality improvement, business quality or
tenant readiness claim.
