# Connector Authorization Contract — Sprint 10

**Status:** `G1_APPROVED_IMPLEMENTATION`

**Task:** S10-05

**Contract version:** `connector-authorization.v1`

The G1 review packet records human approval on 2026-08-10. Sprint 10 C tasks
implement only the provider-neutral principal/policy seam, local/test adapter,
and opaque SecretStore binding described here; production identity and secret
manager integration remain separate review gates.

## Boundary and authority

Connector authorization is decided by the server-owned principal and policy
layer. The browser, connector adapter, fixture, event payload, project path,
trusted header, or opaque handle is never an authority.

The authorization flow is:

```text
server/auth adapter
  → ConnectorPrincipal
  → project membership and allowed-project scope
  → connector operation policy
  → installation/capability/revision checks
  → bounded adapter/orchestration operation
```

Sprint 10 adds a provider-neutral seam. It does not claim a production OIDC
provider, tenant administration, or complete RBAC/ABAC implementation.

## Server-owned principal

The internal principal is resolved before a connector operation:

```text
ConnectorPrincipal
├── principalId: internal actor/session identity
├── actorId: server-established actor identity
├── allowedProjects: server-derived project scope
├── roles: finite safe role values
├── capabilities: finite action values
├── authSource: local-experience | test | future-reviewed-provider
└── correlation: requestId + operationId
```

Only the server may populate or change these fields. A public DTO may expose
safe actor/session status, but never the principal's internal identity,
credential, authorization headers, secret reference, or full project list
beyond the explicitly authorized finite catalog.

The principal port is conceptually:

```python
class ConnectorPrincipalPort(Protocol):
    async def resolve(self, request: AuthorizationRequest) -> ConnectorPrincipal: ...

    async def project_membership(
        self, principal: ConnectorPrincipal, project_scope: ProjectScope
    ) -> MembershipDecision: ...
```

The connector adapter does not resolve Projecta authorization. It receives only
the already authorized, bounded operation context needed for its port.

## Local experience adapter

The existing local experience adapter remains valid for local and deterministic
test use:

- It supplies a configured server-owned actor and finite project allowlist.
- The browser cannot choose or override the actor, project, context secret,
  request identity, or selection revision.
- It fails closed when the required secret, actor, project catalog, or selection
  revision is missing or stale.
- It may grant a deterministic connector-admin capability only when local/test
  configuration explicitly enables that operation.
- It is disabled or rejected in `production` mode until a reviewed production
  authentication/authorization boundary exists.

Local success is evidence of deterministic policy behavior, not evidence of
production identity, tenant isolation, or external consent.

## Finite connector operations

The v1 action vocabulary is:

- `catalog.read`
- `installation.read`
- `installation.create`
- `installation.update`
- `installation.enable`
- `installation.disable`
- `sync.run`
- `sync.read`
- `dead-letter.read`
- `sync.retry`

No arbitrary `connector.execute`, provider method, filesystem operation,
outbound action, or capability string is accepted.

## Decision matrix

Every operation is checked independently. Having permission to read an
installation does not imply permission to run or retry it.

| Operation | Required server checks | Mutation |
| --- | --- | --- |
| `catalog.read` | Principal is present; return only allowlisted connector types/capabilities safe for the caller's scope | None |
| `installation.read` | Principal, project membership, visible project scope, installation belongs to that project | None |
| `installation.create` | Principal, project membership, `connector-admin` capability, allowlisted connector type, valid configuration, secret-reference policy, idempotency | Create one installation revision |
| `installation.update` | Same project/admin checks, current opaque handle, expected revision, immutable-type rules, idempotency | New installation revision |
| `installation.enable` | Project/admin checks, current revision, valid capability/configuration, secret reference policy | Enabled state transition |
| `installation.disable` | Project/admin checks, current revision, explicit mutation confirmation | Disabled state transition |
| `sync.run` | Project/admin checks, enabled installation, current revision, `inbound-import` capability, new operation idempotency key, bounded command | One single-attempt run |
| `sync.read` | Principal, project membership, installation/run visibility, safe projection limits | None |
| `dead-letter.read` | Principal, project membership, installation/run visibility, safe summary scope | None |
| `sync.retry` | Project/admin checks, failed terminal run, expected failed-run revision, new idempotency key, explicit retry authorization, no loop | New linked run only |

The service rechecks project scope and revision immediately before mutation. A
previously authorized browser view is not a durable grant.

## Project and installation scope

Project scope is resolved by the Application API from server state. The request
may carry an opaque project/installation handle and expected revision, but it
may not carry a raw project ID, actor ID, graph name, RDF IRI, storage path, or
secret reference as authority.

The service verifies all of the following before adapter execution:

- principal is valid and not expired/revoked;
- project is in the principal's allowed scope;
- installation is owned by the selected project;
- connector type matches the allowlisted registry entry;
- installation revision matches the expected revision where required;
- installation is enabled for `sync.run`;
- requested capability is declared by the installation snapshot;
- operation budget and idempotency key are valid.

