# Finite Graph Projection API — Sprint 8

**Status:** `IMPLEMENTATION_BASELINE` — S8-11 approval recorded
**Task:** S8-39→S8-49
**Scope:** Project-scoped graph view, bounded neighborhood expansion, node
detail, evidence/lifecycle links, and accessible clients

## Boundary principles

The Graph API is a finite domain projection, not an RDF browser. It exposes
human labels, approved semantic display types, lifecycle/verification states,
direction, evidence/provenance summaries, and opaque navigation handles. It
never accepts or returns arbitrary SPARQL, graph names, graph IRIs, TDB2 paths,
raw RDF, arbitrary paths, or storage identifiers.

The Application API resolves the active project from the S8-06 server-owned
selection and revalidates it for every operation. Semantic Core performs the
allowlisted project-scoped query. Named graphs remain an internal isolation
boundary and are never a browser capability.

## Projection version and freshness

Every response includes:

```json
{
  "projectionVersion": "s8.graph.v1",
  "projectHandle": "opaque-selected-project",
  "sourceRevision": "asserted-revision",
  "materializationRevision": "inferred-revision",
  "asOf": "2026-08-09T12:00:00Z",
  "stale": false,
  "partial": false,
  "requestId": "req-safe-opaque"
}
```

`sourceRevision` and `materializationRevision` are opaque freshness values. A
response is `stale=true` when a known revision does not match the requested
selection/revision; it is not silently replaced with an older graph. A bounded
page is not `partial=true` merely because the project has more data: the
response declares continuation/expansion state explicitly.

## Allowlisted projection vocabulary

### Node display types

The initial proposal uses only released or already-governed domain concepts:

`Project`, `Note`, `NoteItem`, `Requirement`, `Decision`, `Question`, `Task`,
`Risk`, `Assumption`, `Constraint`, `ProgressClaim`, `ResearchFinding`,
`Person`, `Candidate`, and `SourceArtifact`.

The API returns a stable display label/type enum, not a class IRI. A future
ontology term cannot be added to this list without the S8-09 semantic review
and S8-11/S8-53 approval path.

### Relation display types

The initial relation allowlist is:

`implements`, `blocks`, `dependsOn`, `supports`, `answers`, `resolves`,
`constrainedBy`, `supersedes`, `derivedFrom`, `hasNoteItem`,
`belongsToProject`, `evidenceFor`, and `provenanceFor`.

Each relation is rendered as a directed edge with a display label. The API
does not accept an arbitrary predicate or return a predicate IRI. Relations
whose exact future semantic meaning is unresolved remain excluded until the
semantic interview is complete.

## DTOs

### Graph node

```json
{
  "handle": "opaque-node-handle",
  "label": "Tax API timeout is 15%",
  "semanticType": "Risk",
  "lifecycleState": "current",
  "verificationState": "candidate",
  "provenanceState": "source-backed",
  "evidenceCount": 1,
  "projectScope": "selected",
  "dates": {
    "validFrom": "2026-08-09",
    "validTo": null,
    "recordedAt": "2026-08-09T10:00:00Z"
  },
  "availableActions": ["view-detail", "view-evidence", "review"]
}
```

Rules:

- `handle` is opaque, short-lived or revision-bound, and only usable with the
  same selected project/projection revision.
- `label` is human-facing and bounded; it must not be replaced with a raw ID.
- `semanticType`, lifecycle, verification, provenance, and evidence are
  independent fields. Candidate, asserted, inferred, source, and provenance
  states must not be merged into one boolean.
- `availableActions` is server-allowlisted and scope-aware; it never exposes a
  generic edit/delete/SPARQL action.

### Graph edge

```json
{
  "handle": "opaque-edge-handle",
  "sourceHandle": "opaque-node-a",
  "targetHandle": "opaque-node-b",
  "relationType": "implements",
  "direction": "source-to-target",
  "verificationState": "asserted",
  "provenanceState": "asserted",
  "evidenceCount": 0
}
```

The client may lay out and filter the edge but cannot reverse, create, or edit
it. An inferred edge remains visibly inferred and is not presented as an
asserted fact.

### Graph page

```json
{
  "projectionVersion": "s8.graph.v1",
  "requestId": "req-safe-opaque",
  "projectHandle": "opaque-selected-project",
  "sourceRevision": "asserted-revision",
  "materializationRevision": "inferred-revision",
  "asOf": "2026-08-09T12:00:00Z",
  "stale": false,
  "partial": false,
  "nodes": [],
  "edges": [],
  "page": {
    "nodeLimit": 100,
    "edgeLimit": 200,
    "hasMore": false,
    "continuation": null,
    "expansionAvailable": false
  },
  "filters": {
    "semanticTypes": [],
    "verificationStates": [],
    "lifecycleStates": [],
    "provenanceStates": [],
    "relationTypes": [],
    "evidence": "any"
  }
}
```

