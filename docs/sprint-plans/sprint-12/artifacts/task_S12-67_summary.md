# S12-67 — Evaluator self-tests

Added adversarial tests for unknown schema, tamper, split policy, duplicate and
leakage digests, cross-file references, missing output, empty metrics,
reviewer raw-data leakage and invalid taxonomy values.

## Testing

`uv run --project apps/api pytest -q scripts/tests/test_sprint12_phase_e_contract.py` — 9 passed.
