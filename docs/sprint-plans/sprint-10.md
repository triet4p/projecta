# Sprint 10 Plan — Governed Connector Foundation and v0.5.0

Status: `RELEASE_REMEDIATION`

Target product release: `v0.5.0`

Milestone: M7 increment 1 — Connector and Production Evolution

Baseline: public product release `v0.4.0` at annotated tag commit
`0b36a3eefdd7efa126e44de25a3653f3ebc30c27`

## Sprint Goal

Deliver the first governed connector vertical slice without binding Projecta to
an external vendor: a server-authorized JSON/Mock connector installation imports
bounded canonical events into the existing project-scoped Note, NoteItem,
candidate-review, evidence, provenance, and Graph lifecycle. Connector
installation, event, cursor, idempotency, run, retry, and dead-letter state is
durable operational data; failures are finite and explicit; no connector input
becomes asserted knowledge without the existing human-review boundary.

The sprint ends only after the exact-tag release workflow publishes product
`v0.5.0`. A green local run is necessary but not sufficient: architecture,
security, semantic, product, release-contract, clean-Compose, and tag-triggered
GitHub gates are all mandatory.

## Release Meaning

Product `v0.5.0` proves the connector framework with a deterministic JSON/Mock
adapter. It does not claim a production Teams/Outlook/Jira connector, public
internet readiness, a production identity provider, tenant administration,
outbound action authorization, or production secret-manager integration.

Product `v0.5.0` is not automatically an ontology release. The default semantic
path reuses released Note, NoteItem, evidence, provenance, project isolation,
candidate, and assertion semantics. Any new ontology term requires the complete
`$projecta-evolve-ontology` workflow and explicit human semantic approval before
implementation or release.

## Completed Prerequisite

- [x] **G0 — Close Sprint 7/M5:** S7-47 product/security approval is recorded,
  M5 is complete, and remaining limitations are tracked as non-gating follow-up
  risk in the Sprint 7 review packet.

## Carried Decisions and Constraints

- Docker Compose remains the local, CI, and early-production topology. Sprint
  10 must not introduce Kubernetes, a broker, or a search cluster without a
  measured requirement and a new decision.
- The React client calls only the typed Application API. It never receives a
  trusted project/actor header, RDF identifier, graph name, storage location,
  connector secret, raw provider payload, or connector-internal identifier.
- The first connector runtime stays behind provider-neutral ports. Whether it
  remains inside the Application API process or becomes a separate deployable
  service is decided at G1; no empty service scaffold is allowed.
- PostgreSQL owns connector operational state and read projections. Fuseki/TDB2
  owns semantic source, candidate, asserted, inferred, and provenance graphs.
  Retry count, cursor, installation state, and dead-letter state never enter RDF.
- Raw connector input remains source evidence, not domain truth. It is immutable
  or content-addressed, bounded, retention-aware, and referenced from the
  canonical event without being exposed to the browser.
- The existing local/self-hosted `SecretStore` port may hold opaque references,
  but the JSON/Mock adapter requires no real external credential. A real
  connector cannot ship until a reviewed server-side secret-manager boundary
  exists.
- The local experience adapter is not production authentication. Sprint 10 adds
  a provider-neutral authorization seam and deterministic policy tests; a real
  OIDC provider and tenant/RBAC administration remain Sprint 11+ work.
- Connector execution is single-attempt by default. No SDK, HTTP client,
  scheduler, proxy, or worker may add hidden retries. A retry is a new explicit,
  auditable operation governed by idempotency and revision rules.
- Connector events may create source artifacts and candidates, but never direct
  asserted Requirements, Tasks, relations, or external identity merges.
- Existing `v0.4.0` compatibility is mandatory. A Sprint 10 route, schema,
  migration, or projection may not silently rewrite released RDF or invalidate
  the current browser workflows.

## Definitions

- **Connector type:** Provider-neutral adapter identifier plus a finite,
  allowlisted capability declaration.
- **Connector installation:** Project-scoped operational configuration,
  authorization state, secret references, revision, and enabled/disabled state.
