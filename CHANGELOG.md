# Changelog

All notable changes to Projecta will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and Projecta uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Added discoverable, accessible Light / Dark / System theme selection across the
  desktop application shell, Settings screen, and native workspace management
  surface, with deterministic configuration persistence in `config/ui-preferences.json`,
  live operating system color-scheme synchronization under System mode, and
  high-contrast token calibration across all app-owned surfaces.

### Security

- Enforced strict origin validation and mandatory `X-Projecta-Theme-Request` custom
  header protection on the desktop `/preferences/theme` endpoint, rejecting foreign
  origins, missing Origin headers, lookalikes, and disallowed HTTP methods without
  mutating stored UI preferences.

### Fixed

- Fixed desktop theme controller error handling to prevent claiming false persisted
  modes upon host read or write failures, rolling back to previous state and presenting
  honest error notifications.
- Added a Tauri v2 desktop host (`apps/desktop`) with one native window over
  the existing loopback Application API SPA. The host registers no native
  commands and refuses foreign navigation inside the privileged view. Verified
  with in-window project selection and Notes navigation; note draft save/commit
  activation remains unverified.
- Integrated app-owned lifecycle into the Tauri host (`apps/desktop`): existing
  workspaces launch the local supervisor as the app's owned child, the same
  window moves from bootstrap to the loopback SPA on real readiness, a second
  launch refuses without a second backend, and cancel/close stop only owned
  children with locks/ports released and data retained. Verified with
  disposable backends using process/port/status/data evidence; no retry loop,
  hidden service, or Rust process manager added.

- Added first-run workspace provisioning to the existing Tauri v2 window.
  Valid form submission reuses the audited project/actor generation and
  DPAPI CurrentUser-protected runtime secret setup; Cancel and invalid names
  leave no workspace state, and the data-only `provision` path does not install
  OS shortcuts or write registry keys. Existing workspaces reopen without
  reseeding or overwriting the catalog. Verified through the native WebView2
  form, real runtime readiness, portable export, deletion, and empty-catalog
  reopen using the internal 0.7.1 `unsigned-pre-release-test` channel
  (`releaseEligible=false`; not for public distribution).
- Added runtime controls and recoverable-error presentation to the existing
  Tauri v2 window. The same window presents startup/readiness/stopped/failure
  and after-ready service failure states with Start/Stop controls, a bounded
  user-initiated recovery action, and sanitized diagnostics carrying the
  supervisor's own finite failure code and failing service name; the surface's
  own form is the only Start/Retry/Stop/Open binding (the host registers no
  native menu bar).
  No automatic retry, no empty success screen, and no Rust process manager.
  Verified on disposable state with the internal 0.7.1
  `unsigned-pre-release-test` channel using controlled port collision,
  after-ready dependency failure, user-initiated start/stop, data retention,
  and owned-cleanup evidence.
- Added WebView/native trust-boundary enforcement to the desktop host. The
  single privileged window is created with explicit boundary handlers: only
  the bundled bootstrap surface and the owned loopback API origin may be
  navigated (foreign origins, foreign loopback ports, `file:` URLs, lookalike
  or credential-bearing protocol hosts, and other custom schemes are refused),
  every secondary-window request is denied, sensitive web permissions are
  denied, and no native command or capability exists (`withGlobalTauri: false`,
  empty capability manifest, direct invoke attempts refused by the ACL). The
  loopback API entry point now also refuses foreign `Host` headers
  (DNS-rebinding defense) and foreign `Origin` headers (local cross-origin
  forgery defense) with `LOOPBACK_BOUNDARY_REJECTED`. CSP, same-origin policy,
  and certificate verification are unchanged. Verified on disposable state with
  the internal 0.7.1 `unsigned-pre-release-test` channel using actual
  WebView2/CDP negative cases, listener-bound checks, connector default-false
  and explicit opt-in runs through the real owned API, and the unchanged
  production guard.
- Adapted the browser-dependent interactions that the single-window desktop
  hosting affects. Portable project export downloads the archive through the
  window with an owned download destination (the platform's own download
  folder by default; an absolute `PROJECTA_DESKTOP_DOWNLOAD_DIR` disposable
  root when configured), the manual-transfer import file picker opens the
  platform's file dialog and cancels with zero state change, keyboard
  copy/paste keeps using the operating-system clipboard while clipboard-read
  permission stays denied, tab order/Enter activation/same-document hash
  navigation/reload behave as before on the owned loopback origin, and an
  allowed external link (`window.open`, `target="_blank"` on an absolute
  `http`/`https` destination) is opened in the user's system browser without
  ever navigating the privileged view or opening a second window. Project
  list, selection, import, and export still run through the existing
  React/typed API surface. Verified in the actual Tauri window on disposable
  data/WebView2/download roots with the internal 0.7.1
  `unsigned-pre-release-test` channel using native file-dialog,
  archive-hash, owned-probe, real-keyboard, and reload/isolation evidence.
