# Sprint 12 Current Handoffs

**Status:** `CURRENT_F12_V9_EXECUTED_POST_RUN_OWNER_DECISION_HANDOFF`

Historical predecessor status: `CURRENT_F12_V9_ISSUED_AUTHORIZATION_HANDOFF`.

This revision supersedes the old baseline and generic-optimization handoffs.
Those tasks are complete or historically closed. Use
[Sprint 12 Current State](current-state.md) before accepting any assignment.

## Shared boundaries

1. Read `AGENTS.md`, `.agents/memory/decisions.md`, `docs/PLAN.md`, the Sprint
   12 plan, current-state index and the exact artifacts named below.
2. Preserve `humanEvidence: false`; do not claim accuracy improvement before a
   registered experiment passes.
3. Never persist credentials, raw source/provider payloads, held-out inputs or
   held-out gold.
4. Use only the exact RM-25 authorization for the single bounded Stage A run;
   it cannot be reused after execution starts.
5. Do not retry, overwrite output, open validation/held-out data, Stage B,
   selection or promotion unless a later owner decision explicitly permits it.
6. Preserve the immutable report and update the task summary/state only from
   executable evidence; a rejected run never opens downstream gates.

## Handoff A — RM-24 exact authorization preparation

**Status:** complete; provider calls were zero.

Prepare a new authorization artifact that binds all of the following exactly:

- `s12-f-12-rm23f-issuance-transition.v1.json` and its digest;
- `s12-f-12-rm23f-owner-review.v1.json` and its digest;
- execution commit `e047911e2e2d513f2b8751965dd702b2c1fe9d5a`;
- f12 v7 preregistration, execution package and freeze digests;
- authorization schema v2, report schema v6, runner v6 and runtime digests;
- output path, 144-call/96-branch bounds, no-retry/no-overwrite policy and the
  exact `$10.00` ceiling.

Run the zero-call preflight and authorization-schema tests. Completion of
RM-24 prepares evidence only and does not authorize execution.

## Handoff B — RM-25 owner authorization review

**Status:** complete; one exact run authorized and subsequently spent.

Independently verify RM-24 against the issued lineage and current-state index.
If every binding and boundary is exact, issue one new authorization for one
bounded development Stage A execution. Record all other permissions as false.
The issued authorization is
`evaluation/sprint-12/optimization/s12-f-12-rm25-authorization.v1.json`; its
owner review and current-state transition remain separate digest-bound records.

## Handoff C — One f12 Stage A execution

**Status:** complete; the guarded v6 runner ran once and the immutable report
was preserved.

The execution recorded 144 provider calls, 96 relation branches, 138
schema-valid responses, 144 usage-valid responses, zero retries, zero pricing
failures and `$0.00592500` cost. It failed closed on six schema-invalid
responses, 17 invalid-evidence findings, thresholds and slice gates.

The run did not authorize Stage B or selection and is rejected pending a
separate owner post-run decision. Any rerun requires a superseding package and
new owner authorization.

## Handoff D — Post-run decision

**Status:** complete. RM-27 closed f12 as `COMPLETED_REJECTED_NO_STAGE_B`.

The owner decision preserves the immutable report, records the spent
authorization and keeps rerun, Stage B, selection, validation and held-out
access closed.

## Handoff E — Offline schema/evidence remediation preparation

Analyze the six schema-invalid responses and 17 invalid-evidence findings from
sanitized development evidence. Distinguish candidate extraction/identity
failures from the passing gold-relations control and preserve the limits of the
sanitized report: exact malformed fields and sole provider/prompt causality are
not established.

This handoff may implement the approved finite diagnostic/remediation contract
and deterministic mock tests only. It does not authorize a superseding
execution lineage, provider call, rerun, validation, held-out access, Stage B
or selection.

**RM-28 status:** complete for offline preparation. The non-authoritative
remediation package records the proven arm/stage locations, the unsupported
evidence bucket with exact semantic matches and resolved endpoints, and finite
sanitized diagnostics. Exact malformed fields and provider causality remain
unknown. RM-29 approved offline implementation only; any execution-lineage
preparation still requires a separate owner review, and any run requires a new
authorization.

## Handoff F — RM-30 offline diagnostic implementation

**Status:** complete; RM-31 owner review approved offline lineage preparation.

RM-30 adds a versioned sanitized diagnostic/report schema, finite schema and
evidence reason classifiers, runtime-only materializer diagnostics and mock
tests. Historical unknowns remain fail-closed; no execution lineage is
prepared. RM-31 reviewed and approved only the next offline preparation gate.

