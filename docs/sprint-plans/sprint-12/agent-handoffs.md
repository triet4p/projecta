# Sprint 12 Current Handoffs

**Status:** `CURRENT_AUTHORIZED_STAGE_A_EXECUTION_HANDOFF`

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
6. Update the task summary and plan only after executable evidence passes.

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

**Status:** complete; one exact run authorized and provider calls remain zero.

Independently verify RM-24 against the issued lineage and current-state index.
If every binding and boundary is exact, issue one new authorization for one
bounded development Stage A execution. Record all other permissions as false.
The issued authorization is
`evaluation/sprint-12/optimization/s12-f-12-rm25-authorization.v1.json`; its
owner review and current-state transition remain separate digest-bound records.

## Handoff C — One f12 Stage A execution

Start only after RM-25 issues a valid authorization. Run the guarded v6 runner
once: 144 provider calls, 96 relation branches, no retry and one final persist.
Score every declared denominator and slice, keep missing/invalid outcomes
fail-explicit, bind usage/pricing and retain sanitized diagnostics only.

The run itself does not authorize Stage B or selection. Close it as rejected if
any hard or semantic gate fails.

## Handoff D — Post-run decision

Review the immutable Stage A report against preregistered thresholds. A passing
result may only open a separate owner review for Stage B. A failing result must
be closed without rerun. No held-out access is allowed in either case.

## External-only work — custody and G6

S12-55/S12-85 and the G6 blinded review still require a real external
custodian, a frozen passing candidate and target-role human evidence. A normal
repository agent cannot satisfy those requirements by relabeling synthetic or
repository-reconstructible data.
