# Changelog

All notable changes to Projecta will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and Projecta uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

No unreleased changes.

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
