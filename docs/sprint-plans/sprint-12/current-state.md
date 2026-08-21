# Sprint 12 Current State

**As of:** 2026-08-22

**Status:** `G5_F12_CORRECTED_V9_LINEAGE_ISSUED_PROVIDER_AUTHORIZATION_PENDING`

RM-37 accepted the RM-36 execution fact and closed v8 as failed before report
persistence. RM-39 subsequently approved only offline runtime remediation and
deterministic regressions; RM-40 implemented them, RM-41 approved preparation
of a corrected lineage, RM-42 prepared v9, and RM-43 issued only its
preregistration and technical freeze. The authoritative machine state is
`evaluation/sprint-12/current-state.v1.json`.

The latest authoritative G5 packet is
`evaluation/sprint-12/optimization/g5-packet.v29.rm43-issuance.json`. RM-43's
immutable owner review and issuance transition issue only the corrected v9
preregistration and technical freeze. Provider execution remains behind the
separate RM-44/RM-45 authorization path.

This is the human-readable current-state index for Sprint 12. Machine consumers
must use `evaluation/sprint-12/current-state.v1.json`.

## State precedence

When versioned artifacts appear to disagree, apply this order:

1. the current-state index;
2. the latest explicit owner decision or transition record;
3. the current Sprint plan and current gate packet;
4. immutable preparation or execution artifacts;
5. historical gate snapshots.

The v7 f12 preregistration and technical freeze correctly retain their original
`PREPARED` and `NOT_ISSUED` fields because they are immutable preparation
snapshots. RM-23F issued that exact lineage, and RM-25 subsequently authorized
one bounded Stage A execution through
`s12-f-12-rm25-authorization-transition.v1.json`. The one authorized execution
is now recorded by
`s12-f-12-stage-a-execution-transition.v1.json`; these transitions change
current governance state without rewriting history or mutating the report.
RM-27 subsequently closed the experiment as rejected through
`s12-f-12-rm27-decision-transition.v1.json`.
RM-29 approved the RM-28 package for offline implementation and mock testing
only through `s12-f-12-rm29-approval-transition.v1.json`. RM-31 then approved
offline preparation of a new superseding lineage through
`s12-f-12-rm31-approval-transition.v1.json`; it did not issue a new
preregistration or technical freeze. RM-39 approved implementation of the
offline RM-38 remediation through
`s12-f-12-rm39-approval-transition.v1.json`; RM-40 did not prepare or issue a
new lineage.

## Current boundary

- G3.1-A, G3.1-B and G3.1-C are complete with their recorded scope limits.
- The historical f12 preregistration and freeze were issued for exact v7;
  current v8 preregistration and freeze are now separately issued by RM-33.
- Exactly one 144-call f12 development Stage A execution ran against execution
  commit `e047911e` and produced the immutable report v6.
- The report is schema-valid but rejected by hard gates (`schemaInvalid=6`,
  `invalidEvidence=17`), registered thresholds and slice gates. It records 144
  calls, 96 relation branches, 0 retries and `$0.00592500` cost.
- RM-27 closes the v7 execution as `COMPLETED_REJECTED_NO_STAGE_B`; RM-29
  approved finite diagnostic/remediation implementation, RM-31 approved
  lineage preparation, RM-33 issued v8 preregistration/freeze, RM-35
  authorized exactly one v8 execution, and RM-37 closed that invocation as
  failed before report persistence.
- Retry and output overwrite were not authorized and were not attempted. The
  RM-35 authorization was consumed by the single RM-36 invocation and cannot be
  reused.
- No candidate is selected or frozen; no accuracy improvement is established.
- Validation and held-out data remain sealed. G6 is blocked by both candidate
  quality and external held-out custody.

## Next work

1. RM-41 approved offline preparation of a corrected superseding lineage only.
2. RM-42 prepared the guarded exact-commit v9 runtime and RM-43 issued its
   preregistration and technical freeze through a separate transition. RM-44
   may prepare exact v9 authorization offline; RM-45 must review and issue it
   before any provider call.
