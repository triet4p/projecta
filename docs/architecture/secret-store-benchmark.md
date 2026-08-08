# Sprint 7 Secret-Store Baseline Benchmark

**Status:** APPROVED BASELINE — application-encrypted operational storage selected by S7-14
**Task:** S7-13

## Scope

This benchmark compares the three options named by S7-13 for interactive LLM
credentials. It evaluates the local Compose vertical slice, dynamic writes,
backup/recovery, rotation, threat model, and migration path. It does not add a
dependency, create a datastore, or approve a production secret manager.

All options must satisfy the same contract: opaque references, server-only
resolution, fail-closed unavailability, no raw credential in profile metadata,
and no credential in browser/API/log/telemetry/RDF/fixture output.

## Comparison

| Criterion | Application-encrypted operational storage | Vault-compatible reference | Host OS keyring |
|---|---|---|---|
| Compose compatibility | Strong. Runs with the existing server topology and can use a local volume or operational database. | Medium. Requires a Vault-compatible service, bootstrap token/auth, health dependency, and extra Compose profile. | Weak for a server-owned web app. Keyring belongs to a workstation session, not the API container. |
| Dynamic writes | Strong. API can create/replace/delete records through one server port. | Strong. Native secret versioning and dynamic writes. | Medium for one desktop user; poor for remote/web and multi-process service ownership. |
| Backup/recovery | Medium. Encrypted records are backupable, but the encryption/master-key boundary must be operated separately. | Strong when Vault backup/unseal/recovery is operated correctly; adds operational responsibility. | Weak/host-specific. Recovery follows workstation/account behavior and is not aligned with Compose volume backup. |
| Rotation | Medium to strong. Application must implement versioning, cleanup, and concurrency safely. | Strong. Secret versions, policies, and rotation workflows are established by the service. | Medium locally; portability and server-side rotation are weak. |
| Threat model | Master-key custody and application compromise are the primary risks; compromise of the app may expose resolved credentials. | Separates secret custody from the app and supports policy/audit boundaries; bootstrap/authentication becomes a new risk. | Reduces browser exposure on one workstation but does not solve server/container custody or remote access. |
| Migration path | Medium. Can migrate opaque references to Vault later if the port is kept stable; encrypted-record format must not leak into domain APIs. | Strong for production evolution if the port is provider-neutral. | Weak as a long-term server baseline; migration out is likely required. |
| Sprint 7 fit | Good local candidate, subject to explicit master-key and backup design. | Good production-shaped candidate, but likely too much local infrastructure before the user slice is proven. | Not suitable as the canonical web/Compose adapter. |

## Findings

- The host OS keyring does not meet the approved server-owned web boundary and
  is excluded from the canonical Sprint 7 adapter.
- Application-encrypted storage has the shortest local Compose path, but its
  acceptability depends on a separately managed encryption/master key,
  recovery evidence, and strict plaintext lifetime controls.
- A Vault-compatible reference provides the clearest secret-custody and
  rotation boundary, but adds a stateful dependency and bootstrap/recovery
  workflow that Sprint 7 does not currently contain.
- Both viable options can preserve the same `SecretStore` port and opaque
  `secretReference`, allowing migration without changing the browser or
  extraction contract.

## Approved S7-14 Decision

Application-encrypted operational storage is approved for the Sprint 7
local/self-hosted Compose slice. The implementation must remain behind the
provider-neutral `SecretStore` port and expose only opaque references to the
runtime configuration layer.

Vault-compatible storage remains the production-shaped migration target, not a
Sprint 7 dependency. The host OS keyring is excluded from the canonical
server-owned web adapter. S7-14 records the choice only; encryption libraries,
operational schema, master-key bootstrap, persistence, and adapter behavior
remain S7-15/S7-16 implementation work.
