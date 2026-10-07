# Changelog

All notable changes to Projecta will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and Projecta uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Added bounded native project data export under the approved projecta-portable.v1 contract, including cross-store writer exclusion fencing, typed schema validation across semantic TriG, evidence objects, application workflows, connectors, review decision receipts, and correction burden events, with hard resource bounds and explicit export confirmation.

- Kept graph-backed exact-span review digests distinct from LocalEvidenceStore
  object references while preserving required connector-inbox evidence closure.

- Added a hybrid-online Microsoft Visual C++ v14 prerequisite to the unsigned
  0.7.0 Windows 11 x64 build path. Package provenance now records selected
  source inputs, their base-revision meaning, runtime archive identities, and
  hashes for derived payload files; the installer receipt binds its source
  scripts and pinned NSIS distribution/compiler/license inputs. The R1 package
  and unsigned NSIS candidate were built locally and independently audited.
  An isolated developer-host frozen-runtime smoke reached all four service
  readiness checks, recorded a source-bound manual approval receipt without a
  model/provider, persisted it across stop/restart, and safely rejected a
  fixed-port collision. The NSIS installer itself remains unrun; no clean-host
  proof, public download, or signed-release eligibility is established.

- Added explicitly requested, locally routed item/type/link suggestions for
  confirmed manual captures, with revision-bound caching, daily budgets, and
  append-only human decisions. No model call runs during capture or reads;
  production remains disabled and suggestions do not write graph assertions.

- Added controlled relations between distinct, same-project manual captures
  with current confirmation receipts and deterministic shared-source evidence.
  Manual predicate selection is zero-model; local assistance can propose only
  an allowlisted predicate. Confirm/reject decisions append receipts and never
  materialize graph relations.
- Added digest-only, project- and actor-scoped authoring metrics for local
  inference attempts, zero-model workflows, correction burden, and
  receipt-backed accepted assertions. Confirm receipts alone do not count as
  materialization; no source text, prompts, or provider payloads enter telemetry.

- Exposed human-authored exact-span capture from Notes and returned completed
  captures directly to the Review Queue, making the zero-model workflow
  reachable through normal workspace navigation.

- Added optional directory-backed serving of the compiled React SPA from the
  Application API for a same-origin local package path. Missing or invalid
  configured assets fail readiness instead of masquerading as a usable install.

- Added a Windows 11 x64 per-user launcher path with loopback-bound managed
  services, CurrentUser DPAPI secrets, readiness/status/stop controls, and
  hash-verified whole-state backup/restore with rollback. The owner-authorized
  unsigned 0.7.0 test-pre-release exception applies only to that exact version
  and channel; it does not establish clean-Windows readiness or signed-release
  eligibility.

- Added validated native project-data deletion under the approved projecta-deletion.v1 contract: discoverable per-project Delete action with explicit typed-identity confirmation, per-store purge across semantic graphs, evidence, SQLite, PostgreSQL history (via a narrow transaction-local purge exception), import-ledger scope entries, registry and selections, with truthful deleted/refused outcomes, busy/cancel no-mutation behavior, interruption recovery, persisted empty catalog on last-project delete with fresh import afterwards, and launcher restart guidance. Verified on isolated disposable native roots with real browser journeys.
- Added validated manual portable-project import under the approved projecta-portable.v1 contract: full archive validation before any live change, explicit owner preview/confirmation/cancel, staged-copy apply with quiesced services and catalog-last publication, durable interrupted-recovery journaling with fail-closed restart behavior, idempotent exact-replay, and finite tamper/partial/version/conflict/unauthorized responses with no implicit approval or materialization. Verified on isolated disposable native roots with real browser journeys.
### Fixed

- Corrected the native launcher path: approved first-run workspace provisioning
  replaces the previous setup blocker; Semantic Core reads the packaged shapes
  directory instead of a hardcoded Unix path; child services are owned by a
  Windows Job Object so a manager crash cannot orphan them; restore uses a
  two-phase directory swap that preserves full state across partial failures;
  Fuseki readiness probes the dataset endpoint; the embeddable Python entry
  points resolve the staged API; and the native package builder rebuilds the
  compiled SPA from source before staging.

