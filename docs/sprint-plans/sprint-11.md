# Sprint 11 Plan — Free Production-Shaped Trust Boundary and GitHub Public Issues Ingestion

Status: `G2_APPROVED_RELEASE_PREPARATION_PENDING`

Release target: `v0.6.0` only after G1, G2, and G3 approval

Amendment checkpoint (2026-08-13): 69/77 original tasks and all seven
review-remediation tasks are complete. The 18-gate deterministic validation,
full TLS/digest-backed clean Compose acceptance, and 25-gate stateful cold
recovery are green. S11-67 live Teams is superseded as a release gate by the
approved GitHub Public Issues amendment; all 20 amendment tasks are complete.
G2 was approved with an explicit anonymous-quota residual-risk waiver on
2026-08-14. G3 and release remain open. No release claim is made.

## Sprint Goal

Deliver the first real, read-only GitHub Public Issues ingestion slice
through production-shaped identity, authorization, and server-side secret
boundaries while preserving the Sprint 10 connector, evidence, candidate,
isolation, recovery, and release contracts.

The default implementation proposal uses self-hosted Keycloak for Projecta
OIDC and self-hosted OpenBao for runtime connector secrets. Both remain
proposals until G1. Sprint 11 must not require an Azure subscription or select
Azure Key Vault by default.

## Release Meaning

A successful Sprint 11 release means an authenticated Projecta user with
server-owned project membership and `connector-admin` capability can configure
one exact public GitHub repository, trigger one bounded read-only issue/comment
import, and review
the resulting evidence and candidates without exposing provider credentials,
external identifiers, raw payloads, or cross-project existence.

The release does not mean that Projecta has general tenant administration,
generic ABAC, continuous synchronization, webhook ingress, outbound actions,
multiple production connectors, high availability, or a fully managed
production platform. Product version `v0.6.0` does not imply an ontology
version change.

## Cost and Production-Shaped Baseline

Sprint 11 prefers components that are free to self-host and preserve a credible
migration path to managed infrastructure:

| Boundary | Proposed no-subscription baseline | Production-shaped properties | Explicit limitation |
| --- | --- | --- | --- |
| Projecta identity | Keycloak in production mode with PostgreSQL, fixed hostname, TLS edge, and private admin surface | OIDC discovery, signed-token validation, session expiry, roles, health, audit seam | Single instance is not HA |
| Runtime secrets | OpenBao with integrated Raft storage, TLS, least-privilege policy, AppRole-style workload authentication, manual unseal, snapshots, and restore drills | Separate custody, versioned secrets, scoped access, revocation, auditability | Manual unseal causes operator dependency after a cold restart |
| Bootstrap secrets | Untracked, permission-restricted Compose secret files; optionally SOPS plus `age` for encrypted deployment artifacts | Per-service file mounts and encrypted-at-rest operator workflow | Bootstrap transport is not the runtime secret manager |
| Operational state | Existing PostgreSQL with separate database/schema ownership where required | Durable migrations, project predicates, backup and restore | No managed database or HA claim |
| Edge | Existing production web/reverse-proxy boundary with TLS and explicit forwarded-header policy | Same-origin application boundary, fixed external URLs, security headers | Certificate issuance remains operator-owned |
| GitHub Public Issues | Unauthenticated GitHub REST access to one exact synthetic public repository | Real external HTTP, pagination, rate-limit, replay, cursor, and hostile-input boundaries | Public data only; provider capacity is externally limited and no private-resource claim is made |
| CI and acceptance | Deterministic replay fixtures are mandatory; one human-controlled live sandbox journey is a separate G2 gate | Repeatable CI plus real-provider evidence | CI must not depend on live provider availability |

Azure Key Vault, a hosted identity service, managed PostgreSQL, managed TLS,
and managed observability remain future adapters. The provider-neutral ports
must allow those migrations without changing browser, connector, or semantic
contracts.

### Live connector

- **GitHub Public Issues — selected for v0.6.0:** definitely free for the
  credential-free public slice, controllable through a disposable synthetic
  repository, and sufficient to exercise the real provider boundary.
- **Microsoft Teams — experimental/deferred:** the implementation and replay
  tests remain, but live acceptance requires a separately authorized tenant,
  app registration, consent, and disposable channel. It is not a v0.6.0
  production-ready claim.

## Evaluated Alternatives

### Identity

- **Keycloak — proposed:** Apache-licensed, self-hosted, OIDC-capable, supports
  PostgreSQL and production-mode hostname/TLS/readiness controls.
- **Microsoft Entra as Projecta login — deferred:** useful for Microsoft-centric
  deployment, but would couple Projecta login rollout to an external tenant and
  does not solve local or vendor-neutral acceptance.
- **Local experience context — rejected for production:** remains valid only
  for deterministic local and test flows.

### Secrets

- **OpenBao — proposed:** MPL-licensed, Vault-compatible API direction,
  production-ready integrated storage, scoped policies, snapshots, and a clear
  future migration seam.
- **Existing application-encrypted secret store — fallback only:** acceptable
  for local/self-hosted use, but keeping the master key beside the application
  does not establish separate production secret custody.
