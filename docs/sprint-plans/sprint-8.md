# Sprint 8 Plan — Truthful Multi-Project Graph and Structured Notes

## Status

**Implementation authorized after G1 approval — S8-12 onward.**

The Sprint 8 architecture/security/semantic packet received explicit human
approval for S8-11/G1 on 2026-08-09. This authorizes implementation under the
approved boundaries; it does not release ontology changes or authorize
unreviewed semantic additions.

## Sprint Goal

Turn the Sprint 7 technical workflow into a truthful product experience: every
runtime failure remains an explicit correlated error, users navigate projects and
knowledge through labels and finite graph views instead of memorizing opaque IDs,
and Quick Note becomes a visible structured Note/NoteItem composer while retaining
source text, evidence, lifecycle, project isolation, and provenance.

## Product Corrections Accepted for Planning

- Opaque IDs are internal navigation handles, not user input or primary labels.
- The UI needs a project catalog, project workspace, and safe graph view.
- Every Sprint 8 UI screen, theme, shell, component, and responsive state must be
  designed and validated with the repository-local `$build-databricks-ui` skill.
  The target is a Databricks-inspired professional data workspace, not a copy of
  Databricks branding, product text, trademarks, or proprietary assets.
- A Note is a source artifact containing ordered typed NoteItems; it is not merely
  one unstructured textarea.
- The product path must not swallow an exception, invent an empty/default success,
  silently switch providers/modes, or perform an undeclared retry.
- An explicitly selected test/replay mode is not a fallback. It must be visible in
  configuration and logs and must never activate after a live-path failure.
- Security redaction remains mandatory: clear errors do not expose secrets,
  provider payloads, SPARQL, graph IRIs, stack traces, or cross-project data.

## Current-State Findings

- The released ontology and Semantic Core already represent
  `Note → ordered typed NoteItem`, with nine controlled item types, exact evidence
  spans, candidate lifecycle, and provenance.
- `ExtractionScreen` exposes only raw text; `CaptureScreen` exposes structure as
  manual text selection. Neither behaves like a normal structured note editor.
- `ReviewScreen` asks for an opaque candidate ID. `KnowledgeScreen` asks for
  candidate and knowledge-item IDs. These are implementation shortcuts.
- The local experience injects one fixed `local-project`; there is no finite
  project catalog or user-visible project selection contract.
- The Application API collapses several distinct provider failures into one public
  semantic-unavailable response, some readiness paths synthesize states, and the
  product gateway currently retries retryable failures without exposing attempts.
- Nginx, API, Semantic Core, and Fuseki logs do not yet share one complete
  correlation and outcome schema.

## Definitions

### Fail-explicit

A failed dependency or contract produces one finite non-2xx problem and a
correlated error log. It never becomes `[]`, `{}`, `null`, `unknown`, `partial`,
`unavailable`, or a successful HTTP response unless that value is the documented
domain result rather than a substituted failure.

### Explicit processing

Provider selection, retry count, replay/test mode, degraded behavior, project
selection, inference rebuild, and background work are declared configuration or
user actions. Defaults may exist only for harmless presentation values; they may
not choose authority, data scope, provider, persistence, or semantic meaning.

### User-facing identity

Screens show names, types, status, timestamps, and provenance summaries. Opaque IDs
may remain in typed API routes, browser route state, logs, and diagnostics, but the
user selects an item from a finite server-provided collection rather than typing or
copying an identifier.

## Acceptance Journeys

1. A user opens Projecta, sees the projects they are allowed to access, selects one,
   and sees its overview without editing a project ID or trusted header.
2. A user creates one Note with a title and multiple ordered typed items such as a
   Requirement, Task, Question, and Risk; the system preserves canonical source
   text, exact evidence, author, time, project, order, and provenance.
3. A user pastes unstructured text for assisted extraction, reviews the proposed
   structured draft, edits it, and explicitly saves it; extraction never asserts
   knowledge automatically.
4. A user opens the project graph, filters by type/status, expands a bounded
   neighborhood, selects a labeled node, and follows evidence/history/review links
   without seeing or entering raw graph IRIs or opaque IDs.