- **Canonical event:** Validated, bounded envelope containing event identity,
  connector/source type, external resource reference, project scope, actor hint,
  occurrence time, content reference/hash, and event type. It contains no domain
  assertion.
- **Sync run:** One explicitly requested, bounded connector execution with one
  start record and exactly one terminal outcome.
- **Cursor:** Opaque connector checkpoint advanced only after the corresponding
  source and semantic transaction succeeds.
- **Dead letter:** Sanitized operational record for an event that reached a
  terminal non-success outcome. It is not an RDF fact and never contains a raw
  secret.
- **Replay:** Reprocessing the same canonical event identity and body. It returns
  the original outcome without a second source artifact or semantic mutation.
- **Retry:** A new authorized operation after a failed run. It preserves the
  original event identity and records its relationship to the prior run.

## Acceptance Journeys

1. **Authorized import:** A server-authorized connector administrator installs
   the JSON/Mock connector for one project, runs a bounded fixture import, and
   sees one truthful terminal result.
2. **Evidence lifecycle:** Imported content appears as a project-scoped source
   Note/NoteItem, produces reviewable candidates, preserves evidence and
   provenance, and appears in Graph/Review Queue without automatic assertion.
3. **Idempotent replay:** Importing the identical event twice produces one
   source/candidate set, one advanced cursor, and an explicit replay response.
4. **Isolation:** A forged, stale, disabled, invisible, or cross-project
   installation/event handle fails closed without revealing another project's
   existence or data.
5. **Failure truthfulness:** Malformed payload, unsupported capability,
   unavailable storage, semantic rejection, timeout, and interrupted execution
   each produce a finite correlated terminal state with no partial semantic
   write and no cursor advance.
6. **Recovery:** Connector installation, cursor, inbox, and run state survive an
   API/PostgreSQL restart. Backup/restore followed by replay does not duplicate
   semantic data.
7. **Accessible operation:** The Connections screen exposes installation,
   capability, last-success, current run, replay/failure, and recovery state with
   keyboard-accessible controls and a non-visual tabular representation.

## Dependency Sequence

```text
current-state and use-case audit
→ contracts, threat model, persistence model, ontology reuse-gap
→ G1 architecture/security/semantic approval
→ PostgreSQL, evidence storage, authorization, connector kernel
→ JSON/Mock adapter and semantic lifecycle integration
→ typed API and Connections UI
→ focused, failure-injection, recovery, and full regression gates
→ G2 product/security/semantic acceptance
→ v0.5.0 version and changelog freeze
→ clean release preflight
→ G3 explicit release authorization
→ annotated tag v0.5.0
→ tag-triggered CI and public release verification
```

Tasks S10-11 onward are blocked until G1 is explicitly approved. A semantic
change, if the reuse-gap finds one, is additionally blocked on its own human
ontology approval.

## Atomic Tasks

Status legend: [ ] pending / [~] in progress / [x] done

### A. Discovery, contracts, and governance

- [x] **S10-01 — Freeze the v0.4.0 compatibility baseline:** Record released
  public routes, projections, component versions, canonical test totals, Compose
  profiles, and tag-publication evidence that Sprint 10 must preserve.
- [x] **S10-02 — Write the connector vertical-slice use case:** Define actors,
  preconditions, the seven acceptance journeys, counterexamples, bounded fixture
  data, explicit non-goals, and user-visible success/failure outcomes.
- [x] **S10-03 — Define the canonical event contract:** Specify allowlisted
  fields, stable event identity, project scope, actor hint, external reference,
  content reference/hash, occurrence time, type, size limits, canonical hashing,
  and validation errors without embedding domain assertions.
- [x] **S10-04 — Define the connector adapter contract:** Specify discovery,
  capability declaration, installation validation, bounded pull/import, opaque
  cursor, resource fetch, identity hint, cancellation, deadline, and terminal
  error behavior for every adapter.
- [x] **S10-05 — Define the connector authorization contract:** Specify the
  server-owned principal, project membership, connector-admin permission,
  install/run/read/retry decisions, stale-revision behavior, and safe 403/404
  mapping without treating the browser or connector as authority.
