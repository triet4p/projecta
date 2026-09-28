# Sprint 12 Current State

**As of:** 2026-08-24

**Status:** `F_RF_POC_BASELINE_ACCEPTED_DENSE_HARD_V4_FAILED_STRATEGY_REDESIGN_REQUIRED`

RM-37 accepted the RM-36 execution fact and closed v8 as failed before report
persistence. RM-39 subsequently approved only offline runtime remediation and
deterministic regressions; RM-40 implemented them, RM-41 approved preparation
of a corrected lineage, RM-42 prepared v9, and RM-43 issued only its
preregistration and technical freeze. The authoritative machine state is
`evaluation/sprint-12/current-state.v1.json`.

The latest authoritative G5 packet is
`evaluation/sprint-12/optimization/g5-packet.v36.rm51-closure-only.json`.
RM-47's immutable owner decision and transition close the single RM-45-
authorized v9 Stage A as rejected with no Stage B. RM-51 rejected the RM-50
accounting implementation under Option C and stopped provider experimentation;
RM-53 then accepted the RM-52 offline closure and backlog custody. The v6 and
v9 reports are immutable and the failed v8 report remains absent. RM-54
accepted the revised human-first extraction design and RM-55 accepted the
versioned SourceVersion/source-receipt contract. RM-56 accepted the versioned
TextAnchor coordinate contract; RM-57 accepted the per-item validation and
quarantine boundary; RM-58 accepted the confirmed-entity relation gate; RM-59
accepted deterministic evidence selection, and
RM-60 accepted the constrained relation contract; RM-61 accepted the durable
append-only review decision receipt contract, and RM-62 accepted the human-first
review workbench contract. RM-63 accepted the disabled-by-default approved-only
assertion materialization boundary. RM-64 accepted versioned invalidation and
transactional rebuild with no stale current projection. RM-65 accepted the
append-only correction-burden telemetry boundary; RM-66 accepted the offline
adversarial/default-path gate, and RM-67 accepted the closed-world human
correction-burden contract for the RM-68 gate. The v5 internal source-only
agent-proxy PoC remains historical bounded evidence only. The immutable
dense-hard v1 through v4 evaluations are separate diagnostics; v4 fails both
stratified gates and requires the finite offline strategy-redesign backlog. No
generalized quality or low-correction claim is permitted. Provider execution,
rerun, retry, external validation, held-out access, selection and promotion
remain closed.

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
2. RM-42 prepared the guarded exact-commit v9 runtime, RM-43 issued its
   preregistration and technical freeze, and RM-45 issued one exact v9 Stage A
   authorization. RM-46 executed it exactly once; RM-47 reviewed the immutable
   post-run fact and closed the run rejected with no Stage B.
3. Keep retry, overwrite, validation, held-out access, Stage B, selection and
   promotion closed.
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
rejection; no provider or live runner was called. Its preparation-only fields
remain immutable historical custody; RM-45 later issued the separate
authorization recorded below.

## RM-45 exact v9 authorization

RM-45 is complete. The owner review, authorization and transition are separate
immutable records:

- `evaluation/sprint-12/optimization/s12-f-12-rm45-owner-review.v1.json`
  (`sha256:8f5e8f55d7893756a764e334915de7317038016ee25b87afbd80884a4c75d1bf`)
- `evaluation/sprint-12/optimization/s12-f-12-rm45-authorization.v9.json`
  (`sha256:ad84eaad496458cc2f5064be59016d7e2497aa4d3ad898e807cf8d496d77a0c8`)
- `evaluation/sprint-12/optimization/s12-f-12-rm45-authorization-transition.v1.json`
  (`sha256:68a69e313e203aa7d5e88209efacf3d7b8eab293a2d015810f0953fdb0dc6234`)

