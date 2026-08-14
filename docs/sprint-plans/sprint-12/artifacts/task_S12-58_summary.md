# S12-58 — Versioned dataset loader

Implemented `load_dataset` with explicit schema-version, provenance, split,
test-custody, and scenario-reference checks. Unknown schema and sealed test
inputs fail closed.

## Testing

`test_sprint12_phase_e_contract.py` covers valid loading, unknown schema,
tampered source and split-policy rejection.