- [x] **S10-06 — Threat-model connector ingestion:** Cover forged scope,
  cross-project replay, confused deputy behavior, SSRF/path traversal, payload
  bombs, malicious JSON, secret/log leakage, cursor tampering, duplicate
  delivery, partial commit, and disabled-installation races.
- [x] **S10-07 — Define the PostgreSQL operational model:** Specify installation,
  event inbox, sync run, cursor, attempt, idempotency, dead-letter, audit index,
  revision, transaction, retention, migration, backup, and rollback semantics.
- [x] **S10-08 — Define the raw-evidence storage contract:** Specify immutable or
  content-addressed writes, bounded reads, content type/size allowlists, hashes,
  retention metadata, project scope, safe deletion policy, and sanitized errors.
- [x] **S10-09 — Complete the ontology reuse-gap audit:** Test competency and
  semantic-commitment gates for connector source provenance and external
  references; record `NO_ONTOLOGY_CHANGE_REQUIRED` when released semantics are
  sufficient, otherwise prepare a `PROPOSAL_ONLY` review packet without changing
  production vocabulary.
- [x] **S10-10 — Approve G1 architecture/security/semantic boundaries:** Human
  approves or revises the connector/event/policy/persistence/evidence contracts,
  threat model, ontology reuse outcome, release gates, and the location of the
  first runtime before implementation begins.

### B. Durable operational and evidence foundation

- [x] **S10-11 — Add the PostgreSQL Compose dependency:** Add pinned local,
  system-test, and production-shaped configuration, health/readiness checks,
  named persistence, non-default credentials, and no host-public port by default.
- [x] **S10-12 — Add deterministic operational migrations:** Provide an
  idempotent, versioned, fail-explicit migration entry point that runs separately
  from concurrent application replicas and has a documented rollback boundary.
- [x] **S10-13 — Create the connector-installation schema:** Persist project
  scope, connector type, capability snapshot, opaque secret references, enabled
  state, revision, and safe timestamps with uniqueness and foreign-key rules.
- [x] **S10-14 — Create the event-inbox and idempotency schema:** Persist canonical
  event identity, canonical body hash, content reference, project/installation
  scope, accepted outcome, and conflict detection without duplicating raw secrets.
- [x] **S10-15 — Create the sync-run, cursor, and dead-letter schema:** Persist one
  start and one terminal outcome per run, opaque checkpoint revisions, explicit
  retry lineage, bounded sanitized failure metadata, and no implicit attempt.
- [x] **S10-16 — Define the operational repository ports:** Expose finite typed
  operations for installations, inbox claims/replays, runs, cursors, retries,
  dead letters, and audit lookup without leaking SQL rows into domain services.
- [x] **S10-17 — Implement the PostgreSQL repositories:** Implement the approved
  ports with parameterized statements, bounded queries, optimistic revisions,
  transactions, and project predicates on every access.
- [x] **S10-18 — Make event claim and cursor advance atomic:** Prove that one
  canonical event wins concurrent ingestion, a body mismatch conflicts, semantic
  failure rolls back the cursor, and replay returns the committed outcome.
- [x] **S10-19 — Validate migration and persistence lifecycle:** Test empty
  bootstrap, repeated migration, upgrade, restart, concurrent claim, rollback,
  unavailable database, pool exhaustion, and deterministic cleanup.
- [x] **S10-20 — Implement the evidence object-store port:** Add content-addressed
  put/get/metadata operations with project scope, bounded streaming, digest
  verification, retention metadata, and no list-all or arbitrary-path capability.
- [x] **S10-21 — Implement the local/Compose evidence adapter:** Store JSON/Mock
  evidence on a dedicated persistent volume through the approved port while
  preserving a future S3-compatible adapter seam.
- [x] **S10-22 — Test evidence safety:** Cover oversize content, unsupported media
  type, digest mismatch, path traversal, cross-project access, interrupted write,
  missing content, restart persistence, and sanitized logging.

### C. Authorization, policy, and secret boundaries

- [x] **S10-23 — Add the connector-principal port:** Resolve a server-owned actor,
  allowed projects, safe roles/capabilities, and request correlation independently
  of browser-supplied project or actor data.
