# Authorized Project Context and Selection — Sprint 8

**Status:** `PROPOSAL_ONLY` — pending S8-11 architecture/security approval
**Task:** S8-06
**Scope:** Project catalog, active selection, request scoping, local experience
profile, and stale/forged selection behavior

## Boundary and non-goals

Sprint 8 introduces a finite multi-project experience without claiming
authentication, RBAC/ABAC, tenant administration, or production authorization.
The current local experience remains an explicitly configured server-side
allowlist. A future authenticated adapter may implement the same ports and
contracts, but it is outside this sprint.

The browser is untrusted for project, actor, tenant, graph, source, and
authorization identity. It may display labels and carry an opaque navigation
handle, but it cannot choose trusted headers or arbitrary IDs.

## Authority model

```text
server-established actor/context
  → finite visible project catalog
  → server-owned active selection
  → revalidated project-scoped request
  → finite Application API operation
  → Semantic Core project scope
```

The authority for each part is:

| Concern | Authoritative source | Browser role |
| --- | --- | --- |
| Actor/context | Deployment/auth adapter outside browser control | Display safe actor/session status only. |
| Visible projects | Semantic Core project-scoped read model queried by Application API | Render and select from returned collection. |
| Project label/status/counts | Authoritative project data and finite projection query | Display; never derive authority from client state. |
| Active selection | Server-side experience session/context state | Send a selection action with an opaque handle; may cache a hint only. |
| Project scope downstream | Application API resolves server-side and forwards trusted context to Core | No direct Core/Fuseki access. |
| Graph/source/evidence identity | Server-owned opaque navigation handles | Use links/actions returned by the API; never type or edit IDs. |

## Catalog contract

The catalog is a finite typed projection. Its conceptual shape is:

```json
{
  "requestId": "req-safe-opaque",
  "selectionRevision": "sel-rev-7",
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
      "freshness": {
        "state": "current",
        "revision": "projection-rev-4"
      }
    }
  ]
}
```

Required rules:

- `handle` is opaque and suitable for typed route state only; it is never a
  primary label, editable field, graph IRI, or arbitrary query input.
- `name`, `summary`, `status`, counts, activity, health, and freshness are
  server-derived and bounded.
- Counts are scoped to the same authorized project and must not be assembled
  from client calls to separate projects.
- Ordering is deterministic: approved status priority, normalized human name,
  then server-defined stable tie-breaker. The tie-breaker is never displayed.
- Empty catalog is a valid successful domain result only when the catalog query
  completed successfully. Missing context or unavailable Core is a finite
  problem, not an empty catalog.
- The catalog does not expose graph IRIs, TDB2 paths, RDF, arbitrary filters,
  actor IDs, tenant IDs, or internal database keys.

## Selection lifecycle

```text
NoSelection
    → CatalogLoaded
    → SelectionRequested(handle, revision)
    → ActiveSelection(handle, revision)
    → StaleSelection(handle, revision)
    → NoSelection
```

### Select

1. Client chooses one returned handle; it does not construct one.
2. Application API validates the handle against the current server-side catalog
   and expected `selectionRevision`.
3. The server records the active selection in the experience session/context
   state and returns the selected project's display projection.
4. Every following project-scoped operation resolves the active selection from
   server state and revalidates visibility before invoking Core.

### Clear/change

Changing project explicitly clears the prior selection before accepting the new
one. The UI must not show a previous project's data while the new catalog or
overview is loading. A failed change leaves no implicit project authority; the
screen remains in `NoSelection` or shows the explicit error.

### Stale selection

A stale selection occurs when the catalog revision, project visibility, or
server session no longer matches the selection. The API returns
`PROJECT_SELECTION_STALE` or the approved safe scope problem. It does not:

- revert to `local-project` or the last project;
- accept an arbitrary handle supplied by the browser;
- reveal whether an inaccessible project exists;
- execute a project-scoped read/write under the stale scope.

The UI clears the stale state, reloads the finite catalog after an explicit
user-visible action or approved flow, and requires a new selection.