- Fixed native portable exports with persisted SQLite workflow rows by using
  column-name access, validating uncommitted draft fingerprints against their
  exact payload bytes, and checking committed draft fingerprints against the
  store's authored-status fingerprint while keeping payload digests bound to
  the exported bytes.

- Fixed portable export of PostgreSQL receipts and correction events by
  canonicalizing stored aware timestamps to UTC before digest verification and
  emitting correctly formatted UTC timestamps independent of the database
  session offset.

- Fixed native export of persisted PostgreSQL review receipts and correction
  burden events by iterating complete SQLAlchemy Core rows rather than
  scalarizing away the fields required for record validation.

- Fixed portable project exports so empty connector state is valid JSON instead of producing an unreadable archive.

- Prevented transient native-runtime readiness failures by aligning the API probe deadline with its nested Semantic Core check; failed probes now record bounded, allow-listed health details in the local launcher log.
- Bounded both native Semantic Core and API outer readiness probes at four seconds to cover their nested three-second checks; regression cases exercise delayed success and the single-request deadline failure.
- Expanded native package assembly to inventory exact Maven runtime and license
  inputs, distinguish the Microsoft Visual C++ v14 external prerequisite from
  Windows baseline imports, and report recursive x64 PE imports and unverified
  loader-string candidates. The builder removes runtime DLLs from upstream
  package inputs and frozen archives, records signed source provenance and the
  pinned prerequisite policy, and rejects any residual runtime DLL in the
  assembled payload.

- Fixed the desktop control panel so its window appears immediately on launch while package verification continues in the background; a failed check now reports its exact code on the visible panel instead of leaving a windowless process.
- Fixed the desktop first-run flow so submitting a workspace name starts
  background provisioning instead of leaving the panel indefinitely at the
  setup modal.

- Fixed the web portable-import preview validator so the `/v1/imports/previews` path is not also checked against the import-result shape; previews (which carry no `status`) no longer fail with a malformed-result error in the Projects import UI.
- Fixed portable project exports failing with an internal error by restoring the export work-directory root on application startup.
- Fixed portable imports of a new project beside a renamed first-run workspace by sending the incoming project name when the destination has no local display name for it; the Core import validation no longer rejects the request.
- Fixed corrupted portable-import archives that break deflate decoding failing with an internal error; they now fail closed with the finite package-invalid response.
- Fixed confirmed portable-import apply so a missing staged package file fails closed with `IMPORT_PACKAGE_INVALID` instead of an unmapped internal error; destination state is unchanged.
- Fixed the unsigned Windows installer failing at the staged-application commit step: setup now leaves the staging directory before renaming it over the install location, commits onto a pre-created empty install directory instead of treating it as an existing installation, no longer aborts silent installs during startup, and uses distinct staging and previous-install temporary names. Fresh installs commit, upgrades replace the previous tree, and a failed commit still restores or leaves the previous installation without touching workspace data.

### Changed

- Separated project selection from workspace navigation; the active project
  remains visible while switching is available only through **Change project**.

- Placed **Signed in** and **Sign out** in the app top bar, keeping session
  controls available in both the Projects chooser and project workspaces.

- Clarified when to use Note Composer, Assisted import, and exact-span capture,
  including their distinct save and review outcomes. Successful capture now
  names the Review Queue as its next step without implying approval.

- Made directed Graph relations legible with labeled, visible arrowheads at
  target-node boundaries; the legend explains non-color patterns for
  verification/lifecycle states, selection, hover, and keyboard focus.

- Canonicalized experience catalog revisions to Semantic Core's sorted project allowlist, preventing a valid selection from becoming stale when the configured allowlist order differs.

- Preserved cross-screen journey context: exact-span captures focus the matching
  source-bound Review Queue candidate; Project Overview items open their
  project-scoped Graph detail, and Recent Notes opens the exact source record in
  Notes. Missing or unavailable routed context remains visible without
  substitution and offers recovery and return paths. Overview now emits
  destination-compatible, project-scoped `node-h-`, `note-h-`, and
  `candidate-h-` handles from the same opaque resource identity used by Core.
- Kept unfinished exact-span source and selection in memory when returning to
  Notes, with explicit continue/discard actions; switching projects clears the
  unsubmitted capture draft.

