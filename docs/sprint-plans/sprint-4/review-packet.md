# Sprint 4 M2 Review Packet

## Delivered Scope

FastAPI accepts a trusted typed Quick Note and uses only finite Semantic Core
operations. Core atomically writes source Note/NoteItems, deterministic
Candidates, provenance, and private idempotency metadata. Capture never writes
asserted or inferred facts. Confirmation creates a Requirement; rejection
creates no asserted item.

## API Example

```json
{"rawText":"Confirm address.","segments":[{"type":"requirement","startOffset":0,"endOffset":16,"text":"Confirm address."}]}
```

`POST /v1/quick-notes` returns `201`; a matching retry returns `200` with the
original Note timestamp. Review and reads are defined in
`docs/architecture/application-api.md`.

## Graph Evidence

- Sources: Note raw text, author, NoteItems, and offset literals.
- Candidates: one `extracted` Candidate per typed item and project scope.
- Provenance: extraction/review activities and private idempotency records.
- Asserted: only confirmed Requirement items.
- Inferred: remains empty; no inference rule was added.

## Validation

Validation passed through the canonical `scripts/run_system_tests.ps1` entry
point outside the sandbox: it uses a process secret when configured, otherwise
lets Compose use the ignored local `.env`, and falls back to a .NET crypto RNG
without requiring OpenSSL. Runner-owned environment state is restored/removed
in `finally`, and the stack is cleaned up. The run passed 103/103 ontology checks,
Java `verify` including Spotless and the remote Fuseki lifecycle integration
test, and 10 API system tests. The ontology suite includes a v0.2 legacy
candidate fixture, and the remote lifecycle test validates and confirms that
legacy candidate. Ruff, Pyright, both Compose configuration modes, and
`git diff --check` also pass.

## Release Decision

The evidence-offset ontology was approved and released repository-locally as
`0.3.0` on 2026-08-01. Runtime validation uses
the candidate's `proposedOntologyVersion`: exactly `0.1.0` and `0.2.0` use
released candidate/source shapes; all other versions use strict current shapes.
The static-review hardening findings and canonical suite evidence are closed.
The human reviewer approved S4-24, M2 completion, and the ontology v0.3.0
release on 2026-08-01.
Authentication, authorization, public deployment, edit/delete, pagination, LLM
extraction, and inference remain out of scope.

## Human Approval Checklist

- [x] Accept the end-to-end Quick Note lifecycle and M2 evidence.
- [x] Accept the additive v0.3.0 evidence-offset semantic contract.
- [x] Accept the compatibility and no-backfill migration classification.
- [x] Approve Sprint 4, M2, and ontology v0.3.0 for repository-local release.