- Fixed the export confirmation dialog staying visible after Cancel. The closed
  dialog is now hidden, it opens only on the explicit Export action, Cancel
  closes it without exporting anything, and reopening starts from cleared
  consent.
- Added the desktop-only `Manage workspace` action to the header of the
  built-in project workspace. It returns the same window to the workspace and
  runtime management surface without stopping, restarting, or reseeding the
  owned runtime, and it renders only inside the desktop window (a
  browser-served copy of the same interface shows no such control).

### Fixed

- Fixed Windows supervisor process-tree containment: the host now configures
  its kill-on-close Job Object with the extended-limit structure required by
  Windows. A create/configure/assign failure is a finite spawn failure after
  cleanup of only the exact newly created child, never a fallback to an
  uncontained supervisor.

### Changed

- Removed the desktop window's native `Runtime` menu bar. It rendered as a
  redundant strip between the OS title bar and the workspace-management
  surface, duplicating controls the surface already exposes. The window keeps
  its OS title bar and standard minimize/maximize/close controls, and
  automatic startup, in-overlay cancel, and owned-tree cleanup are unchanged.
  The round trip that menu carried is preserved: the runtime surface is still
  the window's first and failure-time view, and the ready project workspace
  returns to it through the desktop-only `Manage workspace` action in its own
  header.

- The desktop app now ships the real Projecta mark as its application icon
  instead of the placeholder. One 1024x1024 master generates the executable's
  Windows icon resource (Explorer, taskbar, Alt-Tab) and the window icon at
  seven sizes from 16 to 256, and the same master backs the browser build's
  favicon.

- Added the distinct startup overlay above the workspace-management surface.
  While the accepted workspace creation or the owned runtime startup is really
  in flight, a non-modal overlay of the same window shows a loading state and
  the same real service steps (never a timer or a percentage), keeps the
  bounded `Cancel startup` action reachable, and never traps keyboard focus.
  It disappears on real readiness, and on any terminal outcome the management
  surface — failure code, failing service, diagnostics, and bounded recovery —
  is fully reachable again. The inline create action no longer holds the
  window on a blocking request: the accepted request runs on an app-owned
  worker while the window keeps reporting its real outcome, and a refused name
  still writes nothing.

- Opening the desktop app now starts the local workspace runtime by itself, and
  the former separate first-run screen and runtime Start/Stop page are replaced
  by one workspace-management surface. It presents the local workspace (name
  and project ID, never the data-root path), the eight real initialization
  steps — application package, owned supervisor process, PostgreSQL `:15432`,
  Fuseki `:18303`, Semantic Core `:18080`, API `:18732`, core readiness, and
  session readiness — each with the status the app actually observed, and only
  then the existing project workspace. There is no timer or percentage
  progress, no empty success screen, and no automatic retry: Start/Retry stays
  a single bounded user action, and Stop/Cancel stops only the services
  Projecta started. A data root with no workspace shows an inline
  create-workspace card on the same surface instead of a separate wizard, and
  cancelling or refusing a name writes nothing.
- Closing the desktop window now cancels workspace creation itself, not just a
  running runtime: a create in flight is stopped as an app-owned child and the
  window waits for its worker to finish before it exits, so no half-writing
  process outlives the window and the data root is left exactly as the
  launcher wrote it.
- The desktop window no longer shows the `Signed in`/`Sign out` session
  control. The local runtime authorizes requests through its own server-owned
  context, where signing out revokes nothing and the next reload re-enters the
  same context, so the control is omitted exactly for that local identity;
  browser and production sign-in keep both controls, and API authorization,
  Origin/Host protections, CSRF, and CSP are unchanged.

## [0.7.1] - 2026-10-09

### Fixed

- Fixed connector installation Enable/Disable requests returning `503` because the composed runtime was not published to the application state those routes read. Both operations now use the same runtime as install, sync, and catalog.

- Restored the documented `PROJECTA_CONNECTOR_LOCAL_ADMIN_ENABLED` opt-in for the native local API; it remains disabled unless explicitly set, and production startup continues to reject it.

- Corrected OpenAI SDK 2 request typing for optional sampling: unspecified `temperature` and `top_p` values are omitted, while explicitly configured values are sent.

