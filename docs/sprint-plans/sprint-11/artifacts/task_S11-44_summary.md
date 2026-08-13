# Task Summary: S11-44

**Sprint:** Sprint 11
**Task:** S11-44 — Teams canonical-event normalization

## Summary of Work

Teams messages and replies are converted to bounded `RawEventCandidate` values with deterministic event identities, created/updated mapping, UTC timestamps, hashed actor identifiers, sanitized body text, bounded evidence JSON, and no raw provider ID in external references.

## Files Modified

* [apps/api/src/projecta_api/connectors/teams.py](../../../../apps/api/src/projecta_api/connectors/teams.py) - Message normalization.
* [apps/api/src/projecta_api/connectors/event_validation.py](../../../../apps/api/src/projecta_api/connectors/event_validation.py) - Teams canonical-event acceptance.

## Testing

* **Test File:** [test_sprint11_teams_adapter.py](../../../../apps/api/tests/test_sprint11_teams_adapter.py)
* **Status:** Passed
* **Execution Command:** `uv run --project apps/api pytest -q apps/api/tests/test_sprint11_teams_adapter.py`

## Additional Notes

HTML is treated as untrusted input and reduced to bounded text before evidence storage.
