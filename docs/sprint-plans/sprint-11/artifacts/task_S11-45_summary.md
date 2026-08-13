# Task Summary: S11-45

**Sprint:** Sprint 11
**Task:** S11-45 — Teams cursor and edit semantics

## Summary of Work

Added a revision-bound opaque Teams watermark cursor. The adapter filters observations at or below the committed watermark, derives event identity from provider message plus modification timestamp, and therefore treats edits/deletions as deterministic new observations while preserving replay identity for unchanged observations.

## Files Modified

* [apps/api/src/projecta_api/connectors/teams.py](../../../../apps/api/src/projecta_api/connectors/teams.py) - Cursor and edit behavior.
* [apps/api/src/projecta_api/connectors/orchestration.py](../../../../apps/api/src/projecta_api/connectors/orchestration.py) - Cursor commit suppression on truncation.

## Testing

* **Test File:** [test_sprint11_teams_adapter.py](../../../../apps/api/tests/test_sprint11_teams_adapter.py)
* **Status:** Passed
* **Execution Command:** `uv run --project apps/api pytest -q apps/api/tests/test_sprint11_teams_adapter.py`

## Additional Notes

The adapter never accepts a browser-supplied cursor as authorization.
