# Controlled Optimization Review Packet v31 — RM-45 v9 Authorization

**Status:** `G5_F12_CORRECTED_V9_LINEAGE_AUTHORIZED_ONE_STAGE_A_PENDING_EXECUTION`  
**Date:** 2026-08-22  
**Scope:** exactly one v9 development Stage A execution; no retry or downstream access

## Decision boundary

RM-45 independently reviewed the immutable RM-44 preparation and issued one
exact v9 Stage A authorization. The authorization is bound to execution commit
`f81103b0b8f6c19a65b8d37ccfb0d08e8aeee11e`, the RM-42 package/freeze, 19 exact
Git-blob runtime bindings, the v9 authorization/report schemas, the frozen v3
dataset, output v9 and a `$10.00` ceiling.

Issuance performed zero provider calls and created no report. The authorization
is single-use: it permits exactly 144 provider calls and 96 relation-branch
outputs for one development Stage A execution. Retry, output overwrite,
validation, held-out access, Stage B, candidate selection, promotion and
downstream access remain closed.

## Immutable custody

- RM-44 preparation:
  `sha256:fe7f74f02e51489d0d68d997df2824705d2c52885ccf88857eec35fc79621285`
- RM-45 owner review:
  `sha256:8f5e8f55d7893756a764e334915de7317038016ee25b87afbd80884a4c75d1bf`
- RM-45 authorization:
  `sha256:ad84eaad496458cc2f5064be59016d7e2497aa4d3ad898e807cf8d496d77a0c8`
- RM-45 transition:
  `sha256:68a69e313e203aa7d5e88209efacf3d7b8eab293a2d015810f0953fdb0dc6234`
- Authoritative machine packet:
  `sha256:e2d2818913447fc20eb6268a94f6ff7fe4cc28fa518dac37b52e4d5b67b7c5e0`

The RM-42 execution package and technical-freeze digests remain respectively
`sha256:cdaad8ebdce34115c8853067245ed6e5ef4107e271de5ce073a1cbdef20b05d2`
and
`sha256:f595730955848c76d0399706d5f2f32c367a6e88b62a5b3c3986bf2ccc3dfe32`.
The immutable v6 report remains
`sha256:419ac3c7aa7fad06287b231432d1ae167990ece45ca11ef94882fb6139569233`.
The failed v8 invocation remains a separate immutable three-call, pre-report
failure fact; its authorization is spent and is not reused.

## Pre-execution evidence

The read-only RM-45 preflight is
`scripts/preflight_sprint12_f12_rm45.py` and returns
`F12_RM45_AUTHORIZED_ZERO_CALL_PRECHECK`. It validates the v9 authorization
schema, owner-review and transition digests, exact commit chain, all 19 Git
blobs, runtime/provider/model/prompt/dataset bindings, output absence and
current-state/packet custody. It reports one authorized execution, 144 calls,
96 relation branches, zero calls performed, zero retries and the `$10.00`
ceiling.

Focused tests cover schema, status, digest custody, single-use and closed
downstream locks. No live runner or provider was invoked during RM-45 issuance
or preflight.

## Current state and next gates

The authoritative machine index is
`evaluation/sprint-12/current-state.v1.json`; this packet is
`evaluation/sprint-12/optimization/g5-packet.v31.rm45-authorization.json`.
The next permitted action is S12-RM-46: execute the exact v9 Stage A once.
S12-RM-47 must then make a separate owner post-run decision from the immutable
report or pre-report execution fact. No quality improvement, candidate,
validation, held-out, Stage B, promotion or tenant-readiness claim exists yet.