An adapter-supplied project hint or event scope is treated as untrusted input.
It cannot redirect the operation to another project.

## Opaque handles and stale revisions

Public handles are short-lived or revision-bound opaque values. They are
navigation capabilities, not database IDs and not authorization tokens.

Mutating operations require the expected installation revision. The server
returns a finite stale result when the revision changed after the screen was
loaded:

- do not apply the mutation;
- do not call the adapter;
- do not retry automatically;
- return a safe current-state/reload action where the caller is authorized;
- preserve the existing installation/run state and audit history.

Retry additionally requires the expected failed-run revision and a new
operation idempotency key. Reusing the original key or retrying a non-failed
run is a typed conflict.

## Safe public mapping

The connector boundary uses the released `application/problem+json` envelope
with `code`, bounded `detail`, and `requestId`. The mapping is deliberately
coarse where revealing existence would be unsafe:

| Situation | Public result | Existence disclosure |
| --- | --- | --- |
| Missing/invalid server context | `401 PROJECT_CONTEXT_REQUIRED` | None |
| Authenticated principal lacks a known visible project action | `403 PROJECT_FORBIDDEN` | Only the already-visible project scope |
| Installation/project/run handle is unknown, stale outside scope, or belongs to another project | `404 RESOURCE_NOT_FOUND` | Does not distinguish missing from invisible |
| Current installation/run revision no longer matches | `409 PROJECT_SELECTION_STALE` or approved connector stale code | Safe revision/reload instruction only |
| Same idempotency identity with different canonical body | `409 IDEMPOTENCY_KEY_REUSED` or approved event conflict code | No original/raw body disclosure |
| Disabled installation is run | `409 INVALID_LIFECYCLE_STATE` | No adapter call or cursor movement |
| Unsupported connector/capability | `400 INVALID_REQUEST` or approved unsupported code | No provider/module details |
| Operational/Core/evidence dependency fails | `503`/`504` approved finite problem | No storage path, SQL, RDF, stack trace, or payload |

The implementation must choose a stable mapping for each public route and test
that cross-project and invisible resources do not reveal existence through
status, counts, error timing, logs, telemetry, or UI fallback data.

## Correlation and audit

The server generates or normalizes `requestId` and `operationId` before policy
evaluation. Every authorization decision and terminal operation record carries:

- correlation IDs;
- safe action and connector type;
- project-safe scope token, not a raw cross-project identifier;
- principal-safe attribution;
- installation/run revision;
- allow/deny reason class;
- terminal outcome when execution began;
- bounded timestamps.

Raw credentials, secret references, raw payload, actor tokens, internal IDs,
RDF IRIs, graph names, SQL, stack traces, and browser-provided authority are
never written to audit or telemetry.

## Secret boundary

Installation configuration may contain an opaque reference to the approved
server-side `SecretStore` port. Authorization can check that a reference is
allowed for the project/installation, but it must not:

- return or log plaintext credentials;
- hash a credential into telemetry;
- persist raw credentials in connector tables, RDF, evidence, or browser state;
- let an adapter choose a secret outside its installation binding;
- treat a local fixture as evidence of production secret-manager readiness.

The JSON/Mock adapter requires no real external credential. A live connector
cannot ship until a separate reviewed server-side secret-manager boundary is
approved.

## Negative decision matrix

| Attempt | Required behavior |
| --- | --- |
| Missing principal | Reject before installation lookup or adapter call |
| Browser forges project/actor headers | Strip/ignore at the server boundary; use server context |
| Principal is not a member of the project | Safe forbidden/not-found mapping; no resource existence leak |
| Handle is from another project | Safe not-found mapping; no lookup detail or adapter call |
| Stale installation revision | Conflict/stale result; no mutation or adapter call |
| Disabled installation run | Lifecycle rejection; cursor unchanged |
| Missing connector-admin capability | Forbidden; no configuration/resource existence leak beyond policy |
| Cross-project secret reference | Configuration/policy rejection; no secret access |
| Production mode with local experience adapter | Fail closed at startup/operation |
| Retry without failed-run revision/new key | Conflict; no second attempt |

## Required tests

The implementation must cover:

- principal resolution and correlation independent of browser input;
- catalog/install/read/enable/disable/run/retry as separate decisions;
- project membership and two-project isolation;
- forged, stale, disabled, invisible, and cross-project handles;
- safe 401/403/404/409 mappings without existence leaks;
- installation revision races and idempotency-key reuse;
- secret-reference scope and no raw credential in responses/logs/telemetry;
- production-mode rejection of the local experience adapter.

## G1 decisions required

Human approval at S10-10 must confirm the provider-neutral principal seam,
local adapter limits, operation matrix, safe 403/404 mapping, revision rules,
and the exact runtime/authentication boundary. This contract does not authorize
production authentication or external provider execution.
