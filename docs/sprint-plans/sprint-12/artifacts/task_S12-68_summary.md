# S12-68 — Run the v0.6.0 baseline

The baseline runner and report boundary are prepared, but the released
runtime/model configuration is not present in the environment. The task
remains pending and the report says `NOT_EXECUTED_MISSING_RUNTIME_CONFIGURATION`.

## Testing

The self-test asserts that missing configuration produces 160 explicit missing
outputs and never substitutes a synthetic replay score.
