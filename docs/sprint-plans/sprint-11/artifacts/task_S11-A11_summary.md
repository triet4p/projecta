# Task Summary: S11-A11 — Normalize GitHub Provider Failures

**Sprint:** Sprint 11

**Task:** S11-A11

## Summary of Work

Added finite failure normalization for rate exhaustion, forbidden/not-found,
provider unavailability, redirects, invalid output/pagination, timeout, byte
and page truncation, and generic transport failure. Only bounded retry-after
seconds from an explicit allowlist may cross the adapter boundary.

## Testing

* **Test File:** `apps/api/tests/test_sprint11_github_mapping.py`
* **Status:** Passed — included in the 43-test A06–A11 connector suite.
* **Execution Command:** `uv run pytest -q tests/test_sprint11_github_setup.py tests/test_sprint11_github_transport.py tests/test_sprint11_github_mapping.py tests/test_connector_operational_contract.py tests/test_connector_kernel.py tests/test_connector_public_api.py tests/test_sprint11_teams_setup.py`
* **Additional checks:** Ruff, Pyright, and `git diff --check` passed.