5. A user opens a candidate review queue, selects a labeled candidate, validates,
   edits, confirms, or rejects it without entering an ID.
6. A provider timeout, malformed output, Semantic Core failure, Fuseki failure, or
   invalid contract returns a distinct non-2xx problem with request ID; container
   logs show the same request, boundary, error class, attempt, latency, and terminal
   outcome without sensitive data.
7. A failed live provider request is not retried or switched to replay implicitly.
   Any retry is a visible new user action with idempotency behavior explained.

## Architecture Invariants

- Browser code never calls Semantic Core or Fuseki directly and never submits
  SPARQL, graph names, trusted actor IDs, or arbitrary project IDs.
- UI implementation must follow `$build-databricks-ui`: semantic `--dws-*`
  light/dark tokens, 4px spacing grid, compact typography and controls, a 48px
  top bar, approximately 200px desktop navigation, restrained borders/surfaces,
  and no marketing hero, glassmorphism, glow, oversized gradients, or decorative
  card clutter.
- Every screen must implement loading, empty, error, success, disabled, selected,
  hover, focus-visible, long-content, reduced-motion, desktop, and narrow-viewport
  behavior without encoding meaning by color alone.
- Project selection is authorized server-side from a finite visible catalog; the
  selected project is revalidated for every request.
- Graph endpoints expose bounded domain projections, not generic RDF traversal.
- Candidate, asserted, inferred, source, and provenance states remain visibly and
  semantically distinct.
- Structured Note input persists a source artifact first. NoteItems and extracted
  candidates do not bypass SHACL or human review.
- Automatic inference remains deterministic and separately labeled; fail-explicit
  does not mean presenting inferred knowledge as asserted truth.
- Released IRIs are not deleted or repurposed. Any semantic extension follows
  `$projecta-evolve-ontology` and a human release gate.

## Dependency Sequence

```text
Audits and contracts
→ architecture/security/semantic approval
→ fail-explicit runtime boundary
→ project catalog and authorized selection
→ `$build-databricks-ui` theme, shell, and shared UI primitives
→ finite graph projection and candidate collections
→ structured Note contract and composer
→ integrated browser/Compose acceptance
→ human M6 approval
```

## Atomic Tasks

Status legend: [ ] pending / [~] in progress / [x] done

### A. Discovery, contracts, and governance

- [x] **S8-01 — Record the Sprint 8 experience gap audit:** Map every manual ID
      field, raw JSON panel, fixed-project assumption, Note input path, swallowed
      exception, synthesized success/empty state, implicit default, fallback, retry,
      and uncorrelated container log to its owning boundary and test.
- [x] **S8-02 — Define the no-implicit-fallback contract:** Classify allowed domain
      emptiness versus operational failure and publish a boundary matrix for Web,
      Nginx, Application API, Semantic Core, Fuseki, provider adapters, and Compose.
- [x] **S8-03 — Define the finite error taxonomy:** Assign stable internal and
      public problem codes, HTTP status, retryability, redaction, and terminal outcome
      for validation, configuration, provider, timeout, persistence, SHACL, query,
      project-scope, and infrastructure failures.
- [x] **S8-04 — Define the correlated logging contract:** Specify mandatory event,
      timestamp, severity, service, boundary, request/operation ID, project-safe scope,
      attempt, latency, error class, HTTP/upstream status, and outcome fields plus the
      secret/source/payload denylist.
- [x] **S8-05 — Decide the explicit retry contract:** Make the interactive product
      path single-attempt by default; document which future operations may retry, who
      authorizes it, how attempts are surfaced, and why replay can never activate as a
      live failure fallback.
- [x] **S8-06 — Design the authorized project-context boundary:** Define project
      catalog visibility, active-project selection, request scoping, local-experience
      behavior, session/state ownership, and rejection of forged or stale selection.
- [x] **S8-07 — Define the finite graph projection contract:** Specify bounded node,
      edge, neighborhood, filter, pagination, lifecycle, evidence, provenance, and
      freshness fields without exposing RDF terms or arbitrary query capability.
