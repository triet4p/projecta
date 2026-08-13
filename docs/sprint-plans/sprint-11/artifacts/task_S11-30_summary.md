# Task Summary: S11-30

**Sprint:** Sprint 11
**Task:** S11-30 — Pinned OpenBao production image and configuration

## Summary of Work

Added the official OpenBao 2.6.1 image with a reviewed linux/amd64 digest, non-root execution, internal TLS, fixed API/cluster addresses, integrated Raft storage, private exposure, health checking, and production resource bounds.

## Files Modified

* [infra/docker/openbao/Dockerfile](../../../../infra/docker/openbao/Dockerfile) - Pinned base and non-root image.
* [infra/openbao/config.hcl](../../../../infra/openbao/config.hcl) - Raft, TLS, and fixed-address configuration.
* [compose.yaml](../../../../compose.yaml) - Local secrets profile and internal OpenBao service.
* [compose.prod.yaml](../../../../compose.prod.yaml) - Production digest, resource, and private-network override.

## Testing

* **Test File:** [test_sprint11_openbao_contract.py](../../../../scripts/tests/test_sprint11_openbao_contract.py)
* **Status:** Passed
* **Execution Command:** `uv run --project apps/api pytest -q scripts/tests/test_sprint11_openbao_contract.py`

## Additional Notes

Single-node Raft and manual unseal remain explicit non-HA residual risks.
