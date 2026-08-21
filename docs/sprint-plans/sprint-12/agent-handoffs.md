# Sprint 12 Current Handoffs

**Status:** `CURRENT_F12_V8_ISSUED_PROVIDER_AUTHORIZATION_HANDOFF`

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

## Handoff I — RM-33 v8 issuance and RM-34/RM-35 authorization path

**Status:** RM-33 complete; RM-34 preparation complete; RM-35 pending.

RM-33 owner review and the digest-bound issuance transition are authoritative
for current v8 issuance only. `preregistrationIssued=true` and
`technicalFreezeIssued=true`; `providerExecutionAuthorized=false`,
`newAuthorizationIssued=false`, the v8 report is absent, and all validation,
held-out, Stage B, selection and promotion permissions remain false. The
historical v7 execution remains the sole issued/spent execution (144 provider
calls, 96 relation branches, zero retries).

RM-34 prepared the exact v8 Stage A authorization offline at
`evaluation/sprint-12/optimization/s12-f-12-rm34-authorization-preparation.v1.json`.
Its preflight is `F12_RM34_PREPARED_ZERO_CALL`; it binds both RM-33 records,
exact runtime commit and all package/freeze/runtime/output/cost digests. The
preparation records a report-schema digest discrepancy between the immutable
RM-33 review and the exact execution blob, so RM-35 must reconcile it before
issuing authorization. No provider call or live runner invocation is allowed.

## External-only work — custody and G6

S12-55/S12-85 and the G6 blinded review still require a real external
custodian, a frozen passing candidate and target-role human evidence. A normal
repository agent cannot satisfy those requirements by relabeling synthetic or
repository-reconstructible data.
