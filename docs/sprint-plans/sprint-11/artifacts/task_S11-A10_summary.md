# Task Summary: S11-A10 — Implement GitHub Cursor, Edit, and Replay Semantics

**Sprint:** Sprint 11

**Task:** S11-A10

## Summary of Work

Added a versioned opaque base64url canonical-JSON cursor with independent issue
and comment `(updated_at, numeric_id)` watermarks. Added strict overlap filtering
for GitHub's inclusive `since` queries. Cursor persistence/commit remains owned
by the existing orchestration completion protocol.

## Testing

* **Test File:** `apps/api/tests/test_sprint11_github_mapping.py`
* **Status:** Passed — overlap filtering, cumulative run byte budget,
  pagination-cycle detection, edit/replay semantics, and adapter-level tests
  are included in the connector suite.
* **Execution Command:** `uv run pytest -q tests/test_sprint11_github_setup.py tests/test_sprint11_github_transport.py tests/test_sprint11_github_mapping.py tests/test_connector_operational_contract.py tests/test_connector_kernel.py tests/test_connector_public_api.py tests/test_sprint11_teams_setup.py`
* **Additional checks:** Ruff, Pyright, and `git diff --check` passed.
