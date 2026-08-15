# S12-73 — Prompt experiments

Executed the bounded supersession prompt experiment against dataset
`s12.corpus.atomic.v2` on 8 development cases with 3 baseline-prompt runs and
3 guarded-prompt runs. The guarded prompt was clean for schema/evidence and
improved entity, abstention and hallucination metrics on this slice.

The required 32-case follow-up was also executed across 3 guarded-prompt runs.
It remains a development result only: 3 `schema_invalid` failures occurred,
so no candidate was promoted or frozen. Link F1 is explicitly non-discriminating
because the selected cases contain zero positive link gold.

The v2 registry now records `s12-f-01` as
`COMPLETED_STABILITY_FAILED`. The registered one-run stopping rule was amended
to the executed 3x8 baseline/candidate protocol plus 3x32 follow-up; the
variance and artifact digests are recorded without rewriting the v1 registry.
G5 therefore records `candidateAvailable: true` with a failed hard-invariant
comparison, not candidate unavailability.

## Governance repair

The executable optimization validator now targets
`s12.experiment-registry.v2`. A regression test loads the persisted v2 registry
and calls `validate_registry()` directly, including the completed-but-failed
`s12-f-01` status. This checkpoint is therefore reviewable as immutable failed
evidence before any new model experiment is opened.

Artifacts:

- `evaluation/sprint-12/optimization/s12-73-prompt-supersession.v1.json`
- `evaluation/sprint-12/optimization/s12-73-prompt-followup-stability.v2.json`

## Testing

The registry self-test confirms prompt changes are development-only and change
exactly one dimension. Validation, full-corpus execution, candidate freeze and
held-out evaluation remain locked.
