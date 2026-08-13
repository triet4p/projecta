# Free Secret Provider Benchmark — Sprint 11 S11-08

**Status:** `G1_APPROVED_WITH_REVISIONS`

**Task:** S11-08

## Decision question

Which secret boundary provides separate runtime custody, scoped lookup,
versioned rotation, revocation, auditability, backup, and restore without
making Azure or another paid managed service a required dependency?

## Options

| Option | Runtime custody | Rotation/revocation | Backup/restore | Fit |
| --- | --- | --- | --- | --- |
| OpenBao integrated Raft | Separate service and policy boundary; versioned secret engine | Explicit scoped policy, versions, revoke/disable workflow | Encrypted snapshot and clean-instance restore; manual unseal | **Proposed baseline; pending G1** |
| Existing application-encrypted store | Master key is deployed with the application boundary; no separate operator custody | Application API can create/resolve/delete, but custody remains coupled | Database backup includes ciphertext; master-key recovery remains coupled | Local/self-hosted fallback only |
| Compose secrets | Per-service file mount and filesystem permissions | No runtime lookup, versioning, revocation, or audit policy | Backup is operator file handling, not secret-manager state | Bootstrap transport only |
| SOPS + `age` | Encrypted deployment artifact with external key custody | Rotation is artifact/deployment workflow, not runtime lookup | Encrypted files can be backed up | Bootstrap transport only unless wrapped by a manager |
| Azure Key Vault | Managed custody and provider operations | Strong managed features | Managed backup/recovery | Deferred; paid/cloud dependency not assumed |

## Criteria and result

OpenBao `2.6.1` is approved as the no-subscription runtime boundary. The
implementation must use `ghcr.io/openbao/openbao:2.6.1` and record its
immutable digest after pulling it. The approved topology is single-node
integrated Raft with TLS, manual unseal, operator key custody, and
snapshot/restore. The existing application-encrypted
store remains valuable as a deterministic fake/fallback for local scope but
does not establish separate production custody. Compose secrets and SOPS plus
`age` can transport bootstrap material but cannot be called the runtime
secret manager on their own.

## Selection guardrails

- the API sees only a provider-neutral `SecretStore` port;
- secret references are opaque and bound to project/installation/provider
  tenant/revision;
- runtime policy denies list-all, arbitrary paths, policy administration,
  sealing, and root operations;
- rotation changes the current version without exposing plaintext to browser,
  RDF, evidence, telemetry, or public API;
- public CI uses a deterministic fake and never requires live OpenBao keys;
- managed providers remain migration adapters, not hidden assumptions.

## G1 evidence required

1. Exact OpenBao version/image provenance and license review.
2. Resource measurements for the target single-VM Compose profile.
3. TLS, policy, workload authentication, initialize/unseal, rotation, and
   revoke procedures.
4. Encrypted snapshot/restore and manual-unseal drill design.
5. Clear custody and break-glass ownership.
6. Explicit acceptance of single-instance and manual-unseal residual risks.

## References

- [OpenBao storage configuration](https://openbao.org/docs/configuration/storage/)
- [OpenBao license](https://github.com/openbao/openbao/blob/main/LICENSE)
- [Compose secrets](https://docs.docker.com/compose/how-tos/use-secrets/)