## Handoff G — RM-31 approved superseding lineage preparation

**Status:** complete; RM-32 preparation complete, pending RM-33 owner issuance review.

RM-31 approved the corrected RM-30 implementation and authorized offline
preparation of a new exact-commit f12 preregistration, execution package and
technical-freeze packet. The historical v7 preregistration/freeze and its
144-call, zero-retry execution remain immutable facts. No new preregistration,
freeze, provider authorization or provider call exists.

RM-32 prepared the new versioned v8 lineage only. It preserved the RM-30
package/report/schema digests, reserved a distinct v8 report output, kept
issuance and downstream locks false, and stopped for RM-33 owner issuance
review.

## Handoff H — RM-32 prepared v8 lineage

**Status:** complete; superseded by the RM-33 issuance transition.

The non-authoritative v8 preregistration, execution package, technical freeze
and zero-call preflight are ready for review. No provider adapter or live
runner was invoked. The immutable preparation fields remain unissued in their
own snapshots; RM-33 separately issued the reviewed v8 preregistration and
freeze. A separate authorization remains mandatory before execution.

## Handoff I — RM-33/RM-34/RM-35 v8 authorization path

**Status:** RM-33 through RM-37 complete; RM-36 failed before report
persistence after one invocation; RM-37 closed v8 and opened offline diagnosis
and deterministic remediation preparation only.

RM-33 owner review and the digest-bound issuance transition remain immutable
history. RM-35 was authoritative for pre-execution v8 authority:
`preregistrationIssued=true`, `technicalFreezeIssued=true`,
`providerExecutionAuthorized=true`, `newAuthorizationIssued=true`,
`authorizedExecutions=1`, `authorizedProviderCalls=144`,
`providerCallsPerformed=0` before RM-36, and the v8 report is absent. Retry, overwrite,
validation, held-out, Stage B, selection and promotion permissions remain
false. The historical v7 execution remains separately issued/spent (144
provider calls, 96 relation branches, zero retries).

RM-34 prepared the exact v8 Stage A authorization offline at
`evaluation/sprint-12/optimization/s12-f-12-rm34-authorization-preparation.v1.json`.
Its preflight is `F12_RM34_PREPARED_ZERO_CALL`; it binds both RM-33 records,
the accepted RM33 custody erratum, exact runtime commit and all
package/freeze/runtime/output/cost digests. The CRLF/LF report-schema
discrepancy is reconciled to the canonical exact git blob. RM-35 has
independently reviewed and authorized one bounded execution; the v8 report is
still absent and provider calls performed remain zero.
The RM32 preflight binding is `sha256:492cc4c9815c168233039c096d5f7bc6121773a2b7f6f84443ed587fea1f8d3e`;
RM-34's own preflight is separately bound by working-tree preparation
evidence so a one-character tamper fails without self-referential hashing.
RM-35 authorized exactly one execution against the exact v8 commit/package/
freeze/runtime/output/cost boundary. RM-36 consumed that authority with the
single documented invocation; the runner failed after three captures before
persisting a v8 report. The exact execution fact is recorded in
`s12-f-12-rm36-execution-transition.v1.json`; its post-run current-state and
G5 packet were explicitly non-authoritative until RM-37 closure. RM-37 has now
closed the failed invocation; no retry or rerun is permitted.

## Handoff J — RM-36 execution and RM-37 post-run decision

RM-36 is complete. It ran the safe pre-execution preflight, then invoked the
exact v8 runner once using the immutable RM-35 authorization. The runner
failed at first-arm diagnostic reconciliation after three completed captures;
no v8 report or aggregate accounting was persisted. The authorization is
spent and non-reusable. RM-37 accepted the immutable execution fact and closed
v8 as failed before report persistence. Only offline reconciliation-failure
diagnosis and deterministic runtime-remediation preparation are permitted.

## Handoff K — RM-37 closure to RM-38 offline diagnosis

**Status:** RM-37 complete; RM-38 pending.

The authoritative current G5 packet is
`evaluation/sprint-12/optimization/g5-packet.v25.rm37-closure.json`. RM-37
accepts 3 calls and 3 responses as partial execution facts, preserves the
absent v8 report and incomplete accounting, and records the spent,
non-reusable authorization. RM-38 may inspect repository-visible runtime code,
sanitized execution facts and deterministic mocks to diagnose and prepare a
remediation. It may not call a provider, rerun v8, create a superseding
lineage, or open validation, held-out, Stage B, selection or promotion.

