# Task Summary: S11-17 — Deterministic realm/client bootstrap

**Sprint:** Sprint 11
**Task:** S11-17

## Summary of Work
Added a versioned non-secret Keycloak realm/client/role/test-user template with PKCE and disabled direct grants. Bootstrap credential handling is operator-injected and documented separately from the template.

## Files Modified
* [infra/keycloak/realm.template.json](/F:/ai-ml/projecta/infra/keycloak/realm.template.json)
* [scripts/keycloak/bootstrap_realm.sh](/F:/ai-ml/projecta/scripts/keycloak/bootstrap_realm.sh)

## Testing
* **Test File:** [test_sprint11_identity_contract.py](/F:/ai-ml/projecta/scripts/tests/test_sprint11_identity_contract.py)
* **Status:** Passed
* **Execution Command:** `uv run --project apps/api pytest -q scripts/tests/test_sprint11_identity_contract.py`

## Additional Notes
The template contains no client secret or bootstrap password.