- [x] **S8-08 — Benchmark the web graph renderer:** Compare accessible React-ready
      libraries on bundle size, keyboard support, directed edges, incremental layout,
      bounded expansion, testability, and license; record one implementation choice.
- [x] **S8-09 — Run the structured Note semantic interview:** Write competency
      questions and answer identity, lifecycle, ordering, item-type, project, author,
      assignee, deadline, status, provenance, and temporal questions before proposing
      any new class or property.
- [x] **S8-10 — Prepare the Sprint 8 architecture/security/semantic packet:** Present
      the fail-explicit, project-selection, graph-projection, structured-Note, migration,
      and compatibility decisions with unresolved choices and explicit checkboxes.
- [x] **S8-11 — Obtain the implementation gates:** Require explicit human approval
      of architecture/security decisions and the exact ontology proposal before tasks
      that change those contracts move to implementation.

### B. Fail-explicit runtime and container diagnostics

- [x] **S8-12 — Add a shared operation-correlation model:** Preserve one validated
      request/operation ID through browser, Nginx, API, Semantic Core, Fuseki calls,
      provider attempts, audit records, and response headers.
- [x] **S8-13 — Make Application API startup fail closed:** Remove authority-bearing
      environment defaults and optional production service composition; invalid mode,
      project scope, secret store, provider, or dependency configuration must prevent
      readiness and emit a finite startup error.
- [x] **S8-14 — Remove implicit product-path provider retry:** Execute one live
      provider attempt per interactive extraction request and return its normalized
      terminal failure; retain retry machinery only behind an explicit reviewed mode.
- [x] **S8-15 — Preserve provider error identity at the API boundary:** Map timeout,
      rate limit, connection, provider status, refusal, empty output, malformed schema,
      invalid evidence, and unsafe links to distinct sanitized public problem codes.
- [x] **S8-16 — Make API route dependencies explicit:** Replace missing optional
      services, generic `ValueError`/`RuntimeError`, synthesized readiness, and unknown
      request IDs with validated composition or finite typed failures.
- [x] **S8-17 — Emit one provider-attempt event:** Log start and terminal outcome
      with attempt number, configured timeout, model/profile revision, latency, token
      counters when available, and safe error class; never log prompts or output.
- [x] **S8-18 — Make Semantic Core handlers fail explicitly:** Ensure parse,
      validation, lifecycle, TDB2/Fuseki, and unexpected exceptions produce typed
      non-2xx responses and terminal structured logs rather than empty or generic
      success bodies.
- [x] **S8-19 — Add Semantic Core lifecycle and query events:** Emit correlated
      start/outcome logs for capture, validation, confirmation, rejection, project
      catalog, graph projection, evidence, and inference operations.
- [x] **S8-20 — Correlate Fuseki query/update diagnostics:** Attach safe operation
      metadata to gateway logs and report endpoint, operation kind, status, latency,
      timeout, and result cardinality without printing SPARQL or RDF payloads by default.
- [x] **S8-21 — Configure Nginx structured access/error logs:** Include request ID,
      route class, method, status, request/upstream time, upstream status/address, and
      connection outcome while excluding bodies, credentials, and trusted headers.
- [x] **S8-22 — Make Compose health failures diagnosable:** Separate liveness from
      readiness, retain probe exit evidence, and document commands that identify which
      dependency and contract failed without converting not-ready into healthy.
- [x] **S8-23 — Make the web client reject invalid responses:** Treat non-JSON,
      wrong content type, schema drift, missing request ID, and malformed success bodies
      as explicit client contract errors instead of manufacturing a generic success or
      silently rendering nothing.
- [x] **S8-24 — Add the implicit-behavior regression gate:** Fail CI on banned
      provider/project defaults, catch-and-ignore paths, fallback provider/replay
      activation, empty-success substitutions, and unreviewed automatic retries while
      supporting an explicit allowlist with rationale.
- [x] **S8-25 — Add cross-container failure-injection tests:** Exercise provider
      timeout/rate limit/schema failure, API crash, Semantic Core 4xx/5xx, Fuseki
      unavailable/invalid response, and Nginx upstream timeout; assert one correlated
      terminal error and no semantic mutation.