- **Compose secrets or SOPS plus `age` alone — rejected as runtime manager:**
  useful for bootstrap delivery, but they do not provide runtime lookup,
  versioned rotation, revocation, or service policy by themselves.
- **Azure Key Vault — deferred:** no Azure subscription is assumed; it may be
  added later as another `SecretStore` adapter after a separate decision.

## Carried Decisions and Constraints

- Docker Compose remains the local, CI, and early-production baseline.
- The React browser calls only the typed Application API and never holds a
  connector credential, trusted project header, raw provider payload, or
  authorization authority.
- The production principal is established server-side. Browser claims and
  opaque handles are inputs to validation, not durable grants.
- Connector execution remains bounded and single-attempt. Provider SDKs,
  proxies, and middleware may not add hidden retries.
- Provider input is source evidence, not domain truth. It may create candidates but
  never direct assertions or display-name identity merges.
- PostgreSQL owns operational state; evidence storage owns raw bounded content;
  Fuseki/TDB2 owns semantic graphs. Auth sessions, provider tokens, connector
  cursors, and secret metadata do not enter RDF.
- Replay fixtures remain the canonical CI contract. Live-provider acceptance
  supplements deterministic evidence and cannot replace it.
- Any required ontology term triggers `$projecta-evolve-ontology` and a separate
  human semantic gate before dependent implementation proceeds.
- No paid managed service or cloud subscription may become a required release
  dependency without explicit human approval.

## Acceptance Journeys

1. **Production sign-in and project scope:** A Keycloak user signs in through
   OIDC, receives a secure server-owned session, sees only authorized projects,
   and loses access after logout, expiry, revocation, or membership removal.
2. **Least-privilege installation:** A `connector-admin` binds one allowlisted
   exact public GitHub owner/repository configuration to one Projecta project
   through a server-issued opaque setup handle. A normal reviewer cannot create
   or alter it.
3. **Real read-only import:** One explicit bounded run reads a finite page set
   from a disposable synthetic public GitHub repository and produces immutable evidence,
   source artifacts, and reviewable candidates through the existing lifecycle.
4. **Review and knowledge continuity:** A reviewer confirms an eligible
   candidate and can retrieve its project-scoped knowledge and evidence without
   provider-shaped fields or external identifiers leaking into public types.
5. **Replay and restart:** Repeating the same import and restarting API,
   PostgreSQL, evidence storage, Keycloak, or OpenBao does not duplicate
   evidence, source, candidate, assertion, run outcome, or cursor advancement.
6. **Isolation and stale authority:** Two users, projects, and installations
   cannot observe or operate one another's sessions, memberships, secret
   references, provider resources, evidence, runs, or semantic graphs.
7. **Truthful provider failure:** Provider `403`/`404`/`429`, exhausted rate
   limit, malformed response, invalid pagination link, timeout, and partial pagination produce
   finite terminal outcomes with no hidden retry or unsafe cursor movement.
8. **Secret boundary preservation:** Sealed/unavailable OpenBao fails readiness
   or the affected operation closed; the credential-free GitHub connector does
   not weaken OpenBao, Teams secret, recovery, or leak gates.
9. **Cold recovery:** PostgreSQL, evidence, Keycloak, and OpenBao state restore
   into an isolated stack; manual unseal and workload re-authentication are
   documented; post-restore replay remains idempotent.
10. **Production-shaped edge:** Fixed hostnames, TLS, forwarded-header handling,
    secure cookies, CSRF/state/nonce controls, private management endpoints,
    sanitized logs, readiness, and rollback operate through the Compose
    production profile.

## Dependency Sequence

```text
v0.5.1 compatibility and current-state audit
→ identity, secret, provider, threat, and ontology-reuse contracts
→ G1 architecture/security/semantic approval
→ Keycloak and OpenBao production-shaped Compose boundaries
→ server session, principal, membership, and capability enforcement
→ read-only GitHub Public Issues adapter and existing connector lifecycle integration
→ typed API and browser experience
→ deterministic, disposable-public-repository, failure, isolation, and recovery evidence
→ G2 product/security/semantic approval
→ immutable v0.6.0 preflight
→ G3 exact-commit release approval and publication
```

Tasks S11-15 through the completed Teams implementation remain governed by the
S11-14 G1 approval record. The provider release gate is amended by
[the GitHub Public Issues G1 amendment](sprint-11/g1-amendment-github-public-issues.md).
S11-67 remains deliberately unexecuted and is not a G2/G3 gate. No credential,
work-tenant resource, or non-synthetic provider payload may enter acceptance or
review artifacts.

## Atomic Tasks

Status legend: [ ] pending / [~] in progress / [x] done

### A. Discovery, contracts, and governance

- [x] **S11-01 — Freeze the v0.5.1 compatibility baseline:** Record released
  routes, schemas, connector contracts, migrations, Compose services, release
  evidence, test totals, and the immutable `v0.5.1` target.
- [x] **S11-02 — Define the read-only Teams use case:** Specify actors,
  tenant/team/channel binding, message and reply scope, bounds, consent,
  evidence mapping, acceptance journeys, counterexamples, and non-goals.