## Handoff L — RM-38 diagnosis to RM-39 owner review

**Status:** RM-38 complete; RM-39 pending.

RM-38 prepared a non-authoritative diagnosis and finite remediation proposal
from repository-visible code, sanitized RM-36/RM-37 facts and deterministic
mocks. The reproducer shows that `_evidence_reasons` counts non-exact/extra
relations while the arm materializer denominator counts only exact semantic
pairs; it also records the endpoint span-shape adapter gap. The hidden provider
payload remains unknown. RM-39 may review the proposal and decide whether
offline runtime implementation is allowed. No provider execution, retry,
rerun, superseding lineage, issuance, validation, held-out, Stage B, selection
or promotion is authorized by RM-38.

## Handoff M — RM-40 implementation to RM-41 owner review

**Status:** RM-40 complete; RM-41 pending.

RM-40 implemented the approved offline remediation in a new versioned module.
The implementation shares the exact semantic-pair domain with scoring,
projects entity spans to two coordinates and fails closed on malformed detail.
Its deterministic custody path performs zero provider calls while proving the
prospective 144-call/96-branch, one-persist, no-retry and no-overwrite rules.
RM-41 may review the package and safe tests. No lineage preparation, issuance,
provider execution, retry/rerun, validation, held-out, Stage B, selection or
promotion is authorized.

## Handoff N — RM-42 v9 lineage preparation to RM-43 issuance review

**Status:** complete; superseded by the RM-43 issuance transition.

RM-42 integrated RM-40 into the guarded v9 runtime at exact commit
`f81103b0b8f6c19a65b8d37ccfb0d08e8aeee11e`. The closed v9 report and
authorization schemas, deterministic mocked E2E, and exact Git-blob runtime
binding are present. The runner defaults load the actual RM-42 v9 package,
preregistration and freeze; the unissued preregistration, execution package and
technical freeze are preparation-only artifacts; the zero-call preflight passes
with 144/96 prospective custody, zero calls, zero retries and absent v9 output.

RM-43 reviewed and issued only the v9 preregistration/freeze through a separate
immutable transition. No provider execution, rerun, retry, validation,
held-out, Stage B, selection or promotion was authorized.

## Handoff O — RM-43 v9 issuance to RM-44/RM-45 authorization path

**Status:** Historical handoff; RM-43 issuance and RM-44 preparation are complete.

The authoritative current G5 packet is
`evaluation/sprint-12/optimization/g5-packet.v29.rm43-issuance.json`. RM-43
issued only the corrected v9 preregistration and technical freeze. The owner
review and issuance transition remain immutable and bind execution commit
`f81103b0b8f6c19a65b8d37ccfb0d08e8aeee11e` and the RM-42 package/freeze chain.
The RM-43 preflight is provider-neutral and reports zero calls; the v9 report
does not exist.

RM-44 prepared an exact v9 Stage A authorization offline at
`evaluation/sprint-12/optimization/s12-f-12-rm44-authorization-preparation.v1.json`.
Its `F12_RM44_PREPARED_ZERO_CALL` preflight binds the RM-43 owner/transition,
the RM-42 package/preregistration/freeze chain, exact execution commit
`f81103b0b8f6c19a65b8d37ccfb0d08e8aeee11e`, 19 Git-blob runtime bindings and
the runtime/provider/model/prompt/dataset contract. The prospective default
path mock is 144 calls and 96 relation branches, one persist, zero retries and
overwrite rejection; unauthorized provider calls and live invocations are
zero. RM-45 must independently review and issue that authorization before any
provider call. Do not reuse the spent RM-35 v8 authorization or revive the
failed v8 lineage. Validation, held-out access, Stage B, selection and
promotion remain closed.

## Handoff P — RM-44 preparation to RM-45 owner authorization review

**Status:** Historical handoff; RM-44 complete and RM-45 review is complete.

The RM-44 artifact is preparation-only and intentionally does not validate as
an issued v9 authorization because `providerExecutionAuthorized` and
`newAuthorizationIssued` remain false. Its own preflight is bound through
external `working_tree_sha256` preparation evidence, so a one-character
preflight tamper fails without circular self-hashing. The non-authoritative
next-state snapshot and v30 packet must not replace the authoritative RM-43
current-state index. RM-45 independently reviewed all bindings and issued one
bounded authorization. The v9 report remains absent until RM-46, and retry,
overwrite, validation, held-out, Stage B, selection and promotion permission
remain false.