- [x] **S10-24 — Preserve the local experience adapter:** Adapt the current finite
  allowlist to the connector-principal port for local/test use and keep it
  disabled or fail-closed in production mode.
- [x] **S10-25 — Implement connector policy checks:** Authorize catalog, install,
  enable/disable, run, inspect, and retry independently with project scope,
  installation revision, connector capability, and least privilege.
- [x] **S10-26 — Bind connector secrets by opaque reference:** Reuse the approved
  `SecretStore` port without returning, logging, hashing into telemetry, or
  persisting raw credentials in connector tables, RDF, or browser state.
- [x] **S10-27 — Add authorization and secret negative tests:** Reject missing
  principal, forged project, stale handle/revision, disabled installation,
  insufficient role, cross-project secret reference, and production-mode local
  adapter startup without leaking resource existence or secret material.

### D. Connector kernel and JSON/Mock adapter

- [x] **S10-28 — Implement typed connector contracts:** Add finite models for
  capabilities, installation snapshots, canonical events, sync commands,
  outcomes, cursors, retry lineage, and sanitized connector errors.
- [x] **S10-29 — Implement the connector registry:** Resolve only allowlisted
  adapters by explicit type, reject duplicates/unknown types, and expose a finite
  capability catalog without importing provider code into semantic services.
- [x] **S10-30 — Implement the installation service:** Create, read, update,
  enable, and disable project-scoped installations with policy, revision,
  capability, secret-reference, and audit checks.
- [x] **S10-31 — Implement the deterministic JSON/Mock adapter:** Read only the
  approved bounded fixture/resource format, declare inbound-import capability,
  emit canonical events and opaque cursors, and perform no network or semantic
  mutation itself.
- [x] **S10-32 — Implement canonical event validation:** Validate identifiers,
  project/installation binding, event types, timestamps, content hashes,
  references, size/count limits, and canonical serialization before inbox claim.
- [x] **S10-33 — Implement single-attempt sync orchestration:** Create one run,
  enforce one absolute deadline, call the adapter once, validate/claim each
  event, persist one terminal result, and never hide adapter/storage/Core errors.
- [x] **S10-34 — Implement explicit replay semantics:** Return the original
  successful outcome for the same canonical event/hash and return a typed conflict
  for identity reuse with different content.
- [x] **S10-35 — Implement cursor commit semantics:** Advance the opaque cursor
  exactly once after source evidence and Semantic Core commit, and leave it
  unchanged on cancellation, timeout, conflict, validation, storage, or Core
  failure.
- [x] **S10-36 — Implement dead-letter capture:** Record only allowlisted terminal
  failure class, safe detail, correlation, event/install handles, and timestamps;
  never store raw payloads, secrets, stack traces, SQL, RDF IRIs, or storage paths.
- [x] **S10-37 — Implement explicit retry:** Require authorization, the expected
  failed-run revision, a new operation idempotency key, and visible linkage to the
  prior run while preventing automatic loops or duplicate semantic mutation.
- [x] **S10-38 — Enforce bounded execution:** Configure adapter, database,
  evidence-store, Semantic Core, proxy, and UI budgets so the outer boundary can
  always return a correlated terminal result without nested retries.

### E. Existing semantic lifecycle integration

- [x] **S10-39 — Map canonical events to source drafts:** Convert approved event
  content into bounded structured Note/NoteItem input with `connector` source kind,
  server-derived project/actor context, exact source offsets, and content hash.
- [x] **S10-40 — Commit connector sources through Semantic Core:** Reuse the
  released project-scoped source/provenance mutation path, SHACL validation,
  named-graph routing, atomic rollback, and opaque response projection.
- [x] **S10-41 — Preserve candidate and assertion separation:** Ensure imported
  source content produces only reviewable candidates, never direct assertions or
  inferred-as-asserted facts, and retains its source/evidence chain after review.
- [x] **S10-42 — Verify Graph and Review Queue projection:** Show imported Notes,
  NoteItems, and candidates through existing bounded handles, graph/table parity,
  evidence, lifecycle, provenance, and freshness fields without an RDF migration.
