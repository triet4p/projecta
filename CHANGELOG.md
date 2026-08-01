# Changelog

All notable changes to Projecta will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and Projecta uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

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
