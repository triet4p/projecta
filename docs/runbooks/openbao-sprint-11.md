# OpenBao runtime boundary — Sprint 11

Status: implemented for S11-30 through S11-39; human operational acceptance remains part of the later recovery gates.

## Boundary

Projecta owns exact authorization for `project → installation → connector type → provider tenant → installation revision`. OpenBao is a service-level custody boundary. The API never asks OpenBao to decide whether an actor may use a project or installation.

The production image is OpenBao `2.6.1`, selected from the official registry and required to be replaced by an immutable digest in `OPENBAO_IMAGE`. The service uses a single integrated Raft node, internal TLS, fixed addresses, no public port, no UI, and bounded resources of 0.5 CPU and 512 MiB. This is intentionally early-production and non-HA.

## Initialize and unseal

Run `scripts/openbao/init.sh` from an operator environment with an offline recovery directory outside the repository. The script creates three Shamir recovery shares with a two-share threshold and refuses to overwrite existing material. It writes only restricted files and reports status; it never prints a share or root token. Keep the three shares across two independent offline locations.

After a cold restart, run `scripts/openbao/unseal.sh` with two shares. A sealed or unavailable manager is not a successful connector-ready state. The API readiness endpoint exposes only `SECRET_MANAGER_UNAVAILABLE`; the detailed state remains an internal adapter status (`sealed`, `unavailable`, `unauthorized`, `missing`, `revoked`, or `stale`).

## Workload bootstrap

Run `scripts/openbao/bootstrap-approle.sh` once the operator has authenticated. It installs the versioned connector policy, enables AppRole idempotently, creates a role with a 10-minute single-use SecretID, 15-minute token TTL, and 60-minute maximum TTL, then revokes the bootstrap root token. RoleID and SecretID are written only to restricted transport files. RoleID is not secret; SecretID is one-time bootstrap material.

The API reads those files through Compose secrets, logs in with AppRole, renews a short-lived token within its bounded maximum, and can invalidate its cached token. No browser, public DTO, RDF graph, PostgreSQL row, telemetry event, or connector fixture receives the token or plaintext secret.

## Secret lifecycle

`OpenBaoSecretStore` exposes only scoped create/resolve/rotate/revoke operations. References are opaque, versions are immutable snapshots, and the in-memory cache is bounded to at most five minutes. Revocation invalidates the cache and subsequent resolution fails closed. The legacy unscoped port methods deliberately return `SCOPE_REQUIRED` when this adapter is used.

## Snapshot and restore

Run `scripts/openbao/snapshot.sh` daily and after important credential changes. The script writes a temporary Raft snapshot, encrypts it with an operator-held key, removes the plaintext temporary file, and records a SHA-256 integrity file in an off-host directory. Run `scripts/openbao/restore.sh` only against a clean isolated instance. It rejects a contract-version mismatch and hash failure, and it explicitly requires manual unseal and workload re-authentication afterward.

The recovery target is RPO 24 hours and RTO 60 minutes. Restoring OpenBao does not restore Projecta browser sessions; the later recovery implementation must invalidate the Projecta session epoch and require login again.

## Operational limits

The current topology has one Raft node and manual unseal. It must not be described as HA. TLS files, digest references, recovery shares, root tokens, AppRole files, snapshot keys, and encrypted snapshots are operator-owned deployment material and must remain untracked.