- [x] **S10-43 — Add connector lifecycle integration tests:** Cover successful
  import, abstention, validation failure, candidate review, evidence lookup,
  Graph projection, replay, restart, and no partial/cross-project semantic write.

### F. Typed Application API and Connections UI

- [x] **S10-44 — Add the finite connector catalog API:** Return allowlisted
  connector types and safe capability descriptions without provider modules,
  credentials, storage details, or administrative scope leakage.
- [x] **S10-45 — Add installation APIs:** Expose project-scoped create/read/update,
  enable/disable operations with opaque revision-bound handles, policy checks,
  idempotency, finite pagination, and typed problems.
- [x] **S10-46 — Add sync and retry APIs:** Expose explicit run, status, dead-letter
  summary, and retry operations with bounded polling, operation correlation,
  revision checks, and no arbitrary job/connector execution.
- [x] **S10-47 — Add connector public projections:** Map internal rows, event IDs,
  content references, SQL/storage details, and exceptions into allowlisted public
  DTOs with truthful pending/succeeded/replayed/failed/cancelled states.
- [x] **S10-48 — Update the API contract and generated client:** Document routes,
  schemas, error mapping, auth seam, idempotency, limits, and examples; regenerate
  the TypeScript client and keep the drift gate deterministic.
- [x] **S10-49 — Build the Connections screen:** Add connector catalog,
  installation list/detail, JSON/Mock setup, enable/disable, explicit run/retry,
  and last-run/cursor/dead-letter summary using the existing workspace shell.
- [x] **S10-50 — Implement truthful Connections states:** Distinguish loading,
  healthy empty, unavailable, forbidden/not-found, running, succeeded, replayed,
  failed, cancelled, stale, disabled, and retry-conflict states with no fallback
  data or optimistic success.
- [x] **S10-51 — Add accessible connector operation:** Provide labels, focus
  management, live announcements, keyboard operation, confirmation for mutations,
  narrow-layout support, and a table/list equivalent for every status view.
- [x] **S10-52 — Test the web connector workflow:** Add unit/component and
  deterministic Playwright coverage for install, run, replay, failure, retry,
  stale revision, forbidden scope, persistence after reload, and secret/ID absence.

### G. Observability, security, operations, and recovery

- [x] **S10-53 — Extend correlated connector telemetry:** Emit one start and one
  terminal event with safe boundary, operation, connector type, project-safe
  scope, attempt mode, outcome, duration, count, and replay fields.
- [x] **S10-54 — Persist connector audit records:** Record authorized
  install/enable/disable/run/retry decisions and terminal outcomes with actor-safe
  attribution, revision, correlation, and no raw payload or credential.
- [x] **S10-55 — Extend the secret and payload leak gate:** Scan API/web responses,
  DOM/storage, built assets, PostgreSQL safe columns, RDF, logs, telemetry, review
  artifacts, and Compose config for seeded credentials and forbidden raw payload.
- [x] **S10-56 — Add connector failure injection:** Prove truthful behavior for
  PostgreSQL/evidence/Core unavailability, timeout, process interruption,
  malformed adapter output, dead-letter persistence failure, and restart during a
  run, including cursor and semantic rollback assertions.
- [x] **S10-57 — Add isolation and concurrency stress tests:** Race duplicate
  events, retries, disable-versus-run, and two projects/installations; prove one
  winner, bounded work, no leaked existence, and no cross-project data.
- [x] **S10-58 — Add connector backup/restore tooling:** Back up and restore the
  connector PostgreSQL schema plus evidence volume with documented consistency,
  version checks, failure handling, and no mutation of shared/production data.
- [x] **S10-59 — Run the recovery drill:** Restore into an isolated clean stack,
  verify installations/cursors/runs/evidence, replay the last event, and prove no
  duplicate source, candidate, assertion, or cursor advancement.
- [x] **S10-60 — Write connector user and operator runbooks:** Document local
  JSON/Mock setup, permissions, import format/limits, status/retry behavior,
  backup/restore, reset, diagnostics, production-disabled boundaries, and safe
  escalation without claiming real-connector readiness.

### H. Validation, review, and v0.5.0 publication

