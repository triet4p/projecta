# Task Summary: S11-27 — Capability enforcement

**Sprint:** Sprint 11
**Task:** S11-27

## Summary of Work
Added Projecta-owned capability checks for candidate review/validation mutations and delegated connector writes to the production membership-derived connector policy. Cross-project selection remains server-owned and safe not-found/forbidden mapping is preserved.

## Files Modified
* [apps/api/src/projecta_api/identity/policy.py](/F:/ai-ml/projecta/apps/api/src/projecta_api/identity/policy.py)
* [apps/api/src/projecta_api/routes.py](/F:/ai-ml/projecta/apps/api/src/projecta_api/routes.py)
* [apps/api/src/projecta_api/connectors/public_api.py](/F:/ai-ml/projecta/apps/api/src/projecta_api/connectors/public_api.py)

## Testing
* **Test File:** [test_sprint11_identity.py](/F:/ai-ml/projecta/apps/api/tests/test_sprint11_identity.py)
* **Status:** Passed
* **Execution Command:** `uv run --project apps/api pytest -q apps/api/tests/test_sprint11_identity.py`

## Additional Notes
`connector-admin` remains additive and does not imply `reviewer`.