- Returned the server-issued project-scoped candidate handle with exact-span
  captures, so Review Queue opens the exact source-bound candidate instead of
  losing its selection.

- Forwarded the optional `PROJECTA_LOCAL_SUGGESTION_MODEL` setting to the Compose
  API with an empty default; suggestions remain operator-enabled and disabled in
  production.

- Simplified local Docker setup to a copy of `.env.example` followed by one
  idempotent PowerShell bootstrap command that generates unique credentials,
  seeds the experience projects, and leaves external providers disabled.

- Changed Fuseki bootstrap to append ontology/project triples and persist a
  version marker in the Fuseki data volume, avoiding graph replacement on
  later starts while preserving existing graph content.

### Fixed

- Appended the system-test M4 fixture to its named graphs instead of replacing
  existing project metadata during local acceptance setup.

- Preserved the API's finite local-suggestion error codes and safe reason details
  for disabled, unconfigured, and unreachable local models.

- Preserved the finite `REVIEW_RECEIPTS_UNAVAILABLE` reason and a safe 503
  detail when review receipt history is unavailable.
- Preserved actionable controlled-relation reason codes and their 409/422/503
  statuses through the API error envelope while sanitizing unrecognized codes.

- Preserved the safe `REVIEW_RECEIPT_REQUIRED` 409 response for legacy manual
  Note rejection requests, directing reviewers to the source-bound receipt route.

- Corrected manual candidate edit metrics so date-only changes stay outside
  correction categories while date plus a classified field retains its RM-67
  category.

- Separated the connector migration service image from the API development
  image so full Compose startup can run migrations before starting the API.

- Preserved already-opaque Semantic Core candidate handles when listing supported
  manual relation targets, avoiding a second hash that hid eligible targets.

- Documented the required connector PostgreSQL settings and secure Fernet-key
  initialization in the local Docker Compose quick start.

- Aligned the web review-workbench response type with its OpenAPI
  `manualCapture` field.

## [0.6.0] - 2026-08-14

### Added

- Added the credential-free, read-only GitHub Public Issues connector for one
  exact public repository, including opaque setup handles, bounded pagination,
  issue/comment mapping, replay-safe cursors, and Connections workflows.

### Changed

- Marked GitHub Public Issues as the live connector and Microsoft Teams as
  experimental/deferred; Teams remains covered by deterministic regression tests
  and is not a release gate.
- Reused the existing connector orchestration, evidence, candidate, review
  queue, and semantic lifecycle without changing the ontology version.

### Security

- Fixed the provider boundary to `api.github.com`, disabled redirects and hidden
  retries, enforced cumulative response/event/deadline limits, and bound setup
  handles to actor, project, installation, and revision.
- Preserved OpenBao as the platform secret boundary; the GitHub connector stores
  no provider token or work-tenant credential.

### Operations

- Use the release's Compose and recovery runbooks with digest-pinned images,
  clean volumes, manual OpenBao unseal, and post-restore workload re-authentication.
- The accepted G2 waiver covers one anonymous GitHub quota-limited live
  edit/replay rerun only; deterministic provenance and tamper contracts remain
  mandatory.

### Upgrade

- Stop the existing Compose stack, apply the checked-in migrations, update all
  component images/manifests to `0.6.0`, and run the release validation and
  recovery gates before starting the production profile.
- Existing v0.5.1 connector, evidence, candidate, and semantic data remains
  compatible; no ontology migration is required for this release.

### Rollback

- Roll back by stopping the `0.6.0` stack, restoring the previously approved
  v0.5.1 images and configuration, and restoring the coordinated operational
  state bundle only when the operator has a verified backup.
- Do not move the `v0.6.0` tag; publish a separately approved maintenance tag if
  a corrected rollback release is required.

### Limitations

- GitHub support is limited to public, read-only issues and issue comments in
  one exact repository; pull requests, private/authenticated access, webhooks,
  outbound actions, and continuous synchronization are out of scope.
- GitHub availability and anonymous API capacity are external limits. The
  release makes no capacity or availability guarantee.
- Teams live acceptance is deferred; it is not a production-ready connector in
  `v0.6.0`. High availability, broad tenant administration, and managed-service
  dependencies remain future work.

## [0.5.1] - 2026-08-11

### Fixed