### C. Project catalog and navigable workspace

- [x] **S8-26 — Define the project catalog read model:** Specify user-facing name,
      summary, status, visible counts, last activity, health indicators, and opaque
      navigation handle sourced from project-scoped authoritative data.
- [x] **S8-27 — Implement the Semantic Core project catalog query:** Return only
      projects visible to the trusted actor with deterministic ordering and no
      cross-project counts, graph IRIs, or arbitrary filtering.
- [x] **S8-28 — Implement the project overview query:** Return one authorized
      project's labeled summary, current knowledge/candidate/note counts, recent
      activity, blockers, risks, and inference freshness through a finite contract.
- [x] **S8-29 — Expose typed project catalog APIs:** Add list/read/select endpoints
      with generated schemas, pagination bounds, explicit empty-domain behavior, and
      distinct forbidden/not-found/stale-selection errors.
- [x] **S8-30 — Implement authorized active-project selection:** Store and validate
      a selection only from the returned catalog; reject arbitrary IDs and clear stale
      selection explicitly rather than reverting to `local-project`.
- [x] **S8-31 — Audit the Sprint 8 visual system with `$build-databricks-ui`:**
      Classify every target screen as shell, overview, explorer/list, editor, form,
      review queue, or diagnostics; record current hierarchy, density, token,
      interaction-state, responsive, overflow, and accessibility gaps at 1440×900
      and approximately 390×844.
- [x] **S8-32 — Install the semantic workspace theme:** Map the skill's `--dws-*`
      light/dark tokens, system typography, 4px grid, control/panel geometry,
      borders, state colors, reduced motion, and focus treatment into the existing
      Projecta stylesheet without introducing a UI framework or one-off palette.
- [x] **S8-33 — Redesign the application shell:** Implement the skill's compact
      48px top bar, approximately 200px grouped sidebar, one clear New Note action,
      project/workspace context, 32px navigation rows, scroll ownership, and
      responsive rail/drawer behavior while preserving skip link, landmarks, and
      `aria-current`.
- [x] **S8-34 — Build shared dense workspace primitives:** Restyle or add compact
      toolbars, breadcrumbs, search/filter controls, tables, split panes, editor
      surfaces, forms, status messages, skeletons, empty/error/success states,
      dialogs, and destructive actions; validate the stylesheet with the skill's
      `check-ui-contract.mjs` gate.
- [x] **S8-35 — Build the Projects screen:** Show searchable labeled project cards,
      meaningful status/count/activity summaries, explicit empty/error states, and a
      user selection action without an ID input.
- [x] **S8-36 — Build the Project workspace header:** Keep active project name,
      status, freshness, navigation, and change-project action visible on every
      project-scoped screen without exposing trusted headers or graph identifiers.
- [x] **S8-37 — Build the Project overview screen:** Present current requirements,
      open questions, tasks, blockers, risks, recent notes, pending candidates, and
      evidence coverage as navigable labeled collections.
- [x] **S8-38 — Add multi-project isolation tests:** Prove catalog, selection,
      overview, graph, note, candidate, evidence, Q&A, and logs cannot leak another
      project even when a browser route or stale opaque handle is forged.

### D. Finite graph view and ID-free knowledge workflows

- [x] **S8-39 — Define graph projection DTOs:** Add strict node/edge/page/detail
      contracts with stable display labels, semantic type, lifecycle/verification
      state, direction, evidence count, and internal opaque navigation handles.
- [x] **S8-40 — Implement bounded graph projection queries:** Retrieve an initial
      project subgraph and one-hop expansion with allowlisted node/relation types,
      deterministic limits, project isolation, and asserted/inferred provenance flags.
- [x] **S8-41 — Expose graph projection endpoints:** Add typed initial-view,
      neighborhood, node-detail, evidence-link, and lifecycle-link APIs; reject unknown
      filters, excessive limits, arbitrary paths, SPARQL, and graph names.
- [x] **S8-42 — Build the project Graph screen:** Render labeled directed nodes and
      relations with legend, zoom, pan, bounded expansion, loading, empty, stale, and
      explicit error states using the approved renderer.
