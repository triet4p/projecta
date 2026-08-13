# OpenBao Operations Proposal — Sprint 11 S11-10

**Status:** `G1_APPROVED_WITH_REVISIONS`

**Task:** S11-10

This document records the G1-approved operator workflow. It does not contain
an image digest; S11-15 must record the digest resolved from the approved
image tag before production-shaped use.

## Topology

- `ghcr.io/openbao/openbao:2.6.1`, pinned by immutable digest after pull, as a
  non-root OpenBao runtime image in the production-shaped Compose
  profile;
- integrated Raft storage on a dedicated persistent volume;
- fixed internal address and TLS listener;
- private management, health, metrics, and administrative surfaces;
- bounded CPU/memory and restart policy measured on the target single VM;
- no development server mode and no shared application database ownership.

The Sprint 11 proposal is single-instance. It must not be described as HA or
as an unattended cold-restart design.

## Initialization and unseal

1. Operator starts a clean isolated instance with TLS and fixed addresses.
2. Operator initializes once and records status only; recovery keys and root
   token are never tracked, logged, or copied into review artifacts.
3. Recovery-key custody is split between explicitly named operators or secure
   custody locations selected at G1.
4. Operator manually unseals the instance with the required quorum.
5. Operator creates the minimum policy/auth objects and revokes the temporary
   root authority as soon as bootstrap is complete.
6. The API receives only the approved short-lived workload bootstrap material
   through restricted Compose secret files or the selected encrypted transport.

The approved Shamir configuration is three recovery shares with a threshold of
two. Shares are stored in two independent offline locations. The tooling must
be idempotent in safe phases and must never print key shares,
root tokens, client secrets, or secret values.

## Workload policy

The API workload can read/write only versioned connector-secret paths derived
from its approved project/installation scope. It cannot list all secrets,
read arbitrary paths, mutate policy, seal/unseal, administer auth, or perform
root operations.

The application remains responsible for exact project/installation
authorization; OpenBao is a service-level custody boundary, not a replacement
for Projecta project membership. Per-installation OpenBao policies are not
assumed unless separately implemented and tested.

## Rotation and revocation

- Create a new version before revoking the old version.
- New runs resolve the current approved version.
- In-flight runs retain their immutable snapshot and terminal outcome.
- Revocation invalidates future resolution and cache entries.
- Connector reinstall is not required for credential rotation.
- A failed rotation does not delete the last known good version or advance an
  installation revision silently.

## Snapshot and restore

- Take an encrypted, integrity-checked snapshot from an isolated, quiesced
  instance according to OpenBao's supported procedure.
- Keep snapshot metadata separate from plaintext secret values.
- Restore only into a clean isolated instance with matching contract/version
  expectations.
- Require manual unseal and workload re-authentication after restore.
- Reject incompatible snapshot/version/configuration combinations.
- Resume connector operations only after readiness, policy, scope, and
  post-restore replay checks pass.

The initial operational targets are daily snapshots, plus a snapshot after
each material credential change, RPO 24 hours, and RTO 60 minutes.

## Upgrade and break-glass

Every image upgrade requires a backup, restore rehearsal, compatibility check,
and rollback image reference. Break-glass access is operator-only, time-bound,
audited, and excluded from application runtime credentials. Break-glass use
does not authorize browser access or raw secret export.

## Residual risk statement

Manual unseal is a deliberate trade-off for a self-hosted, no-subscription
path. Loss or unavailability of the operator quorum can block cold recovery.
The single-instance topology is another availability risk. Both must be
measured, documented, and explicitly accepted at G1 and G2.

## References

- [OpenBao storage](https://openbao.org/docs/configuration/storage/)
- [OpenBao license](https://github.com/openbao/openbao/blob/main/LICENSE)
- [Projecta deployment choice](../initialization/08-Deployment-Choice.md)
