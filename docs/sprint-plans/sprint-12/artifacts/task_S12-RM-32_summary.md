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

## Governance

Preparation flags are true. Preregistration issuance, technical-freeze
issuance, provider execution, new authorization, validation, held-out access,
Stage B, selection and promotion are all false. RM-33 owner issuance review is
the next gate, followed by separate exact-commit execution authorization.

## Validation

* RM-32 preflight: `F12_RM32_READY_ZERO_CALL`, `providerCalls=0`.
* RM-32 deterministic preparation tests: `4 passed`.
* v8 RM-30 integration tests and adversarial schema/runtime regression:
  `8 passed` with one environment-only `.pytest_cache` permission warning.
* Exact-commit preflight validates 22 runtime git blobs and 4 separate
  preparation-evidence files; provider calls remain zero.
* Runtime implementation commit: `79447940f90b17dd22bfa2042be4c9ef2f8c54d1`.
  Regenerated package/preregistration/freeze digests are respectively
  `sha256:111f6399b5f1871a099f685673979ec5850add8489e18a11586bb1c310e4a681`,
  `sha256:9fafbc5bbbdad62c8166551248b6da8f690b3e8612842e28d19f94f6041a18f7`,
  and `sha256:011d190dabc0a4af2648ccff271b239262ec4ec019d826ce1d77d11f674b7827`.
* Immutable report digest remains
  `sha256:419ac3c7aa7fad06287b231432d1ae167990ece45ca11ef94882fb6139569233`.
* Historical accounting remains 144 calls and 0 retries.
* No provider/live runner calls; `git diff --check` required before commit.

## Next Gate

RM-33 owner issuance review of the v8 preregistration, execution package,
technical freeze and zero-call preflight. This task does not issue or execute
the new lineage; a separate v8 authorization artifact remains required.