- [x] **S10-61 — Create the Sprint 10 validation runner:** Compose all configured
  API, web, Semantic Core, ontology, migration, connector, contract, security,
  documentation, and whitespace checks; propagate every native nonzero exit and
  reject unconfigured or skipped required gates.
- [x] **S10-62 — Create the clean-Compose acceptance runner:** Start isolated
  clean volumes, migrate PostgreSQL, run the seven acceptance journeys through
  the production web image, restart API/web/PostgreSQL, scan correlated logs, and
  always clean up without masking the first failure.
- [x] **S10-63 — Create the isolated recovery runner:** Automate backup, teardown,
  clean restore, service readiness, state verification, replay verification, log
  scanning, and cleanup with nonzero exit on any mismatch.
- [x] **S10-64 — Extend repository contract gates:** Reject authority-bearing
  defaults, hidden retries, unbounded connector operations, raw IDs/storage
  details in public types, browser connector authority, missing project predicates,
  and connector operational state modeled in RDF.
- [x] **S10-65 — Extend the tag release workflow:** Add Sprint 10 validation,
  clean connector system acceptance, recovery, frontend format check, and
  connector security jobs as required `publish` dependencies with no
  `continue-on-error` or release bypass.
- [x] **S10-66 — Prepare the Sprint 10 review packet:** Record architecture,
  security, semantic reuse outcome, API/UI matrix, migrations, acceptance
  evidence, test totals, clean logs, recovery evidence, residual risks, release
  notes, and exact unresolved choices without claiming unrun checks.
- [x] **S10-67 — Run the complete pre-release validation:** From a clean checkout
  and clean volumes, run every mandatory gate in the release matrix, attach exact
  command/output evidence, and reopen the owning task for any failure, skip,
  warning treated as failure, secret leak, flaky rerun, or undocumented baseline
  change.
- [x] **S10-68 — Approve G2 product/security/semantic readiness:** Human reviews
  the real browser journey, isolation, evidence/candidate truthfulness, connector
  policy, failure/recovery behavior, semantic reuse outcome, and residual risks;
  approval does not yet authorize a release tag.
- [x] **S10-69 — Align product version 0.5.0:** Update `VERSION`, API project/lock
  and runtime version, web package/lock, and Semantic Core Maven version together;
  do not rename or imply an ontology release without separate approval.
- [x] **S10-70 — Freeze the v0.5.0 changelog section:** Write user-facing Added,
  Changed, Fixed, and Security notes as applicable, date the `0.5.0` section, and
  retain a fresh empty `Unreleased` section above it.
- [x] **S10-71 — Verify the v0.5.0 release contract:** Pass release-contract unit
  tests and `check_release_contract.py --tag v0.5.0`; reject any manifest,
  changelog, tag-shape, or rendered-notes mismatch.
- [x] **S10-72 — Re-run the immutable release preflight:** On the exact proposed
  release commit, pass every matrix gate again with no source change afterward;
  record commit SHA, image identifiers, totals, and artifact digests.
- [x] **S10-73 — Approve G3 release authorization:** Human explicitly authorizes
  publication of the exact validated commit as `v0.5.0`; automated green status,
  prior sprint approval, or approval of a different SHA is insufficient.
- [x] **S10-74 — Commit and push the release contract:** Create the reviewed
  release commit, push it, verify the remote SHA matches the approved SHA, and
  make no post-approval code or generated-artifact change.
- [x] **S10-75 — Create and push annotated tag v0.5.0:** Tag only the G3-approved
  commit, verify annotation and target locally, push the single exact tag, and do
  not move or recreate it after publication begins.
- [~] **S10-76 — Verify tag-triggered release gates:** Follow every required
  GitHub Actions job to terminal success; any cancelled, skipped-required,
  neutral, timed-out, or failed job blocks publication and keeps Sprint 10 open.
- [ ] **S10-77 — Verify the public v0.5.0 release:** Confirm the release is public,
  non-draft, non-prerelease, points to the immutable annotated tag, and contains
  only the matching changelog section.
- [ ] **S10-78 — Close Sprint 10 without closing M7:** Attach publication evidence,
  mark Sprint 10 complete, update the global plan, and retain M7 in progress for
  production authentication, secret management, and the first real connector.

