# Sprint 12 Current State

**As of:** 2026-08-21

**Status:** `G5_F12_STAGE_A_AUTHORIZED_PENDING_EXECUTION`

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
`s12-f-12-rm25-authorization-transition.v1.json`. These transitions change
current governance state without rewriting history.

## Current boundary

- G3.1-A, G3.1-B and G3.1-C are complete with their recorded scope limits.
- The f12 preregistration and freeze are issued for the exact v7 lineage.
- Exactly one 144-call f12 development Stage A execution is authorized against
  execution commit `e047911e`; no provider call has occurred yet.
- Retry and output overwrite are not authorized. The authorization is
  single-use and is spent when execution starts.
- No candidate is selected or frozen; no accuracy improvement is established.
- Validation and held-out data remain sealed. G6 is blocked by both candidate
  quality and external held-out custody.

## Next work

1. Execute the exact authorized f12 development Stage A once, with at most 144
   provider calls and 96 relation-branch outputs.
2. Preserve the report without retry or overwrite and record actual failures,
   usage and cost truthfully.
3. Only a passing, immutable Stage A report may open a separate Stage B review.

Historical gate packets remain valid evidence of what was decided at their
time; they are not current-state dashboards.
