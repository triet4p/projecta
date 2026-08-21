# Sprint 12 Current State

**As of:** 2026-08-21

**Status:** `G5_F12_ISSUED_PROVIDER_AUTHORIZATION_PENDING`

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
snapshots. RM-23F subsequently issued that exact lineage through
`s12-f-12-rm23f-issuance-transition.v1.json`. The transition changes current
governance state without rewriting history.

## Current boundary

- G3.1-A, G3.1-B and G3.1-C are complete with their recorded scope limits.
- The f12 preregistration and freeze are issued for the exact v7 lineage.
- Provider execution is not authorized and no f12 provider call has occurred.
- No candidate is selected or frozen; no accuracy improvement is established.
- Validation and held-out data remain sealed. G6 is blocked by both candidate
  quality and external held-out custody.

## Next work

1. S12-RM-24 prepares a new exact authorization artifact without calling the
   provider.
2. S12-RM-25 independently reviews it and may authorize one bounded f12 Stage A
   run.
3. Only a passing, immutable Stage A report may open a separate Stage B review.

Historical gate packets remain valid evidence of what was decided at their
time; they are not current-state dashboards.