- [x] **S11-03 — Audit existing identity and context seams:** Trace local
  experience context, opaque project selection, connector principal resolution,
  public types, audit attribution, and every production-mode rejection.
- [x] **S11-04 — Benchmark free OIDC options:** Compare Keycloak, Entra-backed
  Projecta login, and retained local/test context on license, Compose fit,
  PostgreSQL use, TLS, recovery, revocation, operations, and migration.
- [x] **S11-05 — Define the production identity contract:** Specify issuer and
  audience validation, server session ownership, subject mapping, logout,
  expiry, revocation, clock skew, safe errors, and fail-closed startup.
- [x] **S11-06 — Define project membership and capability policy:** Specify the
  server-owned membership source and the minimal `project-reader`, `reviewer`,
  and `connector-admin` decisions without implementing generic ABAC.
- [x] **S11-07 — Extend the identity threat model:** Cover login CSRF, forged
  issuer/audience, token substitution, replay, session fixation, open redirect,
  stale membership, cookie theft, admin-surface exposure, and forwarded-header
  spoofing.
- [x] **S11-08 — Benchmark free secret options:** Compare OpenBao, the existing
  application-encrypted store, Compose secrets, and SOPS plus `age` across
  custody, bootstrap, rotation, revocation, audit, backup, restore, sealing,
  failure behavior, resource cost, and managed migration.
- [x] **S11-09 — Define the server-side secret-manager contract:** Specify
  project/installation scope, opaque references, version selection, workload
  authentication, caching, rotation, deletion, readiness, safe errors, and
  plaintext lifetime.
- [x] **S11-10 — Define the OpenBao operations proposal:** Specify integrated
  storage, TLS, initialization, manual unseal, recovery-key custody, root-token
  revocation, workload policy, AppRole-style bootstrap, snapshot, restore,
  upgrade, and break-glass procedures.
- [x] **S11-11 — Define the Teams provider contract:** Freeze Graph endpoints,
  least-privilege permissions, pagination, ordering, bounds, provider identity,
  canonical event mapping, throttling, error normalization, and no-hidden-retry
  behavior against current official documentation.
- [x] **S11-12 — Extend the connector threat model for Teams:** Cover consent
  escalation, cross-tenant confusion, SSRF, next-link validation, HTML/content
  handling, oversized replies, external identifiers, token disclosure,
  throttling, deletion/edit semantics, and malicious provider payloads.
- [x] **S11-13 — Audit ontology reuse:** Determine whether released source,
  evidence, candidate, provenance, actor-hint, and project-scope terms answer the
  Teams competency questions; propose `NO_ONTOLOGY_CHANGE_REQUIRED` by default.
- [x] **S11-14 — Approve G1 architecture, cost, security, and semantic scope:**
  Human selects or revises the identity and secret baselines, Teams scope,
  runtime placement, residual risks, ontology outcome, and implementation start.

### B. Production-shaped identity and edge foundation

- [x] **S11-15 — Add an optimized Keycloak image:** Pin the reviewed version,
  enable health and metrics internally, use a non-root immutable image, and ban
  `start-dev` from the production profile.
- [x] **S11-16 — Add isolated Keycloak PostgreSQL ownership:** Create a separate
  database/user or equivalently isolated schema, repeatable initialization, and
  least-privilege grants without sharing Projecta application credentials.
- [x] **S11-17 — Add deterministic realm/client bootstrap:** Version only
  non-secret realm, client, role, and test-user templates; inject bootstrap
  credentials separately and remove one-time bootstrap authority after setup.
- [x] **S11-18 — Configure fixed OIDC hostnames and TLS routing:** Expose only
  required login endpoints through the production edge, overwrite forwarded
  headers, keep management/metrics private, and reject dynamic-host confusion.
- [x] **S11-19 — Add Keycloak readiness and startup ordering:** Make API
  readiness depend on usable OIDC discovery and signing keys in production mode
  without turning transient dependency failures into silent local fallback.
- [x] **S11-20 — Add the server session repository:** Persist opaque session
  state, expiry, revocation, subject/tenant mapping, and safe audit attribution
  in PostgreSQL with migration and project predicates where applicable.
- [x] **S11-21 — Implement OIDC login initiation:** Generate and persist bounded
  state, nonce, PKCE, return-path allowlist, correlation, and expiry without
  storing provider credentials in the browser.
- [x] **S11-22 — Implement the OIDC callback boundary:** Validate issuer,
  audience, signature, state, nonce, PKCE, timestamps, subject, and finite claim
  mappings before creating a server-owned session.
- [x] **S11-23 — Implement secure session cookies and CSRF protection:** Enforce
  `Secure`, `HttpOnly`, appropriate `SameSite`, rotation, bounded lifetime,
  mutation protection, and safe local-development exceptions.
- [x] **S11-24 — Implement logout, expiry, and revocation:** Invalidate the local
  session, handle provider logout where approved, refresh membership on the
  defined cadence, and reject expired or revoked state without fallback.
- [x] **S11-25 — Implement production principal resolution:** Adapt validated
  sessions into the existing connector principal seam and strip browser-supplied
  actor, role, capability, project, and trusted-context headers.
