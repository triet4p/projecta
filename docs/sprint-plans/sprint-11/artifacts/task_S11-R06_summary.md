# Task Summary: S11-R06 — Reconcile Compose and acceptance contracts

**Sprint:** Sprint 11
**Task:** S11-R06

## Summary of Work

Restored optimized, immutable, read-only Keycloak startup; added private DNS and
CA trust for the public OIDC issuer; and replaced the shallow clean runner with
staged OpenBao initialization, manual unseal, AppRole bootstrap, deterministic
journeys, workload re-authentication, log scanning, evidence, and cleanup.

## Files Modified

- [compose.prod.yaml](../../../../compose.prod.yaml)
- [run_sprint11_clean_compose.ps1](../../../../scripts/run_sprint11_clean_compose.ps1)
- [generate_sprint11_acceptance_tls.ps1](../../../../scripts/generate_sprint11_acceptance_tls.ps1)
- [s11-66-clean-compose.json](s11-66-clean-compose.json)

## Testing

- **Status:** Passed all 18 gates with short-lived untracked TLS, real immutable
  image digests, initialized/unsealed OpenBao, deterministic journeys, AppRole
  re-authentication, root-token revocation, log collection, and full cleanup.
- **Command:** `pwsh -File scripts/run_sprint11_clean_compose.ps1 -Start -AllowDirtyWorktree`

## Additional Notes

The runner redacts operator-sensitive output and deletes temporary recovery
material after each isolated acceptance run.