## Handoff Q — RM-45 authorization to RM-46/RM-47 execution path

**Status:** historical execution handoff; RM-45 and RM-46 complete, RM-47
closure recorded below.

The authoritative current G5 packet is
`evaluation/sprint-12/optimization/g5-packet.v31.rm45-authorization.json`, and
the authoritative machine state is `evaluation/sprint-12/current-state.v1.json`.
RM-45 issued exactly one v9 development Stage A authorization through
`s12-f-12-rm45-authorization-transition.v1.json`. It binds execution commit
`f81103b0b8f6c19a65b8d37ccfb0d08e8aeee11e`, the RM-42 package/freeze, 19 exact
Git-blob runtime bindings, output v9 and the `$10.00` ceiling.

The read-only preflight
`scripts/preflight_sprint12_f12_rm45.py` returned
`F12_RM45_AUTHORIZED_ZERO_CALL_PRECHECK`. RM-46 invoked the exact runner once
and preserved the immutable v9 report with 144 calls, 96 relation branches,
zero retries and `$0.00599700` cost. The report is schema-valid but
hard-gate-rejected with 5 schema-invalid and 20 invalid-evidence findings.
The RM-46 transition and report were non-authoritative until RM-47 made the
separate owner post-run decision recorded in Handoff S. Do not retry,
overwrite output, inspect held-out data, open Stage B, select a candidate or
promote.

## Handoff R — RM-46 v9 execution to RM-47 owner decision

**Status:** complete; RM-47 closed v9 rejected with no Stage B.

The exact RM-45-authorized v9 command ran once against commit
`f81103b0b8f6c19a65b8d37ccfb0d08e8aeee11e`. The persisted report is
schema-valid and immutable at
`evaluation/sprint-12/optimization/s12-f-12-stage-a-report.v9.json`, digest
`sha256:84cb0667b8ee3469be5bdd4c3545a41012ba46bb07071508c41dca76fbf3761e`.
Its status is `COMPLETED_REJECTED_HARD_GATE` with failed schema-invalid,
invalid-evidence, threshold and slice gates. RM-47 accepted the immutable
execution evidence and closed the experiment rejected with no Stage B. The
schema-invalid count is 5 versus v6's 6, but invalid evidence is 20 versus
v6's 17; no quality-improvement claim follows. Authorization is spent; rerun,
retry, overwrite, validation, held-out, Stage B, selection, promotion and
downstream access are all closed.

## Handoff S — RM-47 closure to RM-48/RM-49 offline error analysis

**Status:** RM-51 Option C stop complete; RM-52 prepared offline; RM-53 pending owner review.

The authoritative current G5 packet is
`evaluation/sprint-12/optimization/g5-packet.v36.rm51-closure-only.json`, and the
authoritative machine state is `evaluation/sprint-12/current-state.v1.json`.
RM-47's owner decision and transition are immutable and close v9 as
`COMPLETED_REJECTED_NO_STAGE_B_OFFLINE_ERROR_ANALYSIS_PREPARATION_ONLY`.
Only offline v6/v9 error comparison and remediation-option preparation was
permitted. RM-48 produced
`evaluation/sprint-12/optimization/s12-f-12-rm48-error-comparison.v1.json`
and RM-49 approved the sequential Option A/Option B offline path. RM-50
implemented the closed diagnostic contract and deterministic parity fixtures in
`evaluation/sprint-12/optimization/s12-f-12-rm50-offline-remediation.v1.json`.
Option A stop criteria passed before Option B began. RM-50 did not modify the
live runtime, prepare a new lineage, call a provider, rerun, retry, overwrite
or open downstream gates. RM-51 rejected the package under Option C because
accounting fields remain mutable against immutable v6/v9 source reports;
provider experimentation and runtime integration are stopped. RM-52 prepared
the non-authoritative closure packet and prioritized backlog at
`optimization/s12-f-12-rm52-offline-closure.v1.json` and
`optimization/s12-f-12-rm52-error-backlog.v1.json`, binding v6/v9, the failed
three-call/no-report v8 fact, spent authorizations, RM-47/RM-51 and rejected
RM-50 artifacts. The v6/v9 reports remain immutable, v8 remains absent and no
quality-improvement or causality claim is established. RM-53 must review the
closure packet before acceptance.

## External-only work — custody and G6

S12-55/S12-85 and the G6 blinded review still require a real external
custodian, a frozen passing candidate and target-role human evidence. A normal
repository agent cannot satisfy those requirements by relabeling synthetic or
repository-reconstructible data.
