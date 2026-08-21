# Sprint 12 Current State

**As of:** 2026-08-21

**Status:** `G5_F12_CLOSED_REJECTED_OFFLINE_REMEDIATION_PREPARATION_ONLY`

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

## Current boundary

- G3.1-A, G3.1-B and G3.1-C are complete with their recorded scope limits.
- The f12 preregistration and freeze are issued for the exact v7 lineage.
- Exactly one 144-call f12 development Stage A execution ran against execution
  commit `e047911e` and produced the immutable report v6.
- The report is schema-valid but rejected by hard gates (`schemaInvalid=6`,
  `invalidEvidence=17`), registered thresholds and slice gates. It records 144
  calls, 96 relation branches, 0 retries and `$0.00592500` cost.
- RM-27 closes f12 as `COMPLETED_REJECTED_NO_STAGE_B`; offline remediation
  preparation is the only newly authorized scope.
- Retry and output overwrite were not authorized and were not attempted. The
  authorization is spent and cannot be reused.
- No candidate is selected or frozen; no accuracy improvement is established.
- Validation and held-out data remain sealed. G6 is blocked by both candidate
  quality and external held-out custody.

## Next work

1. Prepare an offline schema/evidence remediation using repository-visible
   development evidence and sanitized diagnostics only.
2. Keep provider execution, validation, held-out access, Stage B, selection and
   promotion closed; any rerun requires a superseding governed lineage and new
   authorization.
3. Do not claim accuracy improvement, candidate quality, business quality or
   tenant readiness from this rejected run.

Historical gate packets remain valid evidence of what was decided at their
time; they are not current-state dashboards.
