# Project workspace read model — Sprint 8

This document defines the bounded read model used by the Projects screen and
the selected project workspace. It is a public Application API contract; it
does not expose RDF, named graphs, actor identifiers, or storage keys.

## Authority and scope

The Application API receives a server-established actor/context and asks
Semantic Core for a finite catalog projection. The catalog is the only source
from which the browser may obtain a project handle. Names, status, summaries,
counts, activity, health, and freshness are server-derived. A missing catalog
source or an unavailable Core is an explicit problem, never an empty success.

The active selection is held by the server-side experience/session adapter.
The browser may retain the opaque handle as a navigation hint, but every
selection and every scoped request is revalidated against the current catalog
revision. There is no default project and no fallback to a previous selection.

## Catalog response

`GET /v1/projects` returns a bounded, deterministically ordered collection:

```json
{
  "requestId": "req-safe-opaque",
  "catalogRevision": "catalog-rev-7",
  "projects": [
    {
      "handle": "opaque-project-handle",
      "name": "Checkout modernization",
      "summary": "Payment and address validation work",
      "status": "active",
      "counts": {
        "requirements": 12,
        "tasks": 8,
        "questions": 3,
        "risks": 1,
        "notes": 9,
        "candidates": 2
      },
      "lastActivityAt": "2026-08-09T10:00:00Z",
      "health": "fresh",
      "freshness": {"state": "current", "revision": "projection-rev-4"}
    }
  ],
  "nextCursor": null
}
```

`handle` is opaque navigation state only. It is never accepted as a graph IRI,
an editable project ID, or an arbitrary filter. Ordering is status priority,
normalized name, then a server-only stable tie-breaker. `limit` is bounded by
the API contract and an empty authorized catalog is a valid `200` response.

## Overview response

`GET /v1/projects/{handle}/overview` returns one selected project with the
same identity, status, health, and freshness projection plus bounded labeled
collections: current requirements, open questions, tasks, blockers, risks,
recent notes, pending candidates, and evidence coverage. Each collection is
already project-scoped and navigable through opaque handles returned by the
API. Counts and labels are not assembled by browser fan-out.

Inference freshness is finite: `current`, `stale`, or `unavailable`, with an
opaque projection revision when available. A stale or unavailable projection
is displayed as such and is not silently treated as current.

## Selection and error behavior

`POST /v1/projects/selection` accepts only a handle returned in the current
catalog and the caller's `catalogRevision`. It returns the selected project
projection and a server-owned `selectionRevision`. Changing project clears
the old selection before accepting the new one.

| Situation | HTTP/code | Meaning |
| --- | --- | --- |
| Missing actor/context | 401 `PROJECT_CONTEXT_REQUIRED` | No project existence is disclosed. |
| Healthy empty catalog | 200 | Authorized domain is empty. |
| Catalog/Core unavailable | 503 `PROJECT_CATALOG_UNAVAILABLE` | Failure is not represented as empty. |
| Unknown or invisible handle | 404 `PROJECT_NOT_FOUND` | Do not distinguish unauthorized existence. |
| Catalog or visibility revision changed | 409 `PROJECT_SELECTION_STALE` | Clear selection and reload the catalog. |
| Scoped operation without selection | 409 `PROJECT_SELECTION_REQUIRED` | No default scope is inferred. |

The same selected project scope is applied to overview, graph projections,
notes, candidates, evidence, Q&A, diagnostics, and correlated operational
records. Forged browser headers, route IDs, graph names, and raw queries are
not trusted inputs.
