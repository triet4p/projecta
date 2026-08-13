# Task Summary: S11-18 — Fixed OIDC hostnames and TLS routing

**Sprint:** Sprint 11
**Task:** S11-18

## Summary of Work
Added a fixed-host TLS reverse proxy with separate Projecta and auth surfaces, forwarded-header overwrite, public OIDC discovery/protocol routing, and rejection of unknown hosts and management paths.

## Files Modified
* [infra/docker/reverse-proxy/nginx.conf](/F:/ai-ml/projecta/infra/docker/reverse-proxy/nginx.conf)
* [compose.prod.yaml](/F:/ai-ml/projecta/compose.prod.yaml)

## Testing
* **Test File:** [test_sprint11_identity_contract.py](/F:/ai-ml/projecta/scripts/tests/test_sprint11_identity_contract.py)
* **Status:** Passed
* **Execution Command:** `uv run --project apps/api pytest -q scripts/tests/test_sprint11_identity_contract.py`

## Additional Notes
TLS certificates are deployment-mounted; management/health/metrics are not routed publicly.
