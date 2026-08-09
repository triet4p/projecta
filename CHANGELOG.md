# Changelog

All notable changes to Projecta will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and Projecta uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Added the repository-local `build-databricks-ui` skill with offline light and
  dark theme specifications, reusable React/CSS assets, page recipes, and a UI
  contract checker for dense data-workspace interfaces.
- Added the server-owned multi-project catalog, opaque project selection, and
  scoped project overview with explicit stale-selection recovery.
- Added a dense workspace shell, searchable Projects screen, active-project
  header, and project overview collections with loading, empty, and error
  states.

### Fixed

- Kept same-origin Quick Note extraction requests open across the API's bounded
  provider retries so the UI receives the final result or sanitized API error
  instead of an Nginx `504 Gateway Timeout` after 60 seconds.

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
