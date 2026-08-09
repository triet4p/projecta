# Structured Note API baseline — Sprint 8

**Status:** `IMPLEMENTATION_BASELINE`
**Scope:** S8-54 through S8-60
**Semantic approval:** [S8-53 review packet](../ontology/structured-note-review-packet.md)

## Boundary

The application accepts an editable structured draft and derives the source
body server-side:

```text
title + ordered typed items
        ↓ LF normalization and one-LF joins
canonical rawText + half-open Unicode-code-point offsets
        ↓ one Semantic Core transaction
Note + NoteItems + candidates + provenance
```

The title maps to released `projecta:name`. The nine released item types map to
`projecta:hasItemType`. Draft status, source metadata, and draft revisions are
operational fields in the application database, not RDF assertions. Evidence
offsets provide textual order; no `itemOrder` term is written.

## Public routes

All routes are project-selection scoped and use opaque handles:

| Route | Purpose |
| --- | --- |
| `POST /v1/projects/{handle}/notes/drafts` | Create/replay an editable draft with idempotency. |
| `GET/PUT /v1/projects/{handle}/notes/drafts/{draftHandle}` | Read/update a draft using `If-Match` revision. |
| `POST /v1/projects/{handle}/notes/drafts/{draftHandle}/commit` | Revalidate and atomically capture one committed Note. |
| `GET /v1/projects/{handle}/notes` | Bounded draft + committed Note collection. |
| `GET /v1/projects/{handle}/notes/{noteHandle}` | Title-first Note detail with exact source text/items. |
| `POST /v1/projects/{handle}/notes/import` | Non-persisting deterministic proposals or explicit abstention. |
| `POST /v1/projects/{handle}/candidates/{candidateHandle}/edits` | Revisioned pre-confirmation correction audit. |

Empty drafts are allowed while editing but commit requires at least one item.
Import never saves a fallback raw Note. A failed semantic capture leaves the
draft uncommitted and retryable.

## Compatibility

The existing `/v1/quick-notes` raw/segment contract remains valid. Its missing
title defaults to `Quick Note`; structured commits send an explicit title.
Semantic Core keeps the same source/candidate/provenance named graphs and runs
the released source/evidence/candidate SHACL shapes before the transaction.
