# Task Summary: S8-64 — Deterministic browser journeys

**Sprint:** Sprint 8
**Task:** S8-64
**Status:** Complete

## Coverage

The Playwright suite uses route-local finite fixtures and no provider
credentials. It covers project selection, structured Note creation, assisted
import, explicit commit, bounded graph plus companion table, candidate review
and validation, Q&A, no-ID browser labels, and an injected graph failure with
request correlation.

The default Playwright config now targets the Sprint 8 suite; the historical
Sprint 7 spec remains available as a compatibility fixture but is not mixed
into the Sprint 8 acceptance run.

## Validation

- `npx playwright test --config=playwright.config.ts` — passed: 4/4 desktop and
  narrow Chromium cases.
- No live provider, credential, Semantic Core endpoint, RDF IRI, or trusted
  header is used by the deterministic suite.
- Desktop and narrow Project Overview screenshots are stored under
  `docs/sprint-plans/sprint-8/evidence/`.
