# Task Summary: S12-RM-32 — Prepare Superseding f12 Lineage Offline

**Sprint:** Sprint 12  
**Task:** S12-RM-32

## Summary of Work

Prepared a new, non-authoritative v8 f12 superseding lineage under the RM-31
owner boundary. The preparation includes a preregistration, execution package,
technical-freeze record and a provider-neutral zero-call preflight. A separate
runtime commit now provides the guarded v8 runner, closed v8 report and
authorization schemas, and actual RM-30 finite diagnostic integration.

Runtime custody uses exact git-blob SHA-256 digests at the execution commit;
preflight and test files are recorded separately as preparation evidence and
excluded from the runtime digest set. Their physical presence at the commit
is not treated as an execution claim.

The closed v7 lineage, spent RM25 authorization and immutable Stage A v6
report remain unchanged. The new v8 output path is distinct and cannot
overwrite report v6. No provider adapter, live runner or authorization was
invoked.

## Artifacts

* `evaluation/sprint-12/optimization/s12-f-12-rm32-preregistration.v8.json`
* `evaluation/sprint-12/optimization/s12-f-12-rm32-execution-package.v8.json`
* `evaluation/sprint-12/optimization/s12-f-12-rm32-technical-freeze.v8.json`
* `scripts/preflight_sprint12_f12_rm32.py`
* `scripts/regenerate_sprint12_f12_rm32_v8.py`
* `scripts/tests/test_sprint12_rm32_offline_preparation.py`
* `scripts/run_sprint12_f12_stage_a_v8.py` and its v8 report/authorization
  schemas and deterministic mocked tests.
* `evaluation/sprint-12/current-state-next-rm32.v1.json` and non-authoritative
  G5 v20 preparation snapshot.

## Governance at RM-32 completion

Preparation flags were true. The RM-32 preparation snapshots retain
preregistration and technical-freeze issuance as false; RM-33 subsequently
issued those two permissions through its separate digest-bound transition.
Provider execution, new authorization, validation, held-out access, Stage B,
selection and promotion remain false.

## Validation

* RM-32 preflight: `F12_RM32_READY_ZERO_CALL`, `providerCalls=0`.
* RM-32 deterministic preparation tests: `4 passed`.
* v8 RM-30 integration tests and adversarial schema/runtime regression:
  `9 passed` with one environment-only `.pytest_cache` permission warning.
* Exact-commit preflight validates 22 runtime git blobs and 4 separate
  preparation-evidence files; provider calls remain zero.
* Runtime implementation commit: `005a35e3be3fbff40fcdae02dfdf79145c76934b`.
  Regenerated package/preregistration/freeze digests are respectively
  `sha256:59a42669692c9c4a5460a44643167c17c68d5449a4b9d8de2e35adad0f0f524c`,
  `sha256:ec2ced60f927e7e8c016b6d2a1d5ed0b5cf52875d3d25c8778626cc75673ccb6`,
  and `sha256:2fc20e806ce4a046c10719e9360cc69938325e1963562b730d02b8138f8dfdc1`.
* Immutable report digest remains
  `sha256:419ac3c7aa7fad06287b231432d1ae167990ece45ca11ef94882fb6139569233`.
* Historical accounting remains 144 calls and 0 retries.
* No provider/live runner calls; `git diff --check` required before commit.

## Next Gate at RM-32 completion

RM-33 owner issuance review of the v8 preregistration, execution package,
technical freeze and zero-call preflight (now complete). RM-34 must prepare a
separate exact v8 authorization artifact, followed by RM-35 owner review; this
task did not issue or execute the new lineage.