- Kept Linux/Compose release and API checks portable with runner-owned evidence roots and container-compatible import/receipt checks; replaced workstation-line-ending and test-source assumptions with byte-provenance and semantic contract checks.

### Security

- Updated the vulnerable web dependencies reported by `npm audit`; the corrected dependency tree reports no vulnerabilities.

## [0.7.0] - 2026-10-08

### Added

- Added human-authored exact-span capture from Notes with a direct return to
  the Review Queue, so the zero-model workflow is reachable through normal
  workspace navigation. Capture returns the server-issued project-scoped
  candidate handle, and does not approve or materialize the candidate.

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

- Added bounded native project data export under the approved
  projecta-portable.v1 contract, with cross-store writer exclusion fencing,
  typed schema validation across semantic TriG, evidence objects, application
  workflows, connectors, review decision receipts, and correction burden
  events, plus hard resource bounds and explicit owner export confirmation.
  Export lives on the Project Overview screen and is available only from the
  supported native launcher; the archive is plaintext with integrity hashes,
  not encryption or signing.

- Added validated manual portable-project import under the approved
  projecta-portable.v1 contract: full archive validation before any live
  change, explicit owner preview/confirmation/cancel, staged-copy apply with
  quiesced services and catalog-last publication, durable
  interrupted-recovery journaling with fail-closed restart behavior, idempotent
  exact-replay, and finite tamper/partial/version/conflict/unauthorized
  responses with no implicit approval or materialization. Verified on isolated
  disposable native roots with real browser journeys.

- Added validated native project-data deletion under the approved
  projecta-deletion.v1 contract: a discoverable per-project Delete action with
  explicit typed-identity confirmation, per-store purge across semantic
  graphs, evidence, SQLite, PostgreSQL history (via a narrow
  transaction-local purge exception), import-ledger scope entries, project
  authorization grants, registry and selections, with truthful
  deleted/refused outcomes, busy/cancel no-mutation behavior, interruption
  recovery, persisted empty catalog on last-project delete with fresh import
  afterwards, and no automatic backup, rollback, or undo. Verified on isolated
  disposable native roots with real browser journeys.

- Added optional directory-backed serving of the compiled React SPA from the
  Application API for a same-origin local package path. Missing or invalid
  configured assets fail readiness instead of masquerading as a usable install.

- Added a Windows 11 x64 per-user launcher path with loopback-bound managed
  services, CurrentUser DPAPI secrets, readiness/status/stop controls, and
  hash-verified whole-state backup/restore with rollback. The owner-authorized
  unsigned 0.7.0 test-pre-release exception applies only to that exact version
  and channel; it does not establish clean-Windows readiness or signed-release
  eligibility.

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

- Kept graph-backed exact-span review digests distinct from LocalEvidenceStore
  object references while preserving required connector-inbox evidence closure.

### Fixed

- Fixed the project-deletion confirmation showing and reporting double the
  actual graph count. The dialog and the deletion receipt now report the
  authoritative total.

- Fixed the project-deletion confirmation escaping the viewport on short
  screens. The confirmation now opens as a bounded modal dialog with scrollable
  content and keeps every warning, the typed project name/ID field, and the
  Cancel/Delete permanently actions reachable by mouse and keyboard.

- Fixed project deletion refusing with a crash-loop when an interrupted delete
  is recovered after its staged previews were already forgotten, and refusing
  only after destroying data when a staged preview belonged to another actor.
  Recovery now completes an already-forgotten staging tail idempotently, and a
  foreign-actor staged preview refuses before any project data is touched.

- Stopped restarting every local service when a project is imported or
  deleted. The new or remaining project catalog serves immediately: the
  Projects list refreshes itself with no manual browser reload, and
  PostgreSQL, Fuseki, Semantic Core, and the API keep running. Interrupted
  operations still refuse safely until recovered.

- Fixed the web portable-import preview validator so the `/v1/imports/previews`
  path is not also checked against the import-result shape; previews (which
  carry no `status`) no longer fail with a malformed-result error in the
  Projects import UI.

- Fixed portable project exports failing with an internal error by restoring
  the export work-directory root on application startup.

- Fixed portable imports of a new project beside a renamed first-run workspace
  by sending the incoming project name when the destination has no local
  display name for it; the Core import validation no longer rejects the request.

- Fixed corrupted portable-import archives that break deflate decoding failing
  with an internal error; they now fail closed with the finite package-invalid
  response.

- Fixed confirmed portable-import apply so a missing staged package file fails
  closed with `IMPORT_PACKAGE_INVALID` instead of an unmapped internal error;
  destination state is unchanged.

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

