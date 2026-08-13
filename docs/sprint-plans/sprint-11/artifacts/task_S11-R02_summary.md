# Task Summary: S11-R02 — Add the operator Teams setup boundary

**Sprint:** Sprint 11
**Task:** S11-R02

## Summary of Work

Added digest-backed, project-bound, expiring, single-use setup handles in
PostgreSQL. The operator CLI writes the certificate credential directly to a
scoped OpenBao record; public create/update requests receive only an opaque
handle. Teams updates reject direct browser injection of provider config,
fixture references, or secret references.

## Files Modified

- [teams_setup.py](../../../../apps/api/src/projecta_api/connectors/teams_setup.py)
- [provision_teams_setup.py](../../../../scripts/provision_teams_setup.py)
- [0006_teams_setup_handles.py](../../../../apps/api/alembic/versions/0006_teams_setup_handles.py)
- [test_sprint11_teams_setup.py](../../../../apps/api/tests/test_sprint11_teams_setup.py)

## Testing

- **Status:** Passed, including project isolation, single use, lifecycle scope,
  and direct provider-config injection rejection.
- **Command:** `uv run pytest -q tests/test_sprint11_teams_setup.py`

## Additional Notes

The database stores the handle SHA-256 digest and non-secret binding only.