- Fixed tag-driven release validation so connector PostgreSQL configuration,
  repository contract collection, and cross-platform recovery checks complete
  consistently before publication.

## [0.5.0] - 2026-08-11

### Added

- Added the governed JSON/Mock inbound connector with project-scoped
  installation, explicit sync/retry, safe run status, and a Connections screen.
- Added PostgreSQL connector operations, content-addressed evidence storage,
  deterministic migrations, backup/restore tooling, and recovery verification.

### Changed

- Reused the released Note, NoteItem, candidate, evidence, provenance, Graph,
  and Review Queue lifecycle for imported sources without an ontology change.

### Fixed

- Scoped connector fixtures and event identities to their authorized project
  and installation, made canonical replay hashes independent of evidence
  locators, and preserved truthful run counts across restart.
- Prevented public captures from claiming server-owned connector provenance and
  required policy checks for connector catalog and read operations.

### Security

- Added bounded event/evidence validation, opaque public handles, explicit
  local-only connector administration, sanitized failure/audit telemetry, and
  secret/payload/RDF leak gates.

## [0.4.0] - 2026-08-10

### Added

- Added governed LLM extraction with exact evidence spans, abstention,
  candidate provenance, deterministic evaluation, and human review.
- Added project-scoped retrieval, blockers, requirement history, evidence-backed
  answers, and deterministic inference materialization.
- Added the React workspace and user-managed provider configuration with
  application-encrypted local secret storage and redacted diagnostics.
- Added the repository-local `build-databricks-ui` skill with offline light and
  dark theme specifications, reusable React/CSS assets, page recipes, and a UI
  contract checker for dense data-workspace interfaces.
- Added the server-owned multi-project catalog, opaque project selection, and
  scoped project overview with explicit stale-selection recovery.
- Added a dense workspace shell, searchable Projects screen, active-project
  header, and project overview collections with loading, empty, and error
  states.
- Added structured Note composition, assisted import, browsing, correction,
  Graph exploration, Review Queue, and accessible companion tables.
- Added tag-driven GitHub releases that validate `vA.B.C`, component versions,
  release notes, and the complete release gate before publication.

### Fixed

- Prevented API-only confirmation correction metadata from leaking into the
  Semantic Core payload and surfacing as a misleading `503`.
- Made Assisted Import execute exactly one bounded provider request with hidden
  SDK retries disabled, an absolute deadline, finite output, truthful token
  telemetry, and DeepSeek thinking disabled through its documented contract.
- Preserved server-owned correlation IDs through Nginx and returned correlated,
  sanitized timeout errors instead of mismatched success headers or HTML 504s.
- Restored existing structured Notes and manual candidates in Graph and Review
  Queue, including node-detail selection, without rewriting persisted RDF.

### Security

- Updated Playwright, Vite, and Vitest to patched releases and added a high
  severity dependency-audit gate to tag-driven publication.

## [0.3.0] - 2026-08-01

### Added

- Added the Manual Quick Note M2 API slice: typed capture, deterministic
  candidates, human review, and evidence-backed reads through FastAPI and
  Semantic Core.

### Fixed

- Hardened the M2 slice with fail-closed trusted context, code-point-consistent
  evidence offsets, pre-commit SHACL validation, opaque server-derived IDs,
  source-type-preserving confirmation, atomic validation provenance, complete
  draft evidence fixtures, and downstream contract-error mapping.

## [0.2.0] - 2026-07-29

### Added

- Added the governed knowledge-lifecycle ontology proposal, including
  provenance, temporal metadata, named-graph isolation, fixtures, and
  competency queries.
- Added a no-op v0.1.0-to-v0.2.0 migration artifact for the additive
  compatibility path.

### Fixed

- Made ontology validation read Jena's SHACL conformance report and test both
  intended-invalid constraints and named-graph isolation without flattening
  TriG graph membership.

## [0.1.0] - 2026-07-28

### Added

- Added the initial product, architecture, memory, ontology, technology, learning-path, and deployment documentation.
- Added repository-local agent rules, decision memory, and the governed ontology-evolution skill.
- Added the approved Quick Note ontology kernel, demo graph, 14 competency
  queries, and three negative data-quality fixtures.
- Added a Docker-native Jena validation service with 32 semantic regression
  checks.