- [x] **S11-26 — Implement project membership storage:** Add server-owned
  user-to-project memberships, finite roles, revisioning, administrative seed
  workflow, and safe removal without building a general tenant-admin product.
- [x] **S11-27 — Enforce capabilities across existing routes:** Apply project
  read, candidate review, and connector-admin decisions consistently to typed
  Application API routes and preserve safe `401`/`403`/`404` behavior.
- [x] **S11-28 — Add the authenticated browser shell:** Add sign-in, callback,
  signed-in identity, authorized project selection, session-expired recovery,
  and logout states without exposing raw claims or tokens.
- [x] **S11-29 — Add identity contract and negative tests:** Cover forged tokens,
  wrong issuer/audience, key rotation, state/nonce/PKCE failures, cookie/CSRF,
  stale membership, cross-project access, and production local-adapter rejection.

### C. OpenBao secret boundary

- [x] **S11-30 — Add a pinned OpenBao production image and configuration:** Use
  TLS, integrated Raft storage, fixed addresses, non-root execution, internal
  health, bounded resources, and no development server mode.
- [x] **S11-31 — Add operator initialization and manual-unseal tooling:** Make
  initialization explicit and idempotent, split recovery keys, prohibit tracked
  keys/root tokens, record safe status only, and fail closed while sealed.
- [x] **S11-32 — Add least-privilege workload policy:** Limit the API runtime to
  versioned connector-secret paths bound to approved project/installation scope;
  deny list-all, arbitrary path, policy, seal, and administration capabilities.
- [x] **S11-33 — Add workload bootstrap authentication:** Inject only the
  minimum one-time AppRole-style bootstrap material through permission-restricted
  Compose secrets, issue short-lived runtime credentials, and support revocation.
- [x] **S11-34 — Implement the OpenBao `SecretStore` adapter:** Resolve, create,
  rotate, and revoke scoped versions behind the existing port with bounded
  caching, zero public plaintext, safe exceptions, and deterministic fakes.
- [x] **S11-35 — Bind connector installations to secret scope:** Ensure an
  installation can reference only secrets authorized for its project,
  connector type, provider tenant, and current revision.
- [x] **S11-36 — Add secret readiness and failure semantics:** Distinguish
  sealed, unavailable, unauthorized, missing, revoked, and stale versions in
  internal telemetry while exposing only finite safe public problems.
- [x] **S11-37 — Add rotation and revocation tests:** Prove new runs use the
  approved current version, in-flight runs keep an immutable snapshot, revoked
  versions fail closed, and no connector reinstall or browser secret is needed.
- [x] **S11-38 — Add OpenBao snapshot and restore tooling:** Produce encrypted,
  integrity-checked isolated snapshots, restore into a clean instance, require
  human unseal, re-authenticate the workload, and reject version mismatch.
- [x] **S11-39 — Extend the secret leak gate:** Scan public API, DOM/storage,
  assets, logs, telemetry, PostgreSQL, RDF, Compose rendering, test artifacts,
  backups, and review packets for seeded secrets, tokens, and forbidden paths.

### D. Read-only Teams adapter and lifecycle integration

- [x] **S11-40 — Add typed Teams installation configuration:** Model only the
  approved tenant/team/channel binding, secret reference, finite capabilities,
  sync bounds, and safe public projection with all provider IDs kept internal.
- [x] **S11-41 — Add the Teams credential provider:** Obtain and cache a bounded
  app-only Graph access token from the scoped secret snapshot, validate token
  lifetime, and prevent token or raw provider errors from crossing the adapter.
- [x] **S11-42 — Implement bounded channel-message retrieval:** Call only
  allowlisted Graph hosts and paths, enforce deadline/page/item/byte limits,
  validate next links, and collect root messages without hidden retry.
- [x] **S11-43 — Implement bounded reply retrieval:** Import replies within the
  approved per-root and total budgets, preserve source hierarchy as evidence
  metadata, and terminate truthfully on truncation or malformed pagination.
- [x] **S11-44 — Normalize Teams messages into `canonical-event.v1`:** Derive
  stable event identity, body hash, timestamps, bounded actor hint, source event
  type, and evidence bytes without treating HTML or display names as truth.
- [x] **S11-45 — Define cursor and edit semantics:** Persist a deterministic
  watermark/checkpoint strategy compatible with Graph ordering and Sprint 10
  idempotency; handle edited, repeated, and deleted observations explicitly.
- [x] **S11-46 — Map provider failures to connector terminal outcomes:** Normalize
  consent, credential, permission, throttling, timeout, invalid body, and partial
  page failures without automatic retry, cursor advancement, or raw leakage.
- [x] **S11-47 — Register the Teams adapter and capabilities:** Add only the
  reviewed read-only inbound capability, keep JSON/Mock deterministic, and reject
  production startup when a required provider boundary is unavailable.
- [x] **S11-48 — Integrate Teams events with the existing semantic lifecycle:**
  Reuse evidence, source, extraction, validation, candidate, provenance, and
  confirmation paths while keeping connector operational state outside RDF.