- [x] **S8-43 — Add graph filters and truthful state styling:** Filter by domain
      type, candidate/asserted/inferred state, lifecycle status, evidence availability,
      and relation type without merging or visually equating those states.
- [x] **S8-44 — Build the graph node detail panel:** Show label, type, status,
      project, dates, source/evidence summary, provenance, relations, and available
      actions; keep opaque IDs in diagnostics only.
- [x] **S8-45 — Add the candidate review queue:** List pending candidates with
      human labels, source excerpt, proposed type/relations, validation state,
      confidence, and age; open review from selection rather than ID entry.
- [x] **S8-46 — Replace the Review ID form:** Route selected candidates into a
      complete review/edit/confirm/reject experience and remove the candidate-ID input
      while preserving stale/not-found/conflict errors.
- [x] **S8-47 — Replace Knowledge ID forms:** Navigate current items, history, and
      evidence from project collections and graph node actions; remove candidate/item
      ID inputs and raw-ID-first labels.
- [x] **S8-48 — Add an accessible graph companion table:** Provide keyboard and
      screen-reader navigation over the same finite graph projection as a first-class
      view, not as a failure fallback or a separate truth source.
- [x] **S8-49 — Add graph performance and safety limits:** Verify node/edge budgets,
      cancellation, layout latency, repeated expansion, cyclic relations, stale
      revisions, and oversized-project behavior without truncating silently.

### E. Structured Note and NoteItem experience

- [x] **S8-50 — Define the structured Note draft contract:** Model title, ordered
      typed items, item content, optional source metadata, and explicit draft status;
      derive canonical raw text and exact evidence offsets deterministically on the
      server rather than requiring users to calculate spans.
- [x] **S8-51 — Propose the smallest ontology extension:** Reuse released `Note`,
      `NoteItem`, item types, provenance, people, projects, tasks, and requirements;
      propose only competency-backed terms needed for item order, assignee/requester,
      due/effective date, work status, or source context.
- [x] **S8-52 — Produce ontology validation artifacts:** For any approved proposal,
      draft ontology/SHACL, positive and negative fixtures, competency queries,
      compatibility notes, migration/deprecation guidance, and a human review packet.
- [x] **S8-53 — Obtain semantic implementation approval:** Keep all new ontology
      terms and validation behavior `PROPOSAL_ONLY` until the human approves exact
      meaning, names/IRIs, constraints, inference impact, and compatibility path.
- [x] **S8-54 — Implement the approved Note semantic contract:** Load approved
      ontology/shapes at bootstrap and every write boundary, preserve named-graph
      separation, and validate canonical source text, ordered items, evidence,
      project, author, time, and provenance before commit.
- [x] **S8-55 — Implement structured Note application APIs:** Add create/read/list
      draft and committed Note contracts with optimistic concurrency, idempotency,
      finite type vocabularies, server-derived offsets, and explicit validation errors.
- [x] **S8-56 — Build the unified Note Composer:** Let users add, reorder, edit, and
      remove labeled typed item cards; show type-specific approved fields and a
      canonical source/evidence preview without exposing offsets as required input.
- [x] **S8-57 — Add assisted text import into the composer:** Extract pasted text
      into an editable structured draft, display abstention or every proposed item and
      relation, and require explicit user save; never persist a fallback raw Note when
      extraction fails.
- [x] **S8-58 — Add structured candidate editing:** Allow supported type, label,
      relation, entity-link, date, and assignment corrections before confirmation;
      revalidate every edit and retain edit provenance.
- [x] **S8-59 — Add Note browsing and detail views:** List notes by human title,
      author, time, item-type summary, candidate state, and evidence coverage; show
      ordered items and linked graph knowledge without requiring note IDs.
- [x] **S8-60 — Add structured Note contract tests:** Cover ordering, Unicode,
      server-derived offsets, empty/duplicate items, invalid type-specific fields,
      project isolation, idempotency, concurrency, SHACL rollback, provenance, and
      backward compatibility with released raw/segment captures.