The authorization binds execution commit
`f81103b0b8f6c19a65b8d37ccfb0d08e8aeee11e`, the RM-42 package/freeze, 19
exact Git-blob runtime bindings, output v9 and the `$10.00` ceiling. It
permits exactly one 144-call development Stage A execution with 96 relation
branches, no retry and no overwrite. Issuance and the read-only preflight
performed zero provider calls; the v9 report was absent before RM-46 consumed
the authorization.

The RM-47-era historical G5 packet was
`evaluation/sprint-12/optimization/g5-packet.v33.rm47-closure.json`; it was
authoritative for that closure decision at the time, but it is not the current
packet. The current packet remains the v36 RM-51 closure-only packet named in
the header above.
RM-47 has closed the exact v9 command's schema-valid but hard-gate-rejected
report at `evaluation/sprint-12/optimization/s12-f-12-stage-a-report.v9.json`
with digest `sha256:84cb0667b8ee3469be5bdd4c3545a41012ba46bb07071508c41dca76fbf3761e`.
The immutable RM-46 execution transition and RM-47 owner decision/transition
bind 144/144 responses, 96 branches, zero retries and `$0.00599700`; five
schema-invalid and 20 invalid-evidence findings fail hard, threshold and
slice gates. Compared with v6, schema-invalid decreased from 6 to 5 while
invalid evidence increased from 17 to 20, so no quality-improvement claim is
established.

Only offline v6/v9 error-analysis preparation was permitted. RM-48 prepared
the sanitized comparison and remediation options at
`evaluation/sprint-12/optimization/s12-f-12-rm48-error-comparison.v1.json`;
RM-49 approved the sequential offline diagnostic-hardening and parity-fixture
path, and RM-50 completed both stages after Option A stop criteria passed. RM-51
rejected the package because accounting mutations can detach it from immutable
v6/v9 evidence. RM-52 prepared the offline closure custody and prioritized
error backlog, and RM-53 accepted that custody under the delegated owner-review
boundary. RM-54 accepted the revised human-first framework for RM-55 contract
definition only. RM-55 accepted the SourceVersion/source-receipt contract;
RM-56 is now the sole permitted action.
Remediation implementation, lineage preparation, provider/new authorization,
rerun, retry, validation, held-out access, Stage B, selection, promotion and
downstream access remain closed. The v6 and v9 reports remain immutable and
the failed v8 report remains absent. No Sprint 12, G5 or G6 completion or
quality claim follows.

## RM-52 closure packet and backlog

The non-authoritative RM-52 artifacts are
`evaluation/sprint-12/optimization/s12-f-12-rm52-offline-closure.v1.json` and
`evaluation/sprint-12/optimization/s12-f-12-rm52-error-backlog.v1.json`.
They bind v6, the three-call/no-report v8 execution fact, v9, spent v7/v8/v9
authorizations, RM-47/RM-51 decisions and rejected RM-50 artifacts. Known cost
is `$0.01192200`; v8 aggregate cost is unknown because no report persisted.
The backlog distinguishes bounded offline fixes, residual product-quality
failures, tooling/governance lessons and external custody blockers.

## RM-53 closure decision

RM-53 accepted the immutable RM-52 closure packet and backlog through the
delegated Codex review records:

- `evaluation/sprint-12/optimization/s12-f-12-rm53-owner-decision.v1.json`
- `evaluation/sprint-12/optimization/s12-f-12-rm53-decision-transition.v1.json`

This is an offline custody decision only. It makes no human business-quality
claim and authorizes no implementation, provider execution, runtime work,
validation, held-out access, Stage B, selection or promotion. RM-54's separate
design review is closed and RM-55's SourceVersion/source-receipt contract is
accepted. RM-56 remains pending for the text-anchor coordinate contract.

## RM-54 human-first design disposition

RM-54 revised and accepted the human-first extraction design for RM-55 contract
definition only. The review binds the unchanged v1 source and revised v2
design at:

