# Task Summary: S11-R01 — Repair the real OIDC login boundary

**Sprint:** Sprint 11
**Task:** S11-R01

## Summary of Work

Aligned the no-secret Keycloak bootstrap with a public authorization-code
client protected by mandatory S256 PKCE. Hardened JWT validation so malformed
or forged RSA signatures become finite identity failures and multiple-audience
tokens require the expected authorized party.

## Files Modified

- [realm.template.json](../../../../infra/keycloak/realm.template.json) — declares
  the reviewed public PKCE client.
- [oidc.py](../../../../apps/api/src/projecta_api/identity/oidc.py) — validates
  typed JWT objects, signature failures, `azp`, and `nbf`.
- [test_sprint11_identity.py](../../../../apps/api/tests/test_sprint11_identity.py)
  — exercises real RSA signing and forged signatures.
- [identity-secret-operator-sprint-11.md](../../../runbooks/identity-secret-operator-sprint-11.md)
  — documents the public PKCE client contract.

## Testing

- **Test File:** `apps/api/tests/test_sprint11_identity.py`
- **Status:** Passed, 14 tests with the identity contract suite.
- **Execution Command:** `uv run --project apps/api pytest -q apps/api/tests/test_sprint11_identity.py scripts/tests/test_sprint11_identity_contract.py`

## Additional Notes

The client remains secretless by design; exact redirect URIs, TLS, state,
nonce, and PKCE are mandatory controls.
