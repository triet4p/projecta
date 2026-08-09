# Task Summary: S8-67 — User and operator runbooks

**Sprint:** Sprint 8
**Task:** S8-67
**Status:** Complete

## Coverage

Expanded `docs/runbooks/sprint-8-operations.md` with explicit bootstrap and
server-owned project selection, structured Note draft/import/commit flow, graph
limits and companion navigation, candidate review, Q&A, finite error/correlation
handling, explicit retry/recovery policy, safe log evidence, and prohibited
fallback behavior.

The runbook distinguishes liveness/readiness, domain-empty/abstained/stale/error
states, opaque handles, and semantic mutation boundaries. It never asks an
operator to paste credentials, raw Note text, graph IRIs, RDF, SPARQL, or
trusted context headers into an incident record.

## Validation

- Markdown links and command paths reviewed against repository artifacts.
- `git diff --check` — passed in S8-66.