An empty `nodes`/`edges` result is valid only when the finite query completed
successfully. A limit/page boundary is explicit through `hasMore` or
`expansionAvailable`; the API never silently truncates a project.

### Node detail

Node detail reuses the same handle/revision and includes:

- display label/type, project-safe status, lifecycle and verification state;
- valid/recorded dates and freshness;
- evidence count plus typed evidence-link handles;
- provenance summary and lifecycle-link handles;
- inbound/outbound relations from the bounded allowlist;
- available review/history/evidence actions;
- no graph/storage identifiers or unbounded related-resource dump.

## Operations

The conceptual typed operations are:

| Operation | Input | Output | Bound |
| --- | --- | --- | --- |
| `initial-view` | Active selection, finite filters, bounded limits | `GraphPage` | Project scope; no arbitrary path. |
| `neighborhood` | Returned node handle, projection revision, optional allowlisted filters | `GraphPage` expansion | One hop only; no recursive depth input. |
| `node-detail` | Returned node handle and revision | Node detail DTO | Same project/revision; no arbitrary ID. |
| `evidence-link` | Returned node/edge handle and revision | Typed evidence summary/link | Scope and evidence availability checked. |
| `lifecycle-link` | Returned node handle and revision | Typed lifecycle/history summary | Candidate/asserted lifecycle allowlist only. |

The eventual Application API may expose these as versioned REST endpoints, but
the contract remains operation-based and generated from one OpenAPI snapshot.
The browser never calls Semantic Core/Fuseki directly.

## Filters and limits

Allowed filters are finite enums:

- semantic type from the node allowlist;
- verification state: `candidate`, `asserted`, `inferred`, `unverified`;
- lifecycle state: `current`, `pending-review`, `confirmed`, `rejected`,
  `superseded`, `retracted`, `stale`;
- provenance state: `source-backed`, `human-confirmed`, `rule-derived`,
  `candidate-proposed`;
- relation type from the edge allowlist;
- evidence: `any`, `with-evidence`, `without-evidence`.

Proposed safety limits, subject to benchmark and G1 review:

- initial view: at most 100 nodes and 200 edges;
- one-hop expansion: at most 50 new nodes and 100 new edges;
- one operation may expand one returned node at a time;
- no client-provided depth, arbitrary path, unbounded page size, or recursive
  traversal;
- continuation handles are bounded, revision-bound, and expire with the
  projection/session policy.

Unknown filter values, excessive limits, duplicate/ambiguous handles, stale
revisions, arbitrary predicates, SPARQL, graph names, and path expressions
return finite validation/scope problems. They never broaden the query.

## Project isolation and lifecycle safety

- The active project is resolved and revalidated by the Application API for
  every graph operation.
- Every returned node/edge/detail is proven to belong to the selected project
  before projection.
- Cross-project relations are omitted or returned only if an approved relation
  policy explicitly allows them; Sprint 8 defaults to same-project edges.
- Candidate, asserted, inferred, source, and provenance graphs remain separate
  internally and their state flags remain separate in the DTO.
- A stale graph revision returns a typed stale result/problem; it is never
  silently merged with a new revision.
- Graph access is read-only in this slice. Review/evidence/history actions route
  through their own typed operations and lifecycle authorization.

## Accessibility and renderer contract

The visual Graph screen and the companion table consume the exact same
`GraphPage` projection. The table is a first-class keyboard/screen-reader view,
not a failure fallback or separate data source. All states—loading, empty,
stale, error, selected, expanded, and long-content—must be represented without
using color alone.

## Regression requirements

1. Initial view and one-hop expansion obey node/edge budgets and preserve
   deterministic ordering.
2. Unknown types/relations/filters, excessive limits, arbitrary paths, SPARQL,
   graph names, and forged handles are rejected.
3. Cross-project data never appears in nodes, edges, counts, evidence, history,
   logs, or error details.
4. Candidate/asserted/inferred/source/provenance states remain distinct in the
   Graph DTO, renderer, and companion table.
5. Empty, stale, partial/continuation, and dependency-failure states are
   contractually distinct.
6. Cycles, repeated expansion, cancellation, stale revisions, and oversized
   projects terminate within bounded time without silent truncation.
7. Detail/evidence/lifecycle handles are usable only from the returned finite
   projection and active project scope.

## Review status

This proposal is an input to S8-10 and depends on S8-03 error mapping,
S8-04 correlation, S8-06 project context, S8-08 renderer benchmark, and the
S8-09 semantic interview for any unresolved Note/assignment/date vocabulary.
The DTO vocabulary and boundary rules are implemented at the Application API
and Semantic Core projection boundary. G1 still owns production acceptance of
performance evidence and any future ontology vocabulary changes; it does not
authorize arbitrary RDF/SPARQL capabilities.
