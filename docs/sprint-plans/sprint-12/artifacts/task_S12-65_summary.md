# S12-65 — Operational metrics

Added latency P50/P95, token usage, cost, failure-class and accepted-candidate
cost aggregation for configuration/slice-tagged records.

## Testing

Operational functions return an explicit not-available state for empty input;
the shared Phase E contract suite exercises the edge-case policy.
