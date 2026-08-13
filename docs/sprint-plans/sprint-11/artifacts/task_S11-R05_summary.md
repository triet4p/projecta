# Task Summary: S11-R05 — Make OpenBao tooling executable

**Sprint:** Sprint 11
**Task:** S11-R05

## Summary of Work

All operator scripts now call the official `bao` executable used by the pinned
OpenBao image. A repository contract enumerates every operator script and
rejects regression to the nonexistent `openbao` command.

## Files Modified

- [OpenBao initialization script](../../../../scripts/openbao/init.sh)
- [test_sprint11_openbao_contract.py](../../../../scripts/tests/test_sprint11_openbao_contract.py)

## Testing

- **Status:** Passed as part of the 30-test Sprint 11 contract matrix.
- **Command:** `uv run --project apps/api pytest -q scripts/tests/test_sprint11_openbao_contract.py`

## Additional Notes

No recovery material or token value is printed by the scripts.
