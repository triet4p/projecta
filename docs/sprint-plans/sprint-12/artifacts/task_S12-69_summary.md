# S12-69 — Classify baseline errors

The finite taxonomy is versioned and the runtime baseline records 55 observed
model-side failures: 48 `invalid_evidence` and 7 `schema_invalid`. No data,
annotation, ontology, prompt, context or tool failure was inferred without
evidence. The quality gate remains blocked until these model-output failures
are investigated and a clean rerun is available.

## Testing

The self-test accepts all declared categories through the classifier contract,
rejects an unknown category, and the runtime report contains only declared
categories.
