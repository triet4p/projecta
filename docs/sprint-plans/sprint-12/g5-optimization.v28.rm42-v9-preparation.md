# Sprint 12 G5 — RM-42 Corrected v9 Runtime-Lineage Preparation

**Status:** `G5_F12_SUPERSEDING_V9_RUNTIME_LINEAGE_PREPARED_PENDING_RM43_OWNER_ISSUANCE_REVIEW`

RM-41 approved offline preparation of a corrected superseding runtime lineage.
RM-42 integrates the RM-40 exact semantic-pair reconciliation behavior into a
new guarded v9 runner and prepares unissued v9 preregistration, execution
package and technical-freeze artifacts.

## Runtime custody

The runtime commit is `f81103b0b8f6c19a65b8d37ccfb0d08e8aeee11e`. Runtime inputs
are bound with Git-blob SHA-256 digests at that exact commit. Preparation
evidence is held in a separate digest namespace and is excluded from
`runtimeBoundDigests`, avoiding working-tree line-ending confusion and
self-reference.

The guarded runtime is:

- `scripts/run_sprint12_f12_stage_a_v9.py`
- `evaluation/sprint-12/harness/s12-f-12-stage-a-report.schema.v9.json`
- `evaluation/sprint-12/harness/s12-f-12-authorization.schema.v9.json`

The v9 arm record calls RM-40 over the same exact greedy semantic-pair domain
as `score_relations`, projects entity spans to `(start,end)`, reconciles finite
evidence reasons with `unsupported + missing`, rejects mismatches, and emits no
raw source/provider/validation data.

The runner defaults load the actual RM-42 v9 package, preregistration and
technical-freeze artifacts. A default-path regression exercises the real
working-tree lineage with exact-commit custody: unauthorized capture is zero,
the authorized mock path performs 144 captures, and retry/overwrite remain
closed.

## Preparation artifacts

- `evaluation/sprint-12/optimization/s12-f-12-rm42-execution-package.v9.json`
- `evaluation/sprint-12/optimization/s12-f-12-rm42-preregistration.v9.json`
- `evaluation/sprint-12/optimization/s12-f-12-rm42-technical-freeze.v9.json`
- `scripts/preflight_sprint12_f12_rm42.py`
- `evaluation/sprint-12/current-state-next-rm42.v1.json`

The zero-call preflight reports `F12_RM42_READY_ZERO_CALL`: 19 exact runtime
blobs, 9 preparation-evidence entries, prospective 144 provider calls and 96
relation branches, zero calls performed, zero retries, and no v9 output.

## Governance boundary

Preparation flags are open only for superseding lineage, preregistration,
technical freeze and execution package preparation. Preregistration and freeze
remain unissued; provider execution, new authorization, rerun/retry,
validation, held-out access, Stage B, selection and promotion remain closed.
RM-43 must perform the separate owner issuance review and a later exact-commit
provider authorization review before any provider call.