- `docs/sprint-plans/sprint-12/human-first-extraction-framework.v1.md`
- `docs/sprint-plans/sprint-12/human-first-extraction-framework.v2.md`
- `evaluation/sprint-12/optimization/s12-f-12-rm54-design-review.v1.json`

The v2 contract resolves source/version, coordinate, lifecycle, project
isolation, evidence, review receipt, atomic materialization, inference,
telemetry and prompt-injection defaults. Human-study parameters remain
owner-gated RM-67/RM-68 work. No ontology production change, implementation,
provider/runtime execution, validation, held-out access, Stage B, selection,
promotion or release is authorized.

## RM-55 SourceVersion/source-receipt contract

The extraction boundary now exposes the versioned opt-in contract and focused
tests:

- `apps/api/src/projecta_api/extraction/source_version.py`
- `apps/api/tests/test_source_version.py`

The contract performs strict UTF-8 decoding, deterministic CRLF/CR-to-LF
canonicalization without Unicode normalization, original/canonical SHA-256
digests, opaque project/artifact/version IDs, optional parent lineage,
retention metadata, deterministic safe receipts and fail-closed replay/fork,
project-scope and tamper verification. Receipts contain no raw source or raw
project/artifact identifiers. Existing extraction remains compatible because
SourceVersion creation is explicit opt-in; RM-56's TextAnchor contract,
RM-57's per-item validation/quarantine boundary, RM-58's confirmed-entity
relation gate, and RM-59's deterministic evidence selection are accepted;
RM-60's constrained relation contract and RM-61's durable receipts are
accepted; RM-62 is the next gate.

## RM-56 TextAnchor coordinate contract

The extraction boundary now exposes the explicit opt-in
`apps/api/src/projecta_api/extraction/text_anchor.py` contract and focused
tests at `apps/api/tests/test_text_anchor.py`. Anchors bind a verified
SourceVersion and canonical content, use zero-based half-open Unicode
code-point offsets, verify the exact quote and digest, and derive original
code-point/UTF-8-byte plus UTF-16 display mappings across CRLF/CR-to-LF
canonicalization. Repeated quotes require an explicit occurrence; missing,
stale, tampered, malformed, unsupported, or ambiguous inputs fail closed with
finite reasons. Safe serialization excludes raw quotes and content. Existing
extraction behavior remains unchanged unless this contract is explicitly
requested. RM-57 through RM-61 are accepted and RM-62 is the sole next permitted action; no provider, runtime,
ontology, validation, held-out, Stage B, selection, promotion, or release
authority is opened.

## RM-57 Per-item validation and quarantine boundary

The explicit opt-in application boundary is implemented in
`apps/api/src/projecta_api/extraction/item_validation.py` with focused tests at
`apps/api/tests/test_item_validation.py`. It independently classifies entity,
entity-link, relation, and evidence items, preserving input order and unrelated
valid results. Outcomes are finite (`contract-valid`, `review-pending`,
`abstained`, `quarantined`, or `stale`); unknown kinds, statuses, reasons,
schema fields, malformed payloads, project/source/anchor mismatches, and stale
content fail closed. Only a `contract-valid` result with reason `VALID` may
pass the downstream materialization guard. Safe results contain no raw item
payload or quote. RM-58 through RM-61 are accepted and RM-62 is the sole next permitted action; this gate opens no
provider, runtime, ontology, relation, validation, held-out, Stage B, selection,
promotion, or release authority.

## RM-58 Confirmed-entity relation gate

The explicit opt-in relation boundary is implemented in
`apps/api/src/projecta_api/extraction/confirmed_entity_gate.py` with focused
tests at `apps/api/tests/test_confirmed_entity_gate.py`. The in-memory registry
issues deterministic opaque project-scoped handles only from contract-valid or
review-confirmed entity validation results under the active SourceVersion.
Relation requests resolve both handles server-side and allow only released
entity types and predicates. Model/global/free-text IDs, unknown or malformed
handles, cross-project/source-version access, unconfirmed or stale handles,
type/version mismatches, self-relations, duplicates, and conflicting replay
are rejected fail-closed. Safe serialization excludes candidate keys and raw
payloads. RM-59 through RM-61 are accepted and RM-62 is the sole next permitted action; no provider, runtime,
ontology, evidence-selection, held-out, Stage B, selection, promotion, or
release authority is opened.

