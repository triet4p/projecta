# Sprint 8 Architecture, Security, and Semantic Review Packet

**Status:** `READY_FOR_HUMAN_ACCEPTANCE`

**Gate:** S8-69 / M6 — explicit human acceptance remains required before Sprint
8 is marked complete.

**Prepared:** 2026-08-10

**Human approval recorded:** 2026-08-09 — user approved S8-11/G1 for
implementation under the exact boundaries and checklist below.

This packet consolidates S8-01 through S8-68. The earlier G1/S8-11 approval is
preserved as implementation authority for its exact boundaries; this packet is
not itself M6 approval, a release, deployment, ontology approval,
authentication claim, or permission to mutate shared data.

## Decision summary

| Boundary | Proposed decision | Evidence |
| --- | --- | --- |
| Fail-explicit behavior | Operational failures are finite non-2xx outcomes with correlated diagnostics; domain-valid empty results remain distinct. No swallowed exception, synthesized success, implicit authority, or fallback. | [fail-explicit-runtime-contract.md](../../architecture/fail-explicit-runtime-contract.md), [error-taxonomy.md](../../architecture/error-taxonomy.md) |
| Error identity | Public problem codes preserve the actionable failure class while redacting secrets, provider payloads, SPARQL, graph IRIs, stack traces, and source text. Released compatibility aliases remain until an API snapshot change is approved. | [error-taxonomy.md](../../architecture/error-taxonomy.md) |
| Correlation | Browser → Nginx → API → Semantic Core → Fuseki/provider uses one validated request/operation correlation model with safe project scope, attempt, latency, and terminal outcome. | [correlated-logging.md](../../architecture/correlated-logging.md) |
| Retry | Interactive product path is single-attempt by default. Retry is only an explicit user action or a reviewed operator/evaluation/replay mode; replay can never activate after live failure. | [explicit-retry-contract.md](../../architecture/explicit-retry-contract.md) |
| Project context | The server owns a finite catalog and opaque handles. The user selects a project from that catalog; every request is scoped server-side. Local experience is not production authentication or tenant administration. | [project-context-selection.md](../../architecture/project-context-selection.md) |
| Graph projection | Expose a bounded domain DTO projection with finite node/edge allowlists, freshness, evidence/provenance links, lifecycle links, and accessible table parity. Never expose RDF terms, graph IRIs, paths, or arbitrary SPARQL. | [graph-projection-api.md](../../architecture/graph-projection-api.md) |
| Graph renderer | Candidate choice is `@xyflow/react` 12 for the React/TypeScript DOM/SVG experience, with companion table and later measured performance gate. No dependency installation is authorized by this packet. | [graph-renderer-benchmark.md](../../architecture/graph-renderer-benchmark.md) |
| Structured Note | Reuse released Note/NoteItem/evidence/provenance semantics. Do not add `itemOrder`, `assignedTo`, `deadline`/`dueAt`, generic `status`, or Note revision vocabulary until the semantic questions are answered. | [structured-note-proposal.md](../../ontology/structured-note-proposal.md), [structured-note.md](../../ontology/competency-questions/structured-note.md) |
| Migration/compatibility | No migration or released IRI change is proposed. Future semantic additions require their own CQs, interview, fixtures, SHACL/query/regression evidence, compatibility review, and rollback plan. | [structured-note-proposal.md](../../ontology/structured-note-proposal.md), Sprint 8 task summaries |

## Architecture and security boundaries

### Fail-explicit runtime

- A provider, Fuseki/TDB2, Semantic Core, API, proxy, configuration, or
  validation failure terminates the operation with a typed terminal outcome.
- Domain-valid empty collections, no-neighborhood results, explicit user
  cancellation, and explicit replay mode are not operational failures.
- Production authority, provider, persistence, project scope, and retry mode
  must come from validated configuration or an explicit user/operator action.

### Project isolation

- The API resolves a user-visible project selection to a server-owned opaque
  handle and trusted project context.
- Catalog membership, active selection, stale selection, and cross-project
  references are validated before read or mutation.
- This local slice does not claim authentication, authorization, tenant
  administration, or connector identity resolution.
- Logs and DTOs use safe project labels/handles; they do not expose graph IRIs,
  raw source text, provider payloads, or secrets.

### Graph safety and accessibility

- Initial graph and one-hop expansion are bounded; node/edge types and relation
  directions are allowlisted.
- Node detail, evidence, provenance, and lifecycle are separate finite links.
- The graph is never the sole navigation surface; the accessible companion
  table is mandatory.
- The renderer must not permit arbitrary create/connect/delete operations and
  must preserve project scope during incremental expansion.

## Semantic boundary

The structured Note path remains source evidence first:

```text
Note → ordered typed NoteItem evidence → Candidate → reviewed/asserted knowledge
```

“Ordered” means textual order can be derived from released evidence offsets for
the v0.3 contract. It does not authorize a new durable editorial-order
property. A NoteItem type is a controlled source classification, not an
asserted Task/Requirement/etc. Author, assignee, deadline, candidate status,
and asserted validity are distinct semantics and must not be collapsed.

