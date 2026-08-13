# Task Summary: S11-A07 — Implement the Bounded GitHub Transport

**Sprint:** Sprint 11

**Task:** S11-A07

## Summary of Work

Implemented a fixed-origin, one-attempt GitHub REST transport with server-owned
headers, disabled redirects, strict issues/comment paths, validated `Link`
pagination, absolute deadline enforcement, bounded streaming response bytes,
and no automatic retry. Provider response parsing and canonical issue/comment
mapping remain separate A08–A11 tasks.

## Files Modified

* [github_public_issues.py](../../../../apps/api/src/projecta_api/connectors/github_public_issues.py) - Fixed-origin HTTP transport and pagination validation.
* [test_sprint11_github_transport.py](../../../../apps/api/tests/test_sprint11_github_transport.py) - Transport security and budget tests.

## Testing

* **Test File:** `apps/api/tests/test_sprint11_github_transport.py`
* **Status:** Passed — 4 transport tests and 33 combined connector regressions.
* **Execution Command:** `uv run pytest -q tests/test_sprint11_github_setup.py tests/test_sprint11_github_transport.py tests/test_connector_operational_contract.py tests/test_connector_kernel.py tests/test_connector_public_api.py tests/test_sprint11_teams_setup.py`
* **Additional checks:** Ruff, Pyright, `python -m alembic heads`, and
  `git diff --check` passed.

## Additional Notes

The transport returns bounded status/header/body data to the future adapter;
failure normalization, event mapping, cursor semantics, and registry
composition are intentionally not implemented in this task.