## RM-59 Deterministic relation evidence selection

The explicit opt-in selector is implemented in
`apps/api/src/projecta_api/extraction/relation_evidence_selection.py` with
focused tests at `apps/api/tests/test_relation_evidence_selection.py`. It
verifies SourceVersion custody, builds deterministic canonical sentence/clause
source blocks, and selects the smallest valid boundary containing confirmed
endpoint anchors and an optional or required trigger anchor. Cross-sentence,
missing, stale, tampered, out-of-block, unsupported, and equally ranked
boundaries fail closed to finite abstain/review/quarantine outcomes. The result
binds source version, relation handles, anchor digests, trigger digest, and
block digest while excluding raw source/evidence text. RM-59 and RM-60 are
accepted and RM-61 is implemented; RM-62 is the sole next permitted action; no provider, runtime, ontology,
constrained-relation, held-out, Stage B, selection, promotion, or release
authority is opened.

## RM-61 Durable review decision receipts

The explicit opt-in review boundary is implemented in
`apps/api/src/projecta_api/extraction/review_receipts.py` with focused tests at
`apps/api/tests/test_review_receipts.py`. It records confirm, edit, reject and
abstain actions as append-only receipts in the existing PostgreSQL operational
persistence boundary, with an in-memory adapter only for deterministic unit
tests. Receipts bind project scope, actor authorization context, item kind and
opaque-handle digest, candidate/source revisions, constrained contract and
evidence digests, predecessor digest, timestamp, idempotency digest and receipt
digest. Optimistic concurrency, source/candidate staleness, cross-project
scope, unauthorized actors, and same-key/different-body replays fail closed;
exact replays are idempotent and do not mutate history. Storage and safe output
exclude raw source/provider payloads and sensitive identifiers. These receipts
record explicit authorized reviewer actions and do not claim human approval or
materialization. RM-62 is the sole next permitted action; provider, runtime,
ontology, held-out, Stage B, selection, promotion and release authority remain
closed.

## RM-62 Human-first review workbench

The authorized same-origin Application API route
`GET /v1/projects/{handle}/candidates/{candidateHandle}/review-detail` projects
one selected, project-scoped item into `review-workbench.v1`. The React
`ReviewScreen` renders source text and exact code-point/UTF-16 anchor mappings,
endpoint/trigger/evidence highlights, source/candidate revisions, finite
uncertainty/quarantine/abstain states, proposal-versus-edit values, and receipt
state before any action. Confirm, edit, reject, and abstain are explicit
controls; stale, quarantined, unavailable-evidence, and terminal-receipt states
fail closed, with no hidden auto-confirm or bulk relation approval. Focused API
and UI contract tests cover valid and invalid anchors plus decision guards. RM-63
is the sole next permitted action; this gate opens no provider, runtime,
ontology, materialization, held-out, Stage B, selection, promotion, or release
authority.

## RM-63 Approved-only assertion materialization

RM-63 adds the versioned `ApprovedAssertionPlan` and a separate Semantic Core
materialization boundary. It requires exact project/source/candidate revisions,
review-receipt and evidence digests, released ontology/contract versions, an
optimistic asserted-graph revision, provenance activity, and an idempotency key.
Only confirmed candidates with a matching safe review-binding record can cross
the boundary. Asserted facts, candidate lifecycle updates, provenance, and the
idempotency receipt are committed in one Jena transaction; exact replays are
read-only and failures roll back all writes. Materialization is disabled by
default and the test-only opt-in does not authorize production enablement,
provider execution, ontology changes, or downstream inference. RM-64 is
accepted; RM-65 accepted correction-burden telemetry and RM-66 was the next
permitted action at that transition.