3. Keep provider execution, new authorization, retry, overwrite, validation,
   held-out access, Stage B, selection and promotion closed.
4. Do not claim accuracy improvement, candidate quality, business quality or
   tenant readiness from this rejected run or the offline preparation.

Historical gate packets remain valid evidence of what was decided at their
time; they are not current-state dashboards.

## RM-28 offline preparation

RM-28 has prepared a non-authoritative next-state package from the immutable
sanitized report only. It records five predicted-entity Stage-1 schema-invalid
responses, one gold-entity Stage-2 schema-invalid response and 17 unsupported
evidence findings. The 17 findings are semantic exact matches with resolved
endpoints, while the gold-relations integrity control has zero materializer
failures. Exact malformed fields and provider payload causality remain unknown
because the report intentionally does not persist them.

The package and diagnostic contract are:

- `evaluation/sprint-12/optimization/s12-f-12-rm28-offline-remediation.v1.json`
- `evaluation/sprint-12/optimization/s12-f-12-rm28-diagnostic-contract.v1.json`

RM-29 approved this preparation for offline implementation only. No
preregistration, technical freeze, authorization, provider call, validation,
held-out access, Stage B or selection was opened by that historical decision.

## RM-30 offline implementation

RM-30 completed the approved implementation-only scope in a new versioned
diagnostic/report path. Historical schema and evidence findings remain
`validation_detail_unavailable` and `materializer_detail_unavailable`; no exact
historical cause was inferred. The implementation preserves typed-span identity,
endpoint denominators, reconciliation and raw-data exclusion, with 31
deterministic mock tests passing.

The non-authoritative next-state snapshot is
`evaluation/sprint-12/current-state-next-rm30.v1.json`. The authoritative
current G5 packet is now
`evaluation/sprint-12/optimization/g5-packet.v23.rm35-authorization.json`.

## RM-31 owner transition

RM-31 approved the corrected RM-30 implementation and authorized preparation
of a new exact, versioned superseding f12 lineage. The old v7 lineage remains
historical: its preregistration and technical freeze were issued and it spent
one 144-call execution with zero retries. No v7 authorization is reusable.

RM-33 completed the separate owner issuance review and issued only the exact
v8 preregistration and technical-freeze lineage through
`evaluation/sprint-12/optimization/s12-f-12-rm33-issuance-transition.v1.json`.
This issuance did not authorize a provider call. RM-35 later authorized one
bounded v8 execution. Current v8 has
`preregistrationIssued=true`, `technicalFreezeIssued=true`,
`providerExecutionAuthorized=true`, `newAuthorizationIssued=true`,
`authorizedExecutions=1`, `authorizedProviderCalls=144`, and
`providerCallsPerformed=0`. The v8 report is absent, and validation, held-out
access, Stage B, selection, promotion, retry and overwrite remain false. No
quality improvement or candidate claim is established.

## RM-32 lineage preparation (historical preparation snapshot)

RM-32 prepared a new v8 preregistration, execution package, technical freeze
and provider-neutral zero-call preflight. These artifacts are explicitly
immutable preparation artifacts reviewed by RM-33:

- `evaluation/sprint-12/optimization/s12-f-12-rm32-preregistration.v8.json`
- `evaluation/sprint-12/optimization/s12-f-12-rm32-execution-package.v8.json`
- `evaluation/sprint-12/optimization/s12-f-12-rm32-technical-freeze.v8.json`
- `scripts/preflight_sprint12_f12_rm32.py`

The v8 package binds the RM-31 transition, corrected RM-30 implementation and
closed v6 runner/schema contracts at exact digests. It reserves a new v8
report output and cannot overwrite the immutable v6 report. Its preparation
snapshots retain `preregistrationIssued=false` and
`technicalFreezeIssued=false`; the separate RM-33 transition is authoritative
for current issuance state.

## RM-33 owner issuance transition

RM-33 is complete. The owner review and transition are digest-bound and issue
only the reviewed v8 preregistration and technical freeze:

