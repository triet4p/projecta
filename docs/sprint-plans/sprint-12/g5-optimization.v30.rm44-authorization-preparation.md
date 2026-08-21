# Controlled Optimization Review Packet v30 — RM-44 Exact v9 Authorization Preparation

**Status:** `G5_F12_RM44_EXACT_V9_AUTHORIZATION_PREPARED_PENDING_RM45_OWNER_REVIEW`  
**Date:** 2026-08-22  
**Scope:** preparation only; no provider or live runner execution

## Decision boundary

RM-44 prepared one exact v9 development Stage A authorization contract. It is
not an issued authorization: `providerExecutionAuthorized=false`,
`newAuthorizationIssued=false`, provider calls performed are zero, and the v9
report is absent. The authoritative current state remains the RM-43 issuance
state until RM-45 independently reviews and issues the authorization.

Machine artifacts:

- `evaluation/sprint-12/optimization/s12-f-12-rm44-authorization-preparation.v1.json`
  (`sha256:9b2448056e81bb66c4034e161ed49f6b523b947488ccce24a9cc6adc0db6649c`)
- `scripts/preflight_sprint12_f12_rm44.py`
- `scripts/tests/test_sprint12_rm44_authorization_preparation.py`
- non-authoritative snapshots:
  `evaluation/sprint-12/optimization/g5-packet.v30.rm44-authorization-preparation.json`
  and `evaluation/sprint-12/current-state-next-rm44.v1.json`

## Exact custody

The preparation binds RM-43 owner review
(`sha256:dd8d0210e8bed24b68fea64188fd8bb5cbb45c7a5962f4342b74b8811c9006a9`)
and issuance transition
(`sha256:d57f040293ff0be4573d49e97a20cea9c838152b47945ee3fc01af2568637fdb`),
lineage commit `6537f6b79f1f5326a9d8362b09af7e52df74819f`, and execution commit
`f81103b0b8f6c19a65b8d37ccfb0d08e8aeee11e`.

The RM-42 v9 preregistration/package/freeze digests are respectively
`sha256:147503146accb6462548b9a4ce238bee989aacc63884e67a15a217304bfa03c4`,
`sha256:cdaad8ebdce34115c8853067245ed6e5ef4107e271de5ce073a1cbdef20b05d2`,
and `sha256:f595730955848c76d0399706d5f2f32c367a6e88b62a5b3c3986bf2ccc3dfe32`.
All 19 runtime bindings use canonical `git_blob_sha256`; the runner, report
schema and authorization schema digests are
`sha256:523106bf38a2da3acdd6cf6be6dcb299e1763174d41d0e1f4438f5c1fefd92dd`,
`sha256:262822030197e36cbabe9d7cb734c794385fa8b6d8d4bf3a63eb5ce82f864bea`,
and `sha256:47b52efd42849e436f757cdcedc12989d6a64820a0049db5c33e14cb8523a2b9`.

The runtime contract is `openai-response` / `deepseek-chat-completions`,
model `deepseek-v4-flash`, prompt `m3.prompt.v7-v2.two-step-extraction`, and
the frozen v3 atomic dataset. The output is
`evaluation/sprint-12/optimization/s12-f-12-stage-a-report.v9.json`.

## Safe evidence

The zero-call preflight returns `F12_RM44_PREPARED_ZERO_CALL`, with 19/19 exact
runtime blobs, 144 planned calls, 96 relation branches, zero provider calls
and zero retries. The prospective default-path deterministic mock records 144
authorized calls, 96 relation branches, one persist and overwrite rejection;
unauthorized calls and live runner invocations are zero. The preflight's own
working-tree digest is externally bound in `preparationEvidence`, and the
tamper test rejects a one-character change without circular self-hashing.

Targeted validation: `20 passed` across RM-44 preparation, RM-42 preparation
and the existing v9 runtime contract tests. The only output is the normal
Windows `.pytest_cache` access warning; no provider call was made.

## Governance and next gate

Only `preregistrationIssued` and `technicalFreezeIssued` are true. Provider,
new authorization, rerun, retry, validation, held-out, Stage B, selection,
promotion and downstream access remain false. The failed v8 lineage and spent
RM-35 authorization are preserved and non-reusable; immutable v6 remains
unchanged. RM-45 must independently review every binding and issue the
authorization before any v9 provider capture.
