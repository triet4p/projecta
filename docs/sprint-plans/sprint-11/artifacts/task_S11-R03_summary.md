# Task Summary: S11-R03 — Stabilize Teams credential scope

**Sprint:** Sprint 11
**Task:** S11-R03

## Summary of Work

Separated explicit `credentialRevision` from the mutable installation revision.
Enable, disable, and run transitions no longer change the OpenBao lookup scope;
an operator setup handle is required to rotate credentials or tenant binding.

## Files Modified

- [teams.py](../../../../apps/api/src/projecta_api/connectors/teams.py)
- [installation_service.py](../../../../apps/api/src/projecta_api/connectors/installation_service.py)
- [test_sprint11_teams_setup.py](../../../../apps/api/tests/test_sprint11_teams_setup.py)

## Testing

- **Status:** Passed; revision 2 installation resolves credential revision 1.
- **Command:** `uv run pytest -q tests/test_sprint11_teams_setup.py`

## Additional Notes

Rotation remains explicit and auditable rather than following ordinary row
revisions.
