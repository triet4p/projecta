# S12-RM-44 — Exact v9 Stage A Authorization Preparation

**Status:** complete, preparation-only; RM-45 owner review pending  
**Date:** 2026-08-22

RM-44 prepared the exact v9 Stage A authorization contract without calling a
provider or invoking the live runner. The artifact binds RM-43 owner review and
issuance transition, the RM-42 v9 package/preregistration/freeze chain, lineage
commit `6537f6b79f1f5326a9d8362b09af7e52df74819f`, execution commit
`f81103b0b8f6c19a65b8d37ccfb0d08e8aeee11e`, and 19 canonical Git-blob runtime
digests. It records the provider/runtime/model/prompt/dataset contract, v9
output path, 144-call/96-branch bound, no retry, no overwrite and `$10.00`
ceiling.

The zero-call preflight returns `F12_RM44_PREPARED_ZERO_CALL`. It confirms
provider calls `0`, retry count `0`, exact runtime blobs `19/19`, v6 unchanged,
v8/v9 output absent and all downstream governance locks closed. The prospective
default-path deterministic mock records unauthorized calls `0`, authorized
calls `144`, relation branches `96`, one persist, retry `0` and overwrite
rejection. The preflight uses external working-tree preparation evidence and
its tamper test rejects a one-character change without circular self-binding.

Machine artifact:
`evaluation/sprint-12/optimization/s12-f-12-rm44-authorization-preparation.v1.json`
(`sha256:9b2448056e81bb66c4034e161ed49f6b523b947488ccce24a9cc6adc0db6649c`).
The v30 packet and next-state file are explicitly non-authoritative. The
authoritative RM-43 current-state index is unchanged. RM-45 is the sole next
gate and must independently review and issue authorization before any provider
capture.
