# S12-60 — Extraction metrics

Added exact-set metrics for entity types/spans, relations and links, plus
abstention accuracy, hallucination rate and optional calibration (Brier/ECE)
by caller-provided slice results.

## Testing

Empty-set, missing-output and calibration edge cases are covered by the Phase E
self-tests.