### F. Integration, migration, and acceptance

- [x] **S8-61 — Regenerate the Application API client:** Commit the OpenAPI snapshot
      and TypeScript types for project, graph, candidate collection, Note draft, and
      finite problem contracts; keep the drift gate blocking mismatches.
- [x] **S8-62 — Migrate the web information architecture:** Replace the
      Overview/Extract/Capture/Review/Knowledge shortcut navigation with Projects,
      Project Overview, Notes, Graph, Review Queue, Q&A, Settings, and Diagnostics.
- [x] **S8-63 — Add frontend component and accessibility tests:** Cover project
      switching, no-ID workflows, graph/table parity, structured composer keyboard
      behavior, visible lifecycle distinctions, explicit error announcements,
      light/dark semantic equivalence, responsive shell collapse, focus visibility,
      long-content overflow, and the `$build-databricks-ui` contract checker.
- [x] **S8-64 — Add deterministic browser journeys:** Cover project selection,
      structured Note creation, assisted import/review, graph navigation, candidate
      decision, evidence/history traversal, Q&A, and every injected failure without
      live provider credentials.
- [x] **S8-65 — Add clean Compose acceptance:** From clean volumes, verify
      correlated container logs, no authority-bearing defaults, multi-project
      isolation, project/graph/Note workflows, restart persistence, and failure
      truthfulness through the production web image.
- [x] **S8-66 — Run released semantic and application regressions:** Execute the
      Sprint 1–7 canonical suites, ontology checks, Java/Python/frontend validation,
      image/config validation, and explicit compatibility fixtures; never report an
      unconfigured command as passing.
- [x] **S8-67 — Write user and operator runbooks:** Document project bootstrap and
      selection, structured Note workflow, graph semantics, candidate review, error
      codes, request correlation, log queries, retry policy, recovery, and prohibited
      fallback behavior.
- [x] **S8-68 — Prepare the Sprint 8 review packet:** Include decision approvals,
      ontology status, API/UI matrix, screenshots, graph limits, migration evidence,
      failure-injection logs, secret-leak evidence, validation results, and unresolved
      risks.
- [ ] **S8-69 — Approve or revise M6:** Human completes the acceptance journeys and
      explicitly approves product truthfulness, project isolation, graph semantics,
      structured Note meaning, error behavior, and release readiness before Sprint 8
      or any ontology version is marked complete.

## Definition of Done

- No released user journey asks a person to type or remember a candidate,
  knowledge-item, note, project, source, activity, or graph identifier.
- A finite authorized Projects screen and persistent workspace selection scope all
  project operations without browser-controlled trusted identity.
- The Graph screen provides bounded labeled navigation across project knowledge,
  lifecycle, evidence, and provenance while preserving state distinctions and
  hiding RDF/storage internals.
- The Note Composer creates one source Note with multiple ordered typed NoteItems;
  server-derived canonical text and offsets remain exact and auditable.
- The complete application uses the `$build-databricks-ui` semantic token system
  and page patterns with a calm dense workspace hierarchy, equivalent light/dark
  themes, compact shell/controls/tables, no decorative marketing treatment, and no
  horizontal page overflow at the required desktop and narrow viewports.
- UI completion includes visible keyboard focus, labeled controls, logical tab
  order, async announcements, reduced motion, and explicit loading, empty, error,
  success, disabled, selected, hover, and long-content states; the skill UI-contract
  checker and repository frontend checks pass.
- Assisted extraction produces an editable draft or an explicit error/abstention;
  it never silently stores raw text or asserts knowledge as a fallback.
- Every failure class returns a finite non-2xx problem and produces one correlated
  terminal event across applicable containers; no dependency failure becomes an
  empty, partial, default, or successful response.
- Interactive live extraction performs no undeclared retry or provider/mode switch.
- All semantic changes have competency questions, fixtures, validation evidence,
  migration analysis, and explicit human approval before release.
- Clean Compose and Sprint 1–7 compatibility suites pass with no secret, raw
  provider payload, arbitrary query, graph IRI, or cross-project data leakage.

## Non-Goals and Guardrails