- [x] **S11-49 — Add deterministic Teams replay fixtures:** Create sanitized,
  bounded message/reply, edit, deletion, pagination, permission, throttling, and
  malformed-response fixtures with no tenant credential or production payload.
- [x] **S11-50 — Add adapter and orchestration tests:** Cover normalization,
  pagination bounds, idempotency, cursor behavior, partial failure, restart,
  replay, cancellation, timeout, and semantic rollback.

### E. Typed API, browser, audit, and operator experience

- [x] **S11-51 — Extend the connector catalog and public API:** Expose Teams as
  a finite read-only type with opaque handles, safe consent/setup guidance,
  bounded status, and no tenant/team/channel raw identifier in public DTOs.
- [x] **S11-52 — Add Teams installation workflows:** Support authorized create,
  update, enable, disable, run, read, and explicit retry through existing
  revision and idempotency contracts.
- [x] **S11-53 — Extend the Connections UI:** Add Teams setup, permission
  guidance, secret-reference-safe status, run progress, terminal outcome,
  reload/stale handling, keyboard operation, and narrow-layout support.
- [x] **S11-54 — Add candidate/evidence continuity UI assertions:** Prove a Teams
  import reaches Review and Knowledge through existing screens without exposing
  provider payloads, raw IDs, secret references, or graph names.
- [x] **S11-55 — Extend correlated audit and telemetry:** Connect login/session,
  membership decision, secret resolution, connector run, candidate lifecycle,
  and terminal outcome through safe correlation and bounded labels.
- [x] **S11-56 — Write identity and secret operator runbooks:** Document initial
  setup, realm/client bootstrap, membership seeding, OpenBao initialize/unseal,
  workload bootstrap, rotation, revocation, backup, restore, and safe escalation.
- [x] **S11-57 — Write the Teams administrator runbook:** Document app
  registration, least-privilege consent, test-channel binding, limits, manual
  sync, permission removal, diagnostics, teardown, and provider-data handling.

### F. Failure, isolation, recovery, and acceptance

- [x] **S11-58 — Add identity and secret failure injection:** Exercise Keycloak
  unavailability/key rotation, stale sessions, membership removal, sealed
  OpenBao, denied policy, expired workload token, and secret rotation races.
- [x] **S11-59 — Add Teams failure and abuse injection:** Exercise `401`, `403`,
  `429`, timeout, oversized content, hostile HTML, invalid next links, partial
  pages, duplicate/edit/delete events, and process interruption.
- [x] **S11-60 — Add multi-user/project/tenant concurrency tests:** Race
  membership changes, installation mutations, syncs, retries, secret rotation,
  and two projects; prove one bounded winner and no existence leak.
- [x] **S11-61 — Extend the production Compose profile:** Add only G1-approved
  identity and secret services, isolated networks/volumes, health checks,
  resource bounds, restart policy, TLS edge, and explicit operator-owned
  bootstrap inputs.
- [x] **S11-62 — Extend backup and restore orchestration:** Coordinate
  PostgreSQL, evidence, Keycloak state, and OpenBao snapshot consistency without
  copying plaintext secrets or mutating shared/production data.
- [x] **S11-63 — Run the isolated cold-recovery drill:** Tear down and restore a
  clean stack, manually unseal, re-establish workload auth, validate sessions
  are safely invalidated or restored per contract, and replay without duplicate.
- [x] **S11-64 — Extend repository contract gates:** Reject dev-mode identity or
  secret servers in production, dynamic issuer/host trust, browser authority,
  broad secret paths, hidden retries, unbounded Graph traversal, raw provider
  fields, and paid-service hard dependencies.
- [x] **S11-65 — Create the deterministic Sprint 11 validation runner:** Compose
  identity, secret, API, web, Teams replay, Semantic Core, ontology, migration,
  security, recovery-contract, documentation, and whitespace gates with native
  exit propagation and no live-provider dependency.
- [x] **S11-66 — Create the clean-Compose acceptance runner:** Start isolated
  production-shaped services, initialize test identity and secrets, execute all
  deterministic journeys, restart services, scan sanitized logs, and clean up
  without masking the first failure.
- [ ] **S11-67 — Run the authorized live Teams sandbox journey:** Use
  human-provided ephemeral credentials and one test channel, import bounded
  messages, verify evidence/candidates/isolation, revoke access, scan artifacts,
  and record only sanitized evidence. **Superseded for v0.6.0 by the approved
  GitHub Public Issues amendment; intentionally remains incomplete.**
- [x] **S11-68 — Verify zero-subscription operation:** Prove all required local,
  CI, recovery, and release gates run without Azure Key Vault, Azure billing, or
  another paid managed service; list deferred Teams prerequisites truthfully.

### G. Review and release

- [x] **S11-69 — Prepare the G2 review packet:** Record selected free baseline,
  architecture, threat controls, API/UI matrix, test totals, disposable public
  GitHub repository
  evidence, recovery evidence, resource measurements, residual risks, and every
  unresolved operational choice.
- [x] **S11-70 — Approve G2 product, security, and semantic readiness:** Human
  reviews production sign-in, project policy, secret custody, real GitHub Public Issues import,
  candidate truthfulness, isolation, recovery, cost constraints, and ontology
  reuse before release preparation.
