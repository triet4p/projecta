# S4-24R — Static-review hardening

## Outcome

The reported S4-24 blockers are implemented in the local M2 slice. S4-24
approval remains a human decision and is intentionally still pending.

## Boundary changes

- Project/actor context fails closed unless the shared context secret is present
  and matches; Compose now requires the secret explicitly.
- Python and Java use Unicode code-point offsets for evidence validation and
  slicing, including supplementary characters such as emoji.
- Capture validates source, candidate, and evidence graphs before its single
  Fuseki write; injected validation-failure coverage proves no update is made.
- Note, candidate, confirmation, rejection, and idempotency resources no longer
  expose the client idempotency key.
- Confirmation requires the candidate's source NoteItem to retain
  `projecta:requirement`; validation promotion records a `prov:Activity` and
  status transition in one conditional update.
- Runtime validation selects shapes by `projecta:proposedOntologyVersion`:
  exactly `0.1.0` and `0.2.0` use released candidate/source shapes; malformed,
  unknown, and future versions use strict current shapes. Legacy Note/NoteItem
  data therefore needs no evidence-field backfill, while malformed versions
  cannot downgrade validation.
- The canonical runner uses an existing process secret, otherwise leaves
  Compose to read the ignored local `.env`, and falls back to .NET crypto RNG
  without requiring OpenSSL. Only runner-owned environment state is restored or
  removed in `finally`; `.env` is never modified.
- Downstream transport, timeout, and invalid-contract responses map to
  `SEMANTIC_CONTRACT_UNAVAILABLE` with `application/problem+json`.

## Evidence

Passed locally: Python tests, Ruff, Pyright, Compose config checks, and
`git diff --check`. The canonical Docker Compose suite was then run outside the
sandbox from a clean secret environment with 103/103 ontology checks, Java
`verify` (including Spotless and the remote Fuseki lifecycle integration test),
and 10 API system tests all passing. The ontology suite includes a v0.2 legacy
candidate fixture; the remote lifecycle regression validates and confirms that
candidate without `rawText` or evidence offsets. The ephemeral containers,
network, and Fuseki volume were removed after the run.

At the time of this hardening task, the ontology and S4-24 remained pending
release approval. The human reviewer subsequently approved both on 2026-08-01;
the final decision is recorded in the Sprint 4 review packet.