- Do not add Teams, Outlook, Jira, webhook, polling, OAuth, or outbound connector
  actions in Sprint 8; those move to Sprint 9+ after this experience is trustworthy.
- Do not expose a generic RDF browser, arbitrary SPARQL, graph names, TDB2 paths,
  provider payloads, stack traces, or trusted context headers.
- Do not make opaque IDs globally meaningful, editable, or primary UI labels.
- Do not add an unbounded graph query or render the whole project graph by default.
- Do not make a visual graph the only accessible navigation mechanism.
- Do not copy Databricks trademarks, logos, proprietary illustrations, product
  text, authenticated URLs, account identifiers, or screenshots; the skill supplies
  a design language and offline references, not brand authorization.
- Do not introduce a UI framework solely for redesign, improvise another color or
  spacing system, shrink text below 12px for density, or use glassmorphism, neon
  glow, oversized gradients, heavy card shadows, and scale-on-hover effects.
- Do not treat raw text as authoritative structured truth or discard it after
  structure is created; it remains source evidence.
- Do not let structured forms bypass candidate review, SHACL, provenance, project
  isolation, or lifecycle rules.
- Do not add ontology vocabulary for UI layout, retries, log severity, graph
  coordinates, selection state, or other operational concerns.
- Do not delete or rename released ontology terms; use additive evolution or a
  reviewed deprecation/migration path.
- Do not claim authentication, tenant administration, connector readiness, or
  production observability from the local multi-project experience.

## Expected Artifacts

```text
docs/architecture/sprint-8-experience-gap-audit.md
docs/architecture/fail-explicit-runtime-contract.md
docs/architecture/error-taxonomy.md
docs/architecture/correlated-logging.md
docs/architecture/project-context-selection.md
docs/architecture/graph-projection-api.md
docs/architecture/graph-renderer-benchmark.md
docs/architecture/sprint-8-ui-design-audit.md
docs/ontology/structured-note-proposal.md
docs/sprint-plans/sprint-8/review-packet.md
docs/sprint-plans/sprint-8/artifacts/
ontology/competency-questions/structured-note.md
ontology/examples/structured-note-draft.trig
apps/api/src/projecta_api/projects/
apps/api/src/projecta_api/graph/
apps/api/src/projecta_api/notes/
apps/web/src/screens/ProjectsScreen.tsx
apps/web/src/screens/ProjectOverviewScreen.tsx
apps/web/src/screens/GraphScreen.tsx
apps/web/src/screens/NotesScreen.tsx
apps/web/src/screens/NoteComposerScreen.tsx
apps/web/src/screens/ReviewQueueScreen.tsx
apps/web/src/styles.css
scripts/run_sprint8_validation.ps1
scripts/run_sprint8_acceptance.ps1
docs/runbooks/sprint-8-user-guide.md
docs/runbooks/sprint-8-operations.md
```

Ontology paths in this list are expected review artifacts, not pre-approved file
names or authorization to implement semantic changes.

## Notes / Blockers

- Sprint 7 S7-47 remains a separate human acceptance gate. Sprint 8 audits and
  proposals may start, but released Sprint 7 behavior must not be silently rewritten
  without compatibility evidence.
- Multi-project selection without a production authentication provider is limited
  to an explicitly configured local/experience allowlist. It must not be described
  as tenant administration or production authorization.
- The meaning of assignee/requester, due versus effective date, NoteItem order,
  typed status, and edit provenance requires the S8-09 semantic interview; this
  plan deliberately does not approve those terms.
- “No fallback” does not prohibit domain-valid empty collections, explicit user
  cancellation, deterministic inference, accessibility companion views, or an
  explicitly selected replay test mode. Each must be distinguishable from failure.
- Container logs must be actionable without violating the existing secret,
  provider-payload, source-text, project-isolation, and internal-IRI boundaries.
- Before editing Sprint 8 UI code, the implementer must load
  `$build-databricks-ui` plus its design-language, page-patterns,
  Projecta-integration, and visual-audit references; completion requires the
  skill's frontend checks, UI-contract command, and desktop/narrow visual review.
