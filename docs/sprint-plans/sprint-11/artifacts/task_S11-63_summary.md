# Task Summary: S11-63 — Isolated stateful cold recovery

## Outcome

Passed a 25-gate drill from clean isolated targets. The source PostgreSQL,
Keycloak, OpenBao, and evidence state was backed up, the complete source state
was destroyed, and the bundle was restored into new containers and volumes.

## Verified boundaries

- Exported the live Keycloak realm and booted Keycloak from its restored
  PostgreSQL database.
- Restored the encrypted OpenBao Raft snapshot and manually unsealed it with two
  original Shamir shares.
- Issued a new single-use AppRole SecretID, authenticated the workload, and read
  the restored sentinel before revoking the root token.
- Invalidated the restored Projecta session and proved the connector replay
  remained idempotent with identical evidence bytes and digest.
- Removed every disposable container, volume, network, recovery share, token,
  database password, and snapshot key after the run.

## Validation

- **Status:** Passed
- **Command:** `pwsh -File scripts/run_sprint11_cold_recovery.ps1 -AllowDirtyWorktree`
- **Evidence:** `s11-63-cold-recovery.json`
