# S12-81 — Candidate artifact freeze

Implemented digest-bound candidate freeze logic. Unselected or unexecuted
experiments return `NOT_FROZEN`; no candidate artifact is produced in this
blocked packet.

## Testing

Self-tests verify freeze refusal for an unexecuted experiment.