- Fixed portable project exports so empty connector state is valid JSON
  instead of producing an unreadable archive.

- Corrected the native launcher path: approved first-run workspace provisioning
  replaces the previous setup blocker; Semantic Core reads the packaged shapes
  directory instead of a hardcoded Unix path; child services are owned by a
  Windows Job Object so a manager crash cannot orphan them; restore uses a
  two-phase directory swap that preserves full state across partial failures;
  Fuseki readiness probes the dataset endpoint; the embeddable Python entry
  points resolve the staged API; and the native package builder rebuilds the
  compiled SPA from source before staging.

- Prevented transient native-runtime readiness failures by aligning the API
  probe deadline with its nested Semantic Core check; failed probes now record
  bounded, allow-listed health details in the local launcher log.

- Bounded both native Semantic Core and API outer readiness probes at four
  seconds to cover their nested three-second checks; regression cases exercise
  delayed success and the single-request deadline failure.

- Expanded native package assembly to inventory exact Maven runtime and license
  inputs, distinguish the Microsoft Visual C++ v14 external prerequisite from
  Windows baseline imports, and report recursive x64 PE imports and unverified
  loader-string candidates. The builder removes runtime DLLs from upstream
  package inputs and frozen archives, records signed source provenance and the
  pinned prerequisite policy, and rejects any residual runtime DLL in the
  assembled payload.

- Fixed the desktop control panel so its window appears immediately on launch
  while package verification continues in the background; a failed check now
  reports its exact code on the visible panel instead of leaving a windowless
  process.

- Fixed the desktop first-run flow so submitting a workspace name starts
  background provisioning instead of leaving the panel indefinitely at the
  setup modal.

- Fixed the unsigned Windows installer failing at the staged-application
  commit step: setup now leaves the staging directory before renaming it over
  the install location, commits onto a pre-created empty install directory
  instead of treating it as an existing installation, no longer aborts silent
  installs during startup, and uses distinct staging and previous-install
  temporary names. Fresh installs commit, upgrades replace the previous tree,
  and a failed commit still restores or leaves the previous installation
  without touching workspace data.

- Preserved the API's finite local-suggestion error codes and safe reason
  details for disabled, unconfigured, and unreachable local models.

- Preserved the finite `REVIEW_RECEIPTS_UNAVAILABLE` reason and a safe 503
  detail when review receipt history is unavailable.

- Preserved actionable controlled-relation reason codes and their 409/422/503
  statuses through the API error envelope while sanitizing unrecognized codes.

- Preserved the safe `REVIEW_RECEIPT_REQUIRED` 409 response for legacy manual
  Note rejection requests, directing reviewers to the source-bound receipt route.

- Preserved already-opaque Semantic Core candidate handles when listing
  supported manual relation targets, avoiding a second hash that hid eligible
  targets.

- Corrected manual candidate edit metrics so date-only changes stay outside
  correction categories while date plus a classified field retains its RM-67
  category.

- Separated the connector migration service image from the API development
  image so full Compose startup can run migrations before starting the API.

- Aligned the web review-workbench response type with its OpenAPI
  `manualCapture` field.

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

- Canonicalized experience catalog revisions to Semantic Core's sorted project
  allowlist, preventing a valid selection from becoming stale when the
  configured allowlist order differs.

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

- Appended the system-test M4 fixture to its named graphs instead of replacing
  existing project metadata during local acceptance setup.

- Preserved the manual-rejection `REVIEW_RECEIPT_REQUIRED` behavior through the
  production-shaped API path so a source-bound receipt survives container
  restart and the legacy path still writes nothing.

- Documented the required connector PostgreSQL settings and secure Fernet-key
  initialization in the local Docker Compose quick start.

- Preserved PostgreSQL credential-mismatch recovery in local setup guidance:
  keep the existing volume and start a separate fresh Compose project instead
  of erasing data to silence an authentication error.

### Limitations

- The unsigned 0.7.0 Windows 11 x64 path remains unsigned, unpublished as a
  signed release, and without clean-host proof, public download, production, or
  `1.0.0` claims. Signed update verification stays fail-closed.

- Offline dense-hard evaluation, provider-backed extraction quality work, and
  external evaluation/production enablement stay deferred; this release makes
  no achieved-quality, clean-host, signing, or production claims for them.

- Deletion is irreversible with no automatic backup, rollback, or undo; export
  archives are plaintext integrity-only artifacts, and copies kept in backups
  or exported files remain wherever they were kept.

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