## Unresolved choices requiring human authority

| ID | Choice | Consequence if approved | Consequence if deferred/rejected |
| --- | --- | --- | --- |
| U1 | Approve textual order from evidence offsets as the Graph view's ordering basis for v0.3 Notes. | The Graph view may sort evidence-bearing items by canonical code-point start offset and label this as textual order. | The view must show source order only when independently supplied; legacy/offsetless items remain unordered. |
| U2 | Approve future assignment semantics on promoted Work/Task resources, not directly on source NoteItems. | Later implementation can model actor identity, role, project scope, temporal validity, and provenance at the work boundary. | Assignee mentions remain source evidence and cannot drive task assignment. |
| U3 | Approve future deadline semantics as a time-qualified work commitment with explicit timezone and requested/committed distinction. | Later implementation can add the smallest governed representation and tests. | Date phrases remain unnormalized source text; no due-date filtering or reminders. |
| U4 | Keep Note edit/versioning outside the current capture contract; corrections create new source records with provenance. | Source history remains immutable and migration-free for this sprint. | A later edit model requires a new semantic interview, version identity, and migration plan. |
| U5 | Approve `@xyflow/react` 12 as the implementation candidate, subject to S8-49 measured performance and accessibility evidence. | S8-12+ may implement the renderer after dependency and fixture gates. | Benchmark fallback remains open; no renderer dependency is installed. |
| U6 | Approve the no-implicit-retry rule for interactive product operations. | S8-12+ may remove implicit live-path retries while retaining explicit reviewed modes. | Retry behavior remains unapproved and contract-changing work cannot proceed. |
| U7 | Approve local finite project catalog as an experience boundary without calling it production authorization. | S8-12+ may implement server-owned selection and project-scoped routes. | Project selection remains a blocked contract; no forged/stale-context behavior may be inferred. |

## Approval checklist — G1

The reviewer must check each item explicitly. No item is pre-approved by the
existence of this packet or by the earlier G0 approval.

- [x] Approve the fail-explicit runtime contract and domain-empty distinction.
- [x] Approve the finite error taxonomy, compatibility alias policy, and
  redaction boundary.
- [x] Approve correlated logging fields, propagation path, and denylist.
- [x] Approve the explicit retry/replay/operator-mode contract.
- [x] Approve server-owned project catalog, selection lifecycle, stale/forged
  selection rejection, and the local-experience limitation.
- [x] Approve the finite graph projection DTO, relation allowlist, bounds,
  freshness, evidence/provenance links, and companion table requirement.
- [x] Approve `@xyflow/react` 12 as a measured implementation candidate subject
  to S8-49; authorize no dependency install until this item is checked.
- [x] Approve the structured Note semantic outcome: reuse released terms and
  defer new ordering, assignment, deadline, generic status, and edit terms.
- [x] Approve the no-migration/no-released-IRI-change compatibility boundary.
- [x] Authorize S8-12 through S8-48 implementation work under these exact
  boundaries.

## Ontology review packet

### Status

`PROPOSAL_ONLY` / `PENDING_HUMAN_REVIEW`. No new class or property is proposed
by S8-09. The complete interview is the
[structured Note competency artifact](../../ontology/competency-questions/structured-note.md).

### Semantic outcome and justification

The current released Note vocabulary answers source-capture identity, parent,
project, author, type, text, evidence, candidate provenance, and capture time.
The Sprint 8 product needs a truthful projection of those facts, not a new
ontology layer for UI fields. Assignment, deadline, status, durable editorial
order, and edit provenance remain deferred because their identity, lifecycle,
temporal, project, and provenance semantics are not yet fully committed.

### Validation evidence

Passed:

- `git diff --check` for the Sprint 8 artifacts.
- Repository inspection of released Note vocabulary, source/evidence shapes,
  competency queries, examples, migrations, and `QuickNoteCaptureService`.
- Package metadata benchmark for the renderer candidates in S8-08.

Not run / not applicable:

- No RDF/SHACL/query test was changed because S8-09 introduces no ontology
  vocabulary or shape.
- The candidate dependency was not installed. S8-49 instead validated the
  bounded custom SVG projection, companion table, cancellation, cyclic graph,
  continuation, and narrow/desktop safety limits.
- No migration, shared graph mutation, deployment, or release was performed.

## Human action requested

G1 approval is recorded above. It authorizes only the listed implementation
boundaries; it does not approve an ontology release, production authentication,
tenant administration, or unreviewed semantic additions.

## S8-68 implementation review

### API and UI matrix

| Boundary | Implemented evidence | Automated result |
| --- | --- | --- |
| Projects/catalog/selection | Server-owned catalog, opaque handles, catalog and selection revisions, Project Overview | API suite; deterministic browser selection |
| Structured Notes | Draft save/update/commit, import proposals/abstention, list/detail, server-derived text and offsets | Structured API/contract tests; deterministic browser lifecycle |
| Candidate collection/review | Labeled queue, bounded edit options, revisioned correction, revalidation, correction-aware confirm/reject contracts | API regressions; browser correction/validation/confirmation journey |
| Graph | Bounded projection, finite filters, one-hop expansion, node detail, companion table | Graph API tests; browser graph/table journey |
| Q&A and diagnostics | Bounded question contract, correlated problem/error state, liveness/readiness | API/client tests; browser Q&A and injected-failure journey |
| IA and accessibility | Projects, Project Overview, Notes, Graph, Review Queue, Q&A, Settings, Diagnostics; skip link, focus-visible, responsive nav | 15 frontend tests; UI contract checker; 4 Playwright cases |