## RM-64 Inference invalidation and rebuild

RM-64 adds `inference-rebuild-plan.v1` and a disabled-by-default Semantic Core
boundary tied to the asserted graph revision, SourceVersion identity/revision
and digest, released ontology version, M4 rule version, rebuild activity, and
idempotency key. Correction, rejection, source supersession, assertion
revision, rule change, and ontology change are finite invalidation causes that
mark the current snapshot stale before rebuild. Rebuild stages a fresh
projection, validates released M4 SHACL, and publishes the current snapshot
only after the complete projection and provenance transaction succeeds.
Previous projections remain historical, stale/current state is explicit, exact
replays are read-only, and failures preserve asserted truth. No ontology,
provider, production runtime, or downstream telemetry authority is opened.
RM-65 is accepted; RM-66 is accepted and RM-67 is accepted for the closed-world
contract. The internal v5 agent-proxy PoC is separately accepted only for
development diagnostics.

## RM-65 Correction-burden telemetry

RM-65 adds `correction-burden.v1` append-only events to the existing PostgreSQL
operational persistence boundary. Events retain only opaque project/item/
assertion/source/review/materialization/inference digests, allowlisted
correction categories and dimensions, finite lifecycle outcomes, edit counts,
and bounded latency. The reducer derives summaries from immutable events and
accepts no mutable totals, reconciliation flags, free-form reasons, raw source,
quotes, provider payloads, secrets, credentials, or sensitive identifiers.
Idempotency, conflict, project isolation, and an explicit review lifecycle hook
are covered; PostgreSQL integration remains an RM-66 environment gate.
No human-study threshold, provider execution, ontology change, or production
enablement is claimed. RM-66 was the next permitted action at this transition.
See `artifacts/task_S12-RM-65_summary.md` for the bounded implementation and
validation record.

## RM-66 Offline adversarial and default-path testing

RM-66 accepts deterministic offline tests across RM-55 through RM-65. The gate
covers Unicode/newline/UTF-16 coordinates, repeated and nested mentions,
smallest evidence containment and cross-block failures, stale/tampered source
and receipts, review concurrency/replay/conflict, RM-65 accounting mutation and
append-only digests, prompt-injection quarantine as data only, project
isolation, and legacy default paths with no implicit source/review/
materialization/inference/telemetry enablement. Semantic Core tests preserve
asserted truth and current-projection state across disabled, stale, replay, and
failure paths. The gate records zero provider calls and verifies immutable v6/v9
digests and absent v8. PostgreSQL Compose execution is an explicit environment
skip when Docker is unavailable, not a pass. No human-study, provider,
ontology, production, held-out, Stage B, selection, promotion, or release
authority is opened. RM-67 is the sole next permitted action.
See `artifacts/task_S12-RM-66_summary.md` for the evidence record.

## RM-67 Human correction-burden evaluation contract

RM-67 accepts an owner-delegated, versioned closed-world contract for the future
RM-68 preregistration gate. It freezes at least 70% accepted without semantic
correction, at least 85% unchanged/minor, at least 30% median review-time
reduction against a counterbalanced same-reviewer manual baseline, median review
time at most 45 seconds, p90 at most 90 seconds, mean semantic edits at most 2
per reviewed item, zero unsupported finalized assertions, and agreement at least
0.80 where applicable. It also freezes deterministic correction taxonomy
precedence, timing/pause rules, denominators, missing/rejection/abstention and
adjudication handling, confidence-interval reporting, three target roles, twelve
scenarios, thirty-six reviewer records, language/journey/threat/ambiguity slices,
and the matched manual baseline.

The JSON contract, strict schema, source digests, and focused mutation-failure
test are recorded at:

