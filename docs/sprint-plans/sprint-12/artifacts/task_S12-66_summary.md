# S12-66 — Evidence report

Added digest-bound JSON and Markdown reports with evaluator/configuration
versions, per-case coverage, missing-output counts, hard-invariant status and a
raw-sensitive-data exclusion marker.

## Testing

The Phase E self-tests recompute the binding digest and assert that source text
does not appear in the serialized report.