### First tag attempt and remediation

- G3 authorized commit `dd1fcccca18647238bf37731fde6c5a7e8fc7726`
  specifically as `v0.5.0` on 2026-08-11.
- Remote `main` and the annotated `v0.5.0` tag were verified at that commit; the
  tag object is `01638a4ec676d75610e03ac6dc6b6023f0a67fde`.
- Tag workflow run `31463795588` completed with `system` and
  `sprint10-recovery` failures. Every other required validation, acceptance,
  security, format, API, web, Semantic Core, repository, and release-contract
  job succeeded; `publish` was correctly skipped.
- Root causes were a legacy system runner missing the new required connector
  PostgreSQL Compose variables, repository-source tests evaluating a host-only
  path during container collection, and recovery port parsing assuming a single
  Docker binding. Remediation is locally validated and awaits a new immutable
  candidate plus fresh release authorization.
- The published tag has not been moved or recreated. Sprint 10 remains open
  until a corrected tag workflow and public release both succeed.

## Mandatory Release Matrix

Every row is blocking. A required test added by Sprint 10 may not be skipped,
xfail, quarantined, retried until green without root-cause evidence, or hidden
behind `continue-on-error`. Existing intentional baseline skips must be listed in
the review packet and may not increase without explicit approval.

| Gate | Required evidence before G3 and tag creation |
| --- | --- |
| Release contract | `python -m unittest discover -s scripts/tests -p "test_*.py"` and `python scripts/check_release_contract.py --tag v0.5.0` pass; all component manifests and dated changelog agree. |
| API | Locked dependency sync, Ruff, strict Pyright, full Pytest, connector focused/integration tests, migration tests, authorization tests, and failure injection pass. |
| Web | `npm ci`, high-severity audit, Prettier check, API drift, typecheck, lint, Vitest, Nginx contract, production build, deterministic Playwright, and real-stack connector journey pass. |
| Semantic Core | `mvn --batch-mode verify` passes, including project isolation, source/provenance lifecycle, rollback, replay, and Graph/Review Queue projection regressions. |
| Ontology | Canonical Compose ontology suite passes at no less than the released 140-check baseline plus every approved Sprint 10 check; no new term is loaded without its own human-approved review and migration/version path. |
| PostgreSQL and evidence | Clean migration, repeated migration, restart, concurrency, rollback, bounded evidence, backup, restore, and replay-after-restore checks pass. |
| Repository contracts | UI contract, implicit-behavior, health, public-type denylist, project-predicate, no-hidden-retry, no-operational-RDF, Markdown/whitespace, and secret/payload leak checks pass. |
| Clean Compose | Isolated production-image startup reaches truthful readiness; all seven acceptance journeys pass; restart persists state; logs are correlated and sanitized; cleanup succeeds. |
| Recovery | Isolated backup/restore completes and the post-restore replay proves no duplicate source, candidate, assertion, run outcome, or cursor advancement. |
| Security | Threat-model negative tests, authorization/isolation matrix, dependency audit, seeded-secret scan, payload/ID leak scan, bounded-input tests, and safe-error assertions pass. |
| Human acceptance | G1 and G2 are recorded; G3 explicitly names the exact release commit approved for tag publication. |
| Tag workflow | Required release-contract, API, web, Semantic Core, repository-contract, connector-system, recovery, and publish jobs all finish successfully for annotated tag `v0.5.0`. |

## Definition of Done

- Every S10 task is `[x]`; every conditional ontology task, if triggered, is
  separately human-approved and complete.
- The seven acceptance journeys pass against clean production-shaped Compose
  images and isolated state.
- The connector is deterministic, project-scoped, idempotent, bounded,
  fail-explicit, restart-safe, recoverable, and incapable of direct assertion.
- PostgreSQL and evidence backup/restore evidence is attached and replay after
  restore creates no duplicate semantic or operational state.
- No required gate is skipped, flaky, allowed to fail, or reported from an
  unconfigured command; existing skips are enumerated and unchanged or approved.
