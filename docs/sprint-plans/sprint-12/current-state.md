# Sprint 12 Current State

**As of:** 2026-08-22

**Status:** `G5_F12_V8_LINEAGE_ISSUED_PROVIDER_AUTHORIZATION_PENDING`

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
preregistration or technical freeze.

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
  lineage preparation, and RM-33 issued v8 preregistration/freeze only.
- Retry and output overwrite were not authorized and were not attempted. The
  authorization is spent and cannot be reused.
- No candidate is selected or frozen; no accuracy improvement is established.
- Validation and held-out data remain sealed. G6 is blocked by both candidate
  quality and external held-out custody.

## Next work

1. Prepare the exact v8 Stage A authorization offline under RM-34.
2. Keep provider execution, validation, held-out access, Stage B, selection
   and promotion closed pending RM-35 owner authorization review.
3. Do not claim accuracy improvement, candidate quality, business quality or
   tenant readiness from this rejected run.

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
`evaluation/sprint-12/optimization/g5-packet.v21.json`.

## RM-31 owner transition

RM-31 approved the corrected RM-30 implementation and authorized preparation
of a new exact, versioned superseding f12 lineage. The old v7 lineage remains
historical: its preregistration and technical freeze were issued and it spent
one 144-call execution with zero retries. No v7 authorization is reusable.

RM-33 completed the separate owner issuance review and issued only the exact
v8 preregistration and technical-freeze lineage through
`evaluation/sprint-12/optimization/s12-f-12-rm33-issuance-transition.v1.json`.
This issuance does not authorize a provider call. For current v8,
`preregistrationIssued=true` and `technicalFreezeIssued=true`, while
`providerExecutionAuthorized=false`, `newAuthorizationIssued=false`, the v8
report is absent, and validation, held-out access, Stage B, selection and
promotion remain false. No quality improvement or candidate claim is
established.

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
- `evaluation/sprint-12/optimization/g5-packet.v21.json`

The historical v7 execution remains the sole issued/spent execution (144
provider calls, 96 relation branches, zero retries). Current v8 has no
provider authorization, no new authorization, no output and no provider
calls. RM-34 may prepare the exact v8 Stage A authorization offline; RM-35
must review it before any execution.