- `evaluation/sprint-12/optimization/s12-f-12-rm33-owner-review.v1.json`
  (`sha256:cb6a2965d8f107b50e01957c99366be34e0d1cfc7cc5ccf6fad684d0278e680c`)
- `evaluation/sprint-12/optimization/s12-f-12-rm33-issuance-transition.v1.json`
  (`sha256:62fb2d8a9b9acec0bd07440ea13943c1e81cf98bb38793392aa97110250b7025`)
- `evaluation/sprint-12/optimization/g5-packet.v23.rm35-authorization.json`

The historical v7 execution remains the sole issued/spent historical execution
(144 provider calls, 96 relation branches, zero retries). Current v8 has one
authorized execution, but no output and no provider calls performed. RM-35 is
complete; RM-36 is the next execution task and RM-37 must review its immutable
result.

## RM-34 exact authorization preparation

RM-34 prepared, but did not issue, the exact v8 Stage A authorization:

- `evaluation/sprint-12/optimization/s12-f-12-rm34-authorization-preparation.v1.json`
- `scripts/preflight_sprint12_f12_rm34.py`
- `evaluation/sprint-12/current-state-next-rm34.v1.json`
- `evaluation/sprint-12/optimization/g5-packet.v22.rm34-authorization-preparation.json`

The preparation binds the RM-33 owner review and issuance transition, exact
execution commit `005a35e3be3fbff40fcdae02dfdf79145c76934b`, the RM-32 v8
preregistration/package/freeze digests, the 22 runtime git blobs, runtime
configuration, model, prompt, provider adapter, dataset and v8 output path.
It proves zero calls at preparation and preserves the exact prospective mock
bounds of 144 calls, 96 relation branches, one persist, no retry and rejected
overwrite. RM-35 later reviewed this artifact without mutating it.

The RM32 preflight binding is the exact Git-blob digest
`sha256:492cc4c9815c168233039c096d5f7bc6121773a2b7f6f84443ed587fea1f8d3e`.
RM-34's own preflight is excluded from the 22 runtime blobs and is bound by
external preparation evidence using `working_tree_sha256`; its digest is
`sha256:ed78c94f97f9ed866a58779541d2bac6178adc0ab58741c40909c5c6413c5e63`.
The preflight fails closed on the former typo and on one-character tampering.

The RM33 owner custody erratum
`evaluation/sprint-12/optimization/s12-f-12-rm33-owner-custody-erratum.v1.json`
now reconciles the report-schema digest: the reviewed working-tree digest
`sha256:662e36911f16aa01c7eda920ec57c4fa9890ad47a4c4e4da2ef9a526482a17fc`
is CRLF-normalized content-equivalent to the canonical exact-commit blob
`sha256:c65a4f039d948e6f3a59750001e58199bfc98e57e2f2f3ac838070ef5f6f6ad5`.
RM-34 now records `ownerReviewReconciliationRequired=false` and binds the
canonical blob. RM-35 independently reviewed that preparation and issued one
bounded v8 authorization. The authorization binds the exact execution commit,
package, freeze, runtime, output and cost boundary; it permits 144 calls and
96 relation branches with no retry or overwrite.

## RM-35 v8 authorization

RM-35 is complete. The immutable owner review, authorization and transition
are:

- `evaluation/sprint-12/optimization/s12-f-12-rm35-owner-review.v1.json`
- `evaluation/sprint-12/optimization/s12-f-12-rm35-authorization.v8.json`
- `evaluation/sprint-12/optimization/s12-f-12-rm35-authorization-transition.v1.json`

The RM-35 pre-execution authorization snapshot recorded
`providerExecutionAuthorized=true`,
`newAuthorizationIssued=true`, `authorizedExecutions=1`,
`authorizedProviderCalls=144`, `providerCallsPerformed=0`, and
`stageAReportExists=false`. Retry, overwrite, validation, held-out, Stage B,
selection and promotion remain false. The safe pre-execution preflight is
`scripts/preflight_sprint12_f12_rm35.py`; it performs zero provider calls and
returns `F12_RM35_AUTHORIZED_ZERO_CALL_PRECHECK`.

