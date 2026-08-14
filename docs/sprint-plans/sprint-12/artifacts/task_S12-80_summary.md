# S12-80 — Hard-invariant regression

Implemented hard-invariant regression checks for safety, provenance, isolation,
review and fail-explicit behavior. A weakened candidate is rejected.

## Testing

The Phase F suite verifies a provenance regression returns `FAIL` and blocks
comparison.