- `evaluation/sprint-12/harness/s12-rm67-human-correction-burden-contract.v1.json`
- `evaluation/sprint-12/harness/s12-rm67-human-correction-burden-contract.schema.v1.json`
- `docs/sprint-plans/sprint-12/human-correction-burden-contract.v1.md`
- `artifacts/task_S12-RM-67_summary.md`

No independent human execution, timing baseline, agreement, or custody claim
exists; the v5 result is primary-agent proxy evidence only. RM-53 through RM-67
are complete for development contracts, implementation, and offline gates.
Phase F-RF is
`F_RF_POC_BASELINE_ACCEPTED_DENSE_HARD_V4_FAILED_STRATEGY_REDESIGN_REQUIRED`
for the internal baseline. The v5 result remains historical bounded evidence
only and does not support a generalized quality or low-correction claim.
Dense-hard v1 through v4 are separate diagnostics; v4 fails both utility and
safety gates. Remediation is limited to the finite offline strategy-redesign
backlog and requires new authority before any fresh benchmark or candidate.
RM-68 remains accepted only for that internal scope; external validation
remains closed and the historical external packet remains blocked/non-
preregistration.
No provider/runtime, ontology, materialization, inference, production,
selection, promotion, or release authority is granted.

## RM-68 Internal PoC acceptance and historical external packet

RM-68 remains accepted only as a historical bounded v5 baseline under
`F_RF_POC_BASELINE_ACCEPTED_DENSE_HARD_V4_FAILED_STRATEGY_REDESIGN_REQUIRED`
for the
versioned internal source-only candidate and primary-agent proxy review. The
accepted v5 review records 60 supported finalized-for-review assertions, zero
unsupported assertions, 12/12 unchanged items, and zero provider calls; timing
and independent agreement are unmeasured and not claimed. Dense-hard v1
through v4 are authoritative separate diagnostics; v4 fails both stratified
gates, so no generalized “good enough” or low-correction claim follows. The
finite offline strategy-redesign backlog requires new authority before any
fresh cases. The historical
preparation packet remains `DRAFT_BLOCKED_EXTERNAL_CUSTODY`, not an issued
preregistration. It records the absence of external custody and remains the
authoritative boundary for any later external study.

See `artifacts/task_S12-RM-68_summary.md` and
`rm68-preregistration-blocked.v1.md`. A later external or business claim would
require new owner authority, an external custody receipt and
non-reconstructibility attestation, opaque dataset/manifest/payload digests,
frozen evaluable candidate/configuration/evaluator digests, and owner-approved
protocol authority. No external-study action is implied by the internal PoC.

## Dense-hard v1 evaluation

S12-DH-01 through S12-DH-03 are complete for the immutable synthetic benchmark
evidence. The frozen v1 candidate evaluates to 0 unchanged, 0 minor, 8 major,
2 reject, and 14 abstain items; 74 semantic edits (mean 3.0833333333), entity
F1 0.5685279188, relation F1 0.1758241758, and 74/138 unsupported finalized
assertions. The RM-67 edit-burden gate therefore fails. Remediation is pending
new authority and must use fresh dense-hard v2 cases; v1 source, gold,
manifest, candidate, and evaluation artifacts are immutable and may not be
reused. Provider, human, external, held-out, production, selection, promotion,
and release claims remain closed.

## Successor / Closure Note — 2026-08-31

This Sprint 12 index remains the historical authoritative record of the frozen
dense-hard v1--v4 diagnostics and the v5 easy baseline. The owner-approved
active successor is [Sprint 13 Evidence-first Assisted
Authoring](../sprint-13.md), beginning with human-authored structured entity
capture and a zero-model fallback, then optional bounded local suggestions and
controlled relations. The machine snapshot is intentionally unchanged: its
`DENSE_HARD_V4_STRATEGY_REDESIGN_REQUIRES_NEW_AUTHORITY` next action records the
last Sprint 12 gate boundary, while Sprint 13 is the active product plan. This
closure note does not authorize R6/R7, provider execution, human/business
validation, held-out access, production, selection, promotion or release.
