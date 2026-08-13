# Task Summary: S11-A06 — Add Typed GitHub Public Issues Installation Configuration

**Sprint:** Sprint 11

**Task:** S11-A06

## Summary of Work

Added the typed, fixed-origin GitHub Public Issues installation binding with
exact owner/repository validation, fixed read capabilities, bounded request,
page, lookback, event, byte, cursor, and deadline limits, plus a safe
credential-free projection. Added single-use project-bound setup handles in
memory and PostgreSQL, with atomic consumption and expiry, and connected the
typed handle to the installation lifecycle without adding provider transport.

## Files Modified

* [github_public_issues.py](../../../../apps/api/src/projecta_api/connectors/github_public_issues.py) - Typed configuration and safe projection.
* [github_public_issues_setup.py](../../../../apps/api/src/projecta_api/connectors/github_public_issues_setup.py) - Single-use setup handle registries.
* [installation_service.py](../../../../apps/api/src/projecta_api/connectors/installation_service.py) - Installation consumption boundary.
* [schema.py](../../../../apps/api/src/projecta_api/operational/schema.py) - PostgreSQL setup-handle table model.
* [0007_github_public_issues_setup_handles.py](../../../../apps/api/alembic/versions/0007_github_public_issues_setup_handles.py) - Versioned database migration.
* [test_sprint11_github_setup.py](../../../../apps/api/tests/test_sprint11_github_setup.py) - Typed config and handle tests.

## Testing

* **Test File:** `apps/api/tests/test_sprint11_github_setup.py`,
  `apps/api/tests/test_connector_operational_contract.py`
* **Status:** Passed — 13 focused tests and 28 broader connector regressions.
* **Execution Command:** `uv run pytest -q tests/test_sprint11_github_setup.py tests/test_connector_operational_contract.py`
* **Additional checks:** Ruff, Pyright, `python -m alembic heads`, and
  `git diff --check` passed.

## Additional Notes

The HTTP transport, adapter registration, public API, generated types, and UI
remain S11-A07 and S11-A12 through S11-A14 work. No token, OpenBao provider
secret, Entra flow, or work tenant is introduced.