- [x] **S11-71 — Align the v0.6.0 product version:** Update all product manifests
  and locks together without changing ontology version unless separately
  approved.
- [x] **S11-72 — Freeze the v0.6.0 changelog and release contract:** Document
  added, changed, security, operations, limitations, and upgrade/rollback notes;
  retain a fresh empty `Unreleased` section.
- [x] **S11-73 — Extend the tag workflow:** Require deterministic Sprint 11,
  clean-Compose identity/secret acceptance, recovery, security, repository, and
  release-contract jobs; keep live-provider access deterministic and
  credential-free in public CI.
- [x] **S11-74 — Run the immutable release preflight:** Execute every mandatory
  gate on the exact proposed release commit with clean worktree, clean volumes,
  pinned images, native exit codes, totals, and artifact digests.
- [x] **S11-75 — Approve G3 exact-commit release authorization:** Human names the
  immutable commit approved for annotated `v0.6.0` publication.
- [x] **S11-76 — Publish and verify v0.6.0:** Push only the approved commit and
  annotated tag, follow every required job to terminal success, verify the
  public non-draft release and notes, and preserve failed tags unchanged.
- [ ] **S11-77 — Close Sprint 11 and update M7:** Attach release evidence, record
  remaining single-instance/manual-unseal/public-provider and deferred Teams
  risks, and keep M7 open
  for outbound action governance, continuous sync, additional connectors, HA,
  and broader tenant administration.

## Review Remediation Tasks

Status legend: [ ] pending / [~] in progress / [x] done

- [x] **S11-R01 — Repair the real OIDC login boundary:** Align Keycloak client
  authentication with the code exchange, map forged signatures to finite
  failures, and exercise a protocol-faithful callback path.
- [x] **S11-R02 — Add the operator Teams setup boundary:** Persist opaque,
  single-use setup handles server-side, create scoped OpenBao credentials, and
  compose the resolver without exposing provider identifiers or plaintext.
- [x] **S11-R03 — Decouple Teams credential scope from mutable installation
  state:** Keep credential/config scope stable across enable, disable, and run
  revisions while preserving explicit rotation revisions.
- [x] **S11-R04 — Make Teams incremental ingestion truthful:** Detect replies on
  previously seen roots, handle provider next links consistently, and return
  `truncated` instead of silently clipping content.
- [x] **S11-R05 — Make OpenBao operator tooling executable:** Use the approved
  `bao` CLI consistently and add executable/static coverage for every operator
  script.
- [x] **S11-R06 — Reconcile production Compose and validation contracts:** Keep
  the optimized immutable Keycloak image contract and make S11-65/S11-66 run
  the gates and journeys they claim.
- [x] **S11-R07 — Restore strict quality gates:** Resolve targeted Pyright
  errors, run the complete deterministic matrix, and attach fresh evidence.

## G1 Amendment Tasks — GitHub Public Issues

Status legend: [ ] pending / [~] in progress / [x] done

- [x] **S11-A01 — Approve the provider amendment:** Record that GitHub Public
  Issues replaces live Teams as the v0.6.0 provider gate while all approved
  identity, OpenBao, recovery, semantic, and isolation boundaries remain.
- [x] **S11-A02 — Freeze the GitHub Public Issues use case:** Specify one exact
  public repository, issues/comments scope, actors, bounds, acceptance journeys,
  counterexamples, first-run lookback, and explicit no-write/no-private-data
  exclusions against current official documentation.
- [x] **S11-A03 — Define the provider contract:** Freeze endpoints, headers,
  pagination allowlist, pull-request exclusion, ordering, rate-limit behavior,
  canonical event mapping, and no-hidden-retry semantics.
- [x] **S11-A04 — Extend the connector threat model:** Cover arbitrary-URL SSRF,
  redirects, malicious `Link` headers, hostile Markdown/Unicode, repository
  confusion, oversized content, external identifiers, rate exhaustion, and
  public-data privacy.
- [x] **S11-A05 — Re-run the ontology reuse audit:** Test issue/comment
  competency questions against released source, evidence, candidate,
  provenance, actor-hint, and project terms; retain
  `NO_ONTOLOGY_CHANGE_REQUIRED` only when the governed audit passes.
- [x] **S11-A06 — Add typed credential-free installation configuration:** Model
  exact owner/repository scope, fixed API origin, capabilities, limits, safe
  projection, and a short-lived single-use server setup handle.
- [x] **S11-A07 — Implement the bounded GitHub transport:** Disable redirects
  and automatic retries, construct only allowlisted paths, validate pagination,
  stream with byte limits, and enforce the absolute deadline/request budget.
- [x] **S11-A08 — Map issue observations to canonical events:** Exclude pull
  requests and produce deterministic immutable created/updated evidence with
  opaque revision-aware identifiers.
- [x] **S11-A09 — Map issue-comment observations to canonical events:** Prove the
  parent belongs to an issue in the bound repository and preserve the same
  bounded, opaque, non-authoritative mapping.
