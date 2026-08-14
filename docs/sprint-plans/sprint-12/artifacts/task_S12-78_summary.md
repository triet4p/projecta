# S12-78 — Candidate selection

Implemented a fail-closed multi-metric selector that requires exactly one
passing development candidate and records that held-out data was not inspected.
Selection remains pending until scored runs exist.

## Testing

Self-tests verify no selection occurs when the baseline is unavailable.
