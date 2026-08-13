# Server-side Secret Manager Contract — Sprint 11 S11-09

**Status:** `G1_APPROVED_WITH_REVISIONS`

**Task:** S11-09

**Contract:** `projecta-secret-store.v1-draft`

## Port

The application depends on a provider-neutral port with these bounded
operations:

```text
create(scope, secret) -> opaque reference + version
resolve(scope, reference, version?) -> immutable secret snapshot
rotate(scope, reference, secret) -> new version
revoke(scope, reference, version?) -> terminal status
delete(scope, reference) -> idempotent terminal status
readiness() -> finite dependency status
```

The concrete OpenBao adapter and deterministic fake may implement the same
port. Provider paths, tokens, policies, and client details remain outside the
application contract.

## Scope and authority

Every operation carries a server-owned scope:

```text
project → installation → connector type → provider tenant → installation revision
```

Projecta is the authority for exact project, installation, connector type,
provider tenant, and installation revision authorization. OpenBao is the
service-level custody boundary for storage, versioning, workload
authentication, and revocation; it is not described as independently enforcing
each installation unless a per-installation policy topology is implemented and
tested.

The adapter must reject a reference that is not owned by the exact scope. A
browser, provider payload, project hint, or connector adapter cannot broaden
scope or choose an arbitrary path.

## References and versions

- References are opaque, bounded, non-secret handles.
- Versions are server-selected or explicitly bound to an installation
  revision; they are not user-controlled provider paths.
- A run captures one immutable secret snapshot at start.
- Rotation changes the version used by future runs.
- In-flight runs do not switch secret halfway through execution.
- Revoked/missing/stale versions fail closed and do not silently fall back.

## Workload authentication and caching

- Workload authentication uses AppRole. The RoleID is non-secret; the SecretID
  is single-use with a short TTL (initial target: 10 minutes). The resulting
  workload token is short-lived, renewable within a bounded maximum (initial
  target: 15 minutes TTL and 60 minutes maximum), and revocable.
- Bootstrap material is injected only through permission-restricted deployment
  files or an equivalent approved transport.
- Runtime credentials are revocable and never returned to the browser.
- Caching is bounded by time, scope, version, and memory; cache invalidation
  follows rotation/revocation.

## Plaintext handling

Plaintext exists only in the narrow adapter-to-provider operation and must not
be written to logs, telemetry, audit, PostgreSQL, RDF, evidence, DOM,
browser storage, public DTOs, exceptions, or review artifacts. The adapter
returns a typed in-memory snapshot to the connector credential provider and
does not expose raw provider errors.

## Safe readiness and errors

Internal statuses distinguish:

- sealed;
- unavailable;
- unauthorized;
- missing;
- revoked;
- stale version;
- invalid scope;
- rotation conflict.

Public behavior is finite and coarse: readiness failure or unavailable
dependency becomes a safe `503`; invalid installation/scope becomes a safe
typed `400`/`403`/`404` according to the existing connector policy. No path,
reference, token, or provider response is included.

## Recovery and audit

Snapshot/restore is an operator workflow. After restore, the service must
remain closed until the approved unseal and workload re-authentication steps
complete. Projecta restores membership/configuration but invalidates all
Projecta sessions. Audit records contain only correlation, scope-safe labels,
version class, and outcome; never secret values or raw references.

## Test obligations

The contract requires deterministic tests for scoped CRUD, version selection,
rotation, revocation, caching, sealed/unavailable/unauthorized/missing
states, in-flight snapshots, restore mismatch, secret leak scans, and
cross-project/reference isolation.