- [x] **S11-A10 — Implement cursor, edit, and replay semantics:** Maintain
  independent `(updated_at, id)` watermarks, overlap inclusive provider queries,
  handle timestamp ties, and commit only after durable orchestration success.
- [x] **S11-A11 — Normalize provider failures:** Map rate exhaustion, `403`,
  `404`, `429`, `5xx`, timeout, invalid output/link, and truncation to finite
  existing outcomes without raw leakage or cursor movement.
- [x] **S11-A12 — Register the adapter and capabilities:** Extend the finite
  connector type, descriptor, registry, composition root, and startup contract
  without provider-specific orchestration branches.
- [x] **S11-A13 — Add typed API and browser workflows:** Support authorized
  repository setup, install/update/revoke/run/status, generated types,
  accessibility, narrow layout, and safe credential-free guidance.
- [x] **S11-A14 — Make provider maturity truthful:** Present GitHub Public Issues
  as the v0.6.0 live connector and Teams as experimental/deferred across the
  catalog, UI, runbooks, changelog, review packet, and release notes.
- [x] **S11-A15 — Add sanitized deterministic fixtures and contract tests:**
  Cover issues, comments, edits, state changes, timestamp ties, duplicates,
  pagination, pull-request exclusion, malicious content, and malformed output.
- [x] **S11-A16 — Add failure, security, and isolation tests:** Cover SSRF and
  pagination negatives, limits, deadline, rate exhaustion, authorization,
  concurrent mutations, cross-project scope, leak gates, restart, and rollback.
- [x] **S11-A17 — Add a live acceptance runner:** Parameterize only bounded
  owner/repository plus opaque Projecta context/setup inputs, consume no
  provider token, capture sanitized counts/hashes/timings, prove
  evidence/candidate continuity, and preserve native failure status.
- [x] **S11-A18 — Run the disposable public-repository journey:** Import
  fabricated issue/comment/edit cases, prove pull-request exclusion, replay and
  isolation, sanitize evidence, and archive or delete the test repository after
  acceptance. The r9 baseline passed; the final live edit/replay rerun is
  accepted as a G2 residual risk after anonymous quota exhaustion, with
  deterministic edit/replay provenance contracts retained as release evidence.
- [x] **S11-A19 — Integrate amended release gates:** Add deterministic GitHub
  tests and the credential-free live journey to validation, clean Compose, and
  tag-preflight contracts while retaining Teams replay regression coverage.
- [x] **S11-A20 — Prepare the amended G2 evidence:** Reconcile totals, API/UI
  truthfulness, semantic outcome, live evidence, carried recovery/security
  gates, resource/cost claims, residual risks, and every unresolved choice.

## Mandatory Validation Matrix

Every configured row is blocking except the explicitly superseded live Teams
row. GitHub live acceptance uses a disposable synthetic public repository and
no credential; public CI remains deterministic and provider-independent.

| Gate | Required evidence |
| --- | --- |
| Compatibility | `v0.5.1` release contract, existing typed API, connector, semantic, browser, and recovery regressions pass unchanged or through an explicitly versioned additive migration. |
| Identity | OIDC discovery/signature/issuer/audience, state/nonce/PKCE, session/cookie/CSRF, logout/expiry/revocation, membership, capability, and forged-context tests pass. |
| Secret manager | Initialize/unseal, workload policy, scoped CRUD/version/rotation/revocation, sealed/unavailable behavior, snapshot/restore, and leak tests pass. |
| Teams replay | Sanitized success, pagination, replies, edit/delete, duplicate, permission, throttling, malformed payload, timeout, cancellation, and rollback fixtures pass. |
| GitHub replay | Sanitized issue/comment, edit/state, timestamp-tie, duplicate, pagination, pull-request exclusion, hostile content, rate-limit, malformed payload, timeout, cancellation, and rollback fixtures pass. |
| Live GitHub Public Issues | One disposable synthetic public repository imports without a credential and proves baseline replay/isolation with sanitized evidence. G2 explicitly waives another quota-consuming live edit/replay run; deterministic edit/replay provenance remains blocking. |
| Live Teams | Superseded for v0.6.0; deterministic regression remains required, but no live or production-ready Teams claim is permitted. |
| API and web | Locked dependency sync, format, lint, strict typecheck, unit/integration, API drift, production build, deterministic browser, accessibility, and narrow-layout checks pass. |
| Semantic Core and ontology | Existing project isolation, evidence/candidate/provenance lifecycle, inference/retrieval regressions, and canonical ontology validation pass; no unapproved term is loaded. |
| Compose | Pinned production-mode images, fixed hosts, TLS edge, private management ports, health/readiness, resource bounds, restart, and clean-volume acceptance pass. |
| Recovery | Coordinated PostgreSQL/evidence/Keycloak/OpenBao restore, manual unseal, workload re-authentication, and post-restore idempotent replay pass. |
| Security | Threat-model negatives, dependency audit, secret/token/payload leak scan, cross-user/project/tenant isolation, safe errors, no hidden retry, and bounded provider traversal pass. |
| Cost | Required gates use no Azure subscription, Azure Key Vault, paid managed service, or licensed live-provider tenant; deferred Teams prerequisites are documented separately. |
| Release | G1, G2, immutable preflight, G3 exact SHA, annotated tag, required CI jobs, and public release verification pass. |

