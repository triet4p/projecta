# S12-72 — Experiment registry

Implemented a versioned registry requiring hypothesis, development-only split,
baseline/candidate configuration digests, one metric target, stopping rule and
preserved governance artifacts.

## Testing

Phase F self-tests validate the five experiment dimensions and reject invalid
split or multi-dimension changes.
