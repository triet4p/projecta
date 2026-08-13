# Task Summary: S11-11 — Define the Teams Provider Contract

**Sprint:** Sprint 11

**Task:** S11-11

## Summary of Work

Defined the current Graph channel-message endpoints, permission candidate,
resource-specific consent caveat, bounded pagination/replies, canonical event
mapping, provider identity handling, failure normalization, and no-hidden-retry
rules. The official documentation must be rechecked before implementation.

## Files Modified

* [teams-provider-contract.md](../../../architecture/teams-provider-contract.md) - Teams adapter contract draft.
* [test_sprint11_phase_a_contract.py](../../../../scripts/tests/test_sprint11_phase_a_contract.py) - Phase A contract checks.

## Testing

* **Test File:** [test_sprint11_phase_a_contract.py](../../../../scripts/tests/test_sprint11_phase_a_contract.py)
* **Status:** Passed
* **Execution Command:** `uv run --project apps/api pytest -q scripts/tests/test_sprint11_phase_a_contract.py`

## Additional Notes

G1 selected certificate-based app-only access with
`ChannelMessage.Read.Group` resource-specific consent; S11-15 onward must
prove the consent and bounded installation scope.