### API contract and migration evidence

- The redacted Application API snapshot is versioned `s8.0` and matches 39
  public backend paths through `npm run check:api-drift`.
- The new public Note/candidate-edit paths are additive. Released raw capture,
  extraction, knowledge, candidate, Q&A, and settings boundaries remain
  available for compatibility; the primary IA no longer exposes legacy
  Capture/Extract/Knowledge shortcut navigation.
- `apps/api/scripts/generate_openapi_snapshot.py` removes the internal
  context-secret header and excludes the internal entity-link path before the
  snapshot is committed.
- No ontology class/property/individual or released IRI was added by S8-61
  through S8-68. The structured Note implementation reuses the released
  vocabulary under the approved S8-53 semantic boundary.

### Graph limits and truthfulness

Initial graph requests are bounded to `nodeLimit` 1–100 and `edgeLimit` 1–200;
one-hop expansion uses a bounded edge limit 1–100. Responses carry source and
materialization revisions, `stale`, `partial`, `hasMore`, and continuation
state. The UI renders a finite accessible table alongside the SVG projection;
it does not expose RDF terms, graph IRIs, storage paths, or arbitrary queries.

### Browser evidence

The deterministic Playwright suite uses route-local fixtures and no live
provider credentials. It passed 4 cases across desktop and narrow Chromium:
project selection, Overview-to-Graph navigation, Note save/import/commit,
graph/table navigation, labeled candidate correction, revision-aware
validation/confirmation, Q&A, no-ID labels, and an injected Graph 503 with a
correlated request ID.

Screenshots captured from the same journey:

- [Desktop Project Overview](evidence/s8-project-overview-desktop.png)
- [Narrow Project Overview](evidence/s8-project-overview-narrow.png)

The narrow capture confirms horizontal navigation remains labeled and usable
after the compact shell breakpoint; the desktop capture confirms the dense
overview hierarchy and companion empty states.

### Failure injection and secret-leak evidence

- API failure-injection coverage is included in the Python regression suite;
  failed provider/Core/crash paths remain finite errors without semantic
  mutation.
- The browser Graph failure fixture preserves the problem detail and request
  correlation instead of showing an empty success state.
- API snapshot generation rejects `_projecta_http_status`, secret references,
  context-secret headers, and `apiKey` fields.
- Deterministic browser fixtures assert no credentials, opaque handles, or RDF
  internals appear in the user-facing journey.
- `run_sprint8_acceptance.ps1 -RunCompose` passed against clean volumes with an
  explicit acceptance-only two-project fixture. It caught and removed an RDF
  graph IRI from bootstrap logs, then passed safe-log scanning and restart
  persistence. Human review remains part of S8-69.

### Validation summary

| Gate | Evidence |
| --- | --- |
| Python | 115 passed, 3 skipped; full-repository Pyright 0 errors, 0 warnings |
| Semantic Core | `mvn verify`: 47 tests passed, 7 skipped |
| Ontology | Container validation: 140/140 checks passed |
| Frontend | 15 Vitest tests; typecheck, lint, and production build passed |
| Browser | 4/4 deterministic desktop/narrow cases passed |
| Contract/security | API drift 39 paths, Nginx, UI contract, implicit behavior, Compose health, clean-volume runtime, safe-log, restart, and diff checks passed |

### Unresolved risks before S8-69

- Automated clean-volume production Compose startup/restart/log scanning and a
  production UI smoke have passed. The human must still review/approve that
  evidence; automation does not close S8-69.
- The local experience catalog is not production authentication or tenant
  administration.
- Future assignment, deadline, durable editorial order, generic status, and
  edit/version semantics remain deferred and require a new semantic review.
- Screenshot evidence covers desktop/narrow Project Overview; automated and
  production smoke cover Notes, Graph, Review Queue correction, Q&A, and
  failure states. Human visual/theme acceptance remains required during M6.

## S8-69 human acceptance checklist

- [ ] Execute or review the clean-volume production web-image journey and
  correlated logs.
- [ ] Approve product truthfulness: empty, stale, abstained, unavailable, and
  error states remain distinguishable.
- [ ] Approve project isolation and server-owned selection behavior.
- [ ] Approve bounded graph semantics, graph/table parity, evidence, lifecycle,
  provenance, and freshness distinctions.
- [ ] Approve structured Note meaning, source-evidence preservation, and
  candidate/review separation.
- [ ] Approve finite error behavior, correlation, retry/recovery policy, and
  absence of prohibited fallbacks.
- [ ] Approve release readiness for Sprint 8/M6.

Until every item above is checked by a human, S8-69 remains pending and no
Sprint 8 or ontology version is marked complete.