## Request scoping

Every project-scoped request carries a server-established context containing:

- canonical request and operation correlation IDs;
- server-established actor/session context;
- selected project scope resolved from the catalog;
- selection revision and project projection revision where relevant.

The Application API rejects requests that contain browser project IDs in bodies,
arbitrary project path parameters, trusted context headers, graph names, RDF
IRIs, SPARQL, or raw storage selectors. It derives downstream graph scope from
the selected project and applies the same scope to:

- project overview and catalog counts;
- graph projection/neighborhood/detail/evidence/history;
- Notes, candidates, review decisions, Q&A, and diagnostics;
- correlated logs and operational audit records.

Semantic Core receives the server-owned project context over its private
boundary. Named-graph isolation remains a defense-in-depth boundary and does
not replace request authorization/revalidation.

## Local experience profile

The local profile is explicit and limited:

- It supplies a finite configured project allowlist and server-established
  actor/context; it never falls back to `local-project` when configuration is
  missing or stale.
- It binds through the same-origin web/API boundary and strips browser-supplied
  project, actor, context-secret, and request-identity headers before injecting
  server-owned values.
- It may use a deterministic local catalog fixture or Semantic Core read model,
  but the source is declared in configuration and logs.
- If the configured allowlist or required catalog dependency is unavailable,
  readiness/operation fails explicitly rather than presenting a fabricated
  catalog.
- It is suitable for local Compose and deterministic browser acceptance only;
  it is not evidence of production identity, tenant administration, or remote
  authorization.

## Server/session state

The server-side active selection is the source of truth. The browser may retain
an opaque handle and selection revision as a navigation hint for reload UX, but
that hint is never authoritative and must be revalidated before data access.

The session/context adapter must provide:

| Field | Rule |
| --- | --- |
| `actorContext` | Server-established; browser cannot write it. |
| `activeProjectHandle` | Opaque server-side handle or `none`. |
| `selectionRevision` | Monotonic/opaque revision checked on selection and scoped requests. |
| `catalogRevision` | Identifies the catalog used for selection. |
| `updatedAt` | Operational timestamp only. |
| `source` | `local_allowlist` or future reviewed authorization adapter. |

No browser `localStorage` or URL parameter can grant project access. A browser
reload with a stale hint must show a selection-recovery state, not a default
project.

## Error and privacy behavior

| Situation | Result | Data disclosure |
| --- | --- | --- |
| Missing trusted context | `PROJECT_CONTEXT_REQUIRED` | No project existence. |
| Empty authorized catalog | Typed `200` empty catalog | None beyond empty authorized domain. |
| Unknown/invisible handle | `RESOURCE_NOT_FOUND` or safe forbidden mapping | Do not distinguish unauthorized existence. |
| Catalog revision changed | `PROJECT_SELECTION_STALE` | Return only safe revision/status. |
| Core unavailable | `SEMANTIC_CORE_UNAVAILABLE`/compatibility alias | No empty catalog/overview. |
| Forged trusted headers | Boundary rejection | No trusted scope accepted. |
| Cross-project route/handle | Scope rejection | No other-project labels/counts/IDs. |

## Required tests

1. Catalog contains only configured/authorized projects and has deterministic
   ordering/counts.
2. Browser-forged project/actor/context headers cannot change server scope.
3. Arbitrary or stale handles are rejected and never fall back to a default.
4. Catalog, overview, graph, Note, candidate, evidence, Q&A, and logs all use
   the same active project scope.
5. A project removed from the allowlist is cleared explicitly and cannot be
   read through a stale route or browser state.
6. Empty authorized catalog is distinguishable from catalog/Core failure.
7. Reload with a valid opaque hint revalidates; reload with a stale hint enters
   explicit recovery.
8. Local mode cannot be presented as authentication or production authorization.

## Review status

This proposal is an input to S8-10 and depends on the S8-02 fail-explicit,
S8-03 error taxonomy, and S8-04 correlation contract. It remains
`PROPOSAL_ONLY` until G1 approval.