- No secret, raw connector payload, trusted context, SQL/storage detail, RDF IRI,
  internal handle, stack trace, or provider-shaped object leaks through public
  responses, browser state/assets, logs, telemetry, RDF, fixtures, or review
  evidence.
- G1, G2, and G3 approvals are recorded with exact scope; G3 identifies the
  immutable release commit.
- The annotated `v0.5.0` tag points to that commit, every tag-triggered required
  job succeeds, and the public GitHub Release is verified.
- `docs/PLAN.md` marks Sprint 10 complete while M7 remains in progress for the
  first real connector and production identity/secret boundaries.

## Non-Goals and Guardrails

- Do not implement Teams, Outlook, Jira, Slack, webhook delivery, polling,
  external OAuth consent, or external task synchronization in Sprint 10.
- Do not implement outbound connector actions, messages, replies, task creation,
  uploads, or automatic external side effects.
- Do not claim production authentication, RBAC/ABAC administration, tenant
  administration, public internet exposure, or production secret management.
- Do not migrate all existing Sprint 7 SQLite profile/draft state merely to make
  the topology look uniform; migrate only through a separately reviewed,
  tested, user-data-safe plan.
- Do not add Kafka, RabbitMQ, Redis, OpenSearch, Kubernetes, a service mesh, or a
  full observability platform without measured volume/SLO evidence.
- Do not expose arbitrary connector execution, filesystem paths, object-store
  keys, SQL, SPARQL, RDF graphs, external resource IDs, or provider payloads.
- Do not create connector-specific Requirement/Task classes, merge external
  identities by display name, or add ontology terms for installation, cursor,
  retry, dead-letter, UI, or job state.
- Do not publish `v0.5.0` manually from `main`, from a lightweight/moving tag,
  with mismatched manifests, with incomplete release notes, or while any required
  gate is non-successful.

## Expected Artifacts

```text
docs/use-cases/json-mock-connector.md
docs/architecture/connector-contract.md
docs/architecture/canonical-event-contract.md
docs/architecture/connector-authorization.md
docs/architecture/connector-threat-model.md
docs/architecture/connector-operational-storage.md
docs/architecture/connector-evidence-storage.md
docs/ontology/sprint-10-connector-reuse-gap.md
docs/sprint-plans/sprint-10/review-packet.md
docs/sprint-plans/sprint-10/g2-review-packet.md
docs/sprint-plans/sprint-10/artifacts/
apps/api/src/projecta_api/connectors/
apps/api/src/projecta_api/operational/
apps/api/tests/test_connector_*.py
apps/web/src/screens/ConnectionsScreen.tsx
apps/web/tests/e2e/sprint10*.spec.ts
scripts/run_sprint10_validation.ps1
scripts/run_sprint10_acceptance.ps1
scripts/run_sprint10_recovery.ps1
scripts/check_sprint10_repository_contract.py
docs/runbooks/sprint-10-connectors.md
docs/runbooks/sprint-10-operations.md
compose.yaml
compose.dev.yaml
compose.prod.yaml
.github/workflows/release.yml
CHANGELOG.md
VERSION
```

Paths are planning targets, not authorization to add empty scaffolding. Create
only artifacts needed by the working vertical slice, and record the exact file,
test, and validation evidence in each completed task summary.

## Notes / Blockers

- G1 is the first blocking gate. No implementation task may be marked in
  progress before its architecture/security/semantic scope is approved.
- The ontology reuse-gap defaults to reuse. If a connector-source competency
  question cannot be answered with released terms, stop dependent semantic work,
  invoke `$projecta-evolve-ontology`, and obtain explicit approval for that exact
  proposal; Sprint 10 approval does not pre-approve vocabulary.
- PostgreSQL connector state and the evidence volume are new stateful boundaries.
  Their migration, backup, restore, ownership, and failure behavior are release
  requirements, not follow-up documentation.
- The JSON/Mock adapter is the only canonical deterministic connector. Live
  external-provider checks cannot replace or weaken the deterministic release
  gates.
- A published release is the terminal condition. Passing implementation tests
  or preparing a tag without verifying the tag-triggered public release does not
  complete Sprint 10.
