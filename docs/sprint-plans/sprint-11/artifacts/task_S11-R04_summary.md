# Task Summary: S11-R04 — Make Teams incremental ingestion truthful

**Sprint:** Sprint 11
**Task:** S11-R04

## Summary of Work

Reply traversal now checks old roots for newer replies, validates and normalizes
provider pagination links, rejects oversized Graph responses, and reports
`truncated` for content limits instead of clipping message bodies silently.

## Files Modified

- [teams.py](../../../../apps/api/src/projecta_api/connectors/teams.py)
- [test_sprint11_teams_adapter.py](../../../../apps/api/tests/test_sprint11_teams_adapter.py)

## Testing

- **Status:** Passed, including old-root/new-reply, absolute next-link,
  preserved long body, and over-limit truncation cases.
- **Command:** `uv run pytest -q tests/test_sprint11_teams_adapter.py`

## Additional Notes

Sprint 10 event/run/reply limits remain unchanged.