## Definition of Done

- Every non-superseded original task and every amendment task is `[x]`; G1,
  amended G1, G2, and G3 approvals identify their exact scope and do not imply
  approval of deferred capabilities. S11-67 remains incomplete by decision.
- A real read-only GitHub Public Issues import crosses authenticated Projecta,
  authorized project, bounded provider, evidence, candidate, review, and
  retrieval boundaries without a provider credential.
- Deterministic replay remains sufficient for public CI; live acceptance uses
  no committed credential or production payload.
- Production mode cannot start or operate with local identity fallback,
  development Keycloak/OpenBao modes, dynamic issuer/host trust, an unsealed
  secret path outside policy, or unavailable required dependencies.
- Project membership, capability, secret scope, provider scope, operational
  predicates, evidence, and semantic graphs remain isolated under negative and
  concurrent tests.
- Provider failure, identity failure, secret failure, restart, and recovery are
  truthful, bounded, auditable, and incapable of direct assertion or hidden
  retry.
- The complete required baseline runs without Azure Key Vault, Azure billing,
  or another paid managed service.
- The annotated `v0.6.0` release is published only from the G3-approved commit,
  or the sprint remains incomplete with the blocker recorded truthfully.

## Non-Goals and Guardrails

- Do not implement any GitHub or Teams write, private repository access,
  provider OAuth/token flow, or external side effect.
- Do not implement webhook ingress, continuous polling, background scheduling,
  or automatic retry.
- Do not add Outlook, Jira, Azure DevOps, Slack, or another live release-gated connector.
- Do not build a general tenant-administration product, generic policy language,
  or full RBAC/ABAC designer.
- Do not require Azure Key Vault, Azure subscription billing, or any paid
  managed identity, secret, database, queue, search, or observability service.
- Do not treat Compose secret mounts, SOPS, environment variables, or the
  application-encrypted local store alone as proof of separate runtime secret
  custody.
- Do not expose Keycloak administration, OpenBao management, health/metrics,
  PostgreSQL, Fuseki, raw provider identifiers, access tokens, secret
  references, external URLs, or provider payloads to the public browser.
- Do not add Kafka, RabbitMQ, Redis, OpenSearch, Kubernetes, a service mesh, or
  a full observability platform without measured volume/SLO evidence and a new
  decision.
- Do not introduce provider-specific domain classes or properties, or change the
  ontology, without competency questions, `$projecta-evolve-ontology`, and
  explicit human semantic approval.
- Do not claim HA or unattended cold restart while the accepted baseline is a
  single Keycloak/OpenBao instance with manual OpenBao unseal.

## Notes / Blockers

- G1 was approved with revisions at S11-14. Keycloak and OpenBao are approved
  baselines subject to immutable digest, resource, security, and recovery
  evidence during implementation. The 2026-08-13 amendment changes only the
  live provider/release gate.
- S11-67 remains blocked by Teams tenant authorization but is no longer a
  v0.6.0 gate. Do not use the currently signed-in work tenant for acceptance.
- GitHub REST behavior and limits are temporally unstable; S11-A02/A03 must
  re-verify current official documentation before implementation.
- OpenBao manual unseal preserves a fully self-hosted no-subscription path but
  introduces operator-dependent cold-start recovery. This residual risk must be
  demonstrated and explicitly accepted at G1 and G2.
- If Keycloak and OpenBao exceed measured single-VM CPU/memory budgets, reopen
  the relevant benchmark rather than silently weakening production mode or
  replacing a boundary with an unreviewed paid service.
- The non-blocking GitHub Actions Node.js runtime warning carried from the
  `v0.5.1` release should be resolved as maintenance without becoming the Sprint
  11 product goal or weakening pinned workflow behavior.

## Planning References

These sources support planning only. S11-A02 and S11-A03 must re-check current
GitHub behavior and limits before implementation. See also the
[G1 amendment](sprint-11/g1-amendment-github-public-issues.md) and the
[implementation guide](sprint-11/github-public-issues-implementation-guide.md).

- [Keycloak production configuration](https://www.keycloak.org/server/configuration-production)
- [Keycloak container guidance](https://www.keycloak.org/server/containers)
- [OpenBao storage configuration](https://openbao.org/docs/configuration/storage/)
- [OpenBao MPL-2.0 license](https://github.com/openbao/openbao/blob/main/LICENSE)
- [Docker Compose secrets](https://docs.docker.com/compose/how-tos/use-secrets/)
- [Microsoft Graph channel messages](https://learn.microsoft.com/en-us/graph/api/channel-list-messages?view=graph-rest-1.0)
- [Microsoft Graph metered API list](https://learn.microsoft.com/en-us/graph/metered-api-list)
- [GitHub REST API authentication](https://docs.github.com/en/rest/authentication/authenticating-to-the-rest-api)
- [GitHub REST issues](https://docs.github.com/en/rest/issues/issues)
- [GitHub REST issue comments](https://docs.github.com/en/rest/issues/comments)
- [GitHub REST rate limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api)