The historical v7 execution remains separately spent and immutable at 144
provider calls, 96 relation branches and zero retries. No v7 authorization is
reused. RM-36 consumed the one v8 authorization with a single failed
invocation; RM-37 closed it as failed before report persistence. No quality or
tenant-readiness claim is established.

## RM-36 exact v8 execution

RM-36 is complete as an execution fact. After the documented zero-call
preflight, the exact runner was invoked once with the RM-35 authorization. It
exited with `F12StageAV8Error: evidence reason counts do not reconcile with arm
materializer failures` after three completed captures (3 calls attempted and 3
responses received), before the first arm record could persist aggregate
accounting or a report. The v8 output remains absent, so report schema and
quality-gate validation are not applicable. Cost and relation-branch totals are
unknown rather than zero; no retry occurred.

The immutable execution transition is
`evaluation/sprint-12/optimization/s12-f-12-rm36-execution-transition.v1.json`.
The post-run current-state and G5 packet are explicitly non-authoritative:

- `evaluation/sprint-12/current-state-next-rm36.v1.json`
- `evaluation/sprint-12/optimization/g5-packet.v24.rm36-execution-failure.json`

The authorization is spent and non-reusable. RM-37 is complete; RM-39 approved
offline implementation, RM-40 prepared the versioned remediation path and
RM-41 later reviewed the implementation. No provider call, retry, overwrite,
superseding-lineage preparation, validation, held-out access, Stage B,
selection or promotion is authorized.

## RM-37 owner closure

RM-37 independently accepted the immutable RM-36 failure fact and closed the
v8 execution as `COMPLETED_FAILED_BEFORE_REPORT_NO_RERUN_OFFLINE_REMEDIATION_PREPARATION_ONLY`.
The decision and transition are:

- `evaluation/sprint-12/optimization/s12-f-12-rm37-owner-decision.v1.json`
- `evaluation/sprint-12/optimization/s12-f-12-rm37-decision-transition.v1.json`

Only offline RM36 reconciliation-failure diagnosis and deterministic runtime
remediation preparation are permitted. Any future provider attempt requires a
corrected exact lineage, issuance review and separate owner authorization.

## RM-43 corrected v9 issuance

RM-43 is complete. The owner review and issuance transition are immutable and
digest-bound:

- `evaluation/sprint-12/optimization/s12-f-12-rm43-owner-review.v1.json`
  (`sha256:dd8d0210e8bed24b68fea64188fd8bb5cbb45c7a5962f4342b74b8811c9006a9`)
- `evaluation/sprint-12/optimization/s12-f-12-rm43-issuance-transition.v1.json`
  (`sha256:d57f040293ff0be4573d49e97a20cea9c838152b47945ee3fc01af2568637fdb`)
- `evaluation/sprint-12/optimization/g5-packet.v29.rm43-issuance.json`

RM-43 issues only the corrected v9 preregistration and technical freeze. The
runtime remains bound to execution commit
`f81103b0b8f6c19a65b8d37ccfb0d08e8aeee11e` and 19 exact Git blobs. The
provider-neutral issuance preflight passes with zero calls and zero retries;
the v9 output remains absent.

The historical v8 failure and immutable v6 report remain preserved. The v6
digest is
`sha256:419ac3c7aa7fad06287b231432d1ae167990ece45ca11ef94882fb6139569233`.
No quality improvement, candidate, validation, held-out, Stage B, selection,
promotion or tenant-readiness claim is established.

RM-44 has prepared the exact v9 Stage A authorization offline in the
non-authoritative artifact
`evaluation/sprint-12/optimization/s12-f-12-rm44-authorization-preparation.v1.json`.
Its zero-call preflight binds the RM-43 issuance, RM-42 package/preregistration/
freeze chain, exact execution commit and 19 Git-blob runtime bindings. The
prospective mock is 144/96 with one persist, zero retries and overwrite
rejection; no provider or live runner was called. This preparation does not
change the authoritative RM-43 state: provider execution and new
authorization remain false, v9 output remains absent, and RM-45 must
independently review and issue authorization before any provider execution.
