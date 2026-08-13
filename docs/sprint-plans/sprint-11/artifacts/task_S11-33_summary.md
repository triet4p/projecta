# Task Summary: S11-33

**Sprint:** Sprint 11
**Task:** S11-33 — Workload bootstrap authentication

## Summary of Work

Added AppRole bootstrap tooling and runtime authentication with RoleID/SecretID transport files, single-use SecretID configuration, 15-minute token TTL, 60-minute maximum TTL, bounded renewal, token invalidation, and root-token revocation after bootstrap.

## Files Modified

* [scripts/openbao/bootstrap-approle.sh](../../../../scripts/openbao/bootstrap-approle.sh) - Operator bootstrap and root revocation.
* [apps/api/src/projecta_api/secrets/approle.py](../../../../apps/api/src/projecta_api/secrets/approle.py) - Short-lived token provider and HTTP login.
* [compose.prod.yaml](../../../../compose.prod.yaml) - Restricted Compose secret wiring.

## Testing

* **Test File:** [test_sprint11_openbao.py](../../../../apps/api/tests/test_sprint11_openbao.py)
* **Status:** Passed
* **Execution Command:** `uv run --project apps/api pytest -q apps/api/tests/test_sprint11_openbao.py`

## Additional Notes

SecretID bootstrap material is consumed once per provider instance; cold restart requires fresh operator-issued material.
