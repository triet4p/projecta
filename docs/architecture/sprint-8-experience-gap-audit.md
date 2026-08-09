# Sprint 8 Experience Gap Audit

**Status:** `IMPLEMENTATION_BASELINE` — S8-01
**Scope:** Sprint 7 web/API/Compose experience carried into Sprint 8
**Audit date:** 2026-08-09

## Purpose and boundary

This audit records the current experience gaps that Sprint 8 must resolve. It
is an evidence inventory, not an implementation approval and not an ontology
change. The audit separates user-facing truthfulness gaps from already-valid
domain outcomes such as an explicit empty collection or an extraction
abstention.

The evidence was checked against the current React client, FastAPI boundary,
Semantic Core boundary, Compose configuration, existing browser/API tests, and
the released Sprint 4–7 contracts. Line references below point to the current
repository state and are intentionally concrete so each gap can acquire an
owning task and regression test.

## Findings at a glance

| Gap family | Current evidence | Sprint 8 owner | Risk if unchanged |
| --- | --- | --- | --- |
| Manual opaque-ID workflow | Review and Knowledge screens require candidate/item IDs; real browser E2E fills them manually. | S8-35, S8-45–S8-47 | Users must copy internal identifiers and can target stale or wrong project data. |
| Raw/internal JSON presentation | Shared `SafeJson` and validation `<pre>` surfaces expose structured payloads; Q&A renders facts/citations/meta directly. | S8-31–S8-34, S8-37 | Storage/API shape becomes the product language and leaks internal distinctions into UI. |
| Fixed local project assumption | Compose and API settings default experience project/actor values; Semantic Core has a fixed trusted-project configuration. | S8-06, S8-26–S8-30 | Local convenience can be mistaken for project catalog, authorization, or tenant administration. |
| Unstructured Note entry | Extraction uses one raw textarea; Capture uses raw textarea plus manual evidence selection. | S8-50–S8-60 | The product does not create an ordered typed Note/NoteItem source artifact. |
| Fallback and retry ambiguity | Provider retry machinery is reusable and bounded, but interactive policy is not yet separated; UI has generic unavailable/empty states. | S8-02, S8-05, S8-12–S8-25 | Dependency failure can look like a valid empty result or an implicit retry/mode switch. |
| Error/log correlation gaps | Request IDs exist at selected boundaries, but no one cross-container event schema is frozen. | S8-03–S8-04, S8-12, S8-17–S8-25 | Operators cannot prove one terminal outcome or connect browser/API/Core/Fuseki events. |

## Evidence inventory

### 1. User-facing identity and raw payload gaps

| ID | Boundary and evidence | Classification | Required resolution |
| --- | --- | --- | --- |
| UX-ID-01 | `apps/web/src/screens/ReviewScreen.tsx:89-101` labels an input `Opaque candidate ID`, stores it in local state, and uses it to validate/confirm/reject. `apps/web/tests/e2e/sprint7.real.spec.ts:62-77` fills the same ID fields. | Confirmed user-input gap. | Replace with selection from a finite candidate collection and route state that remains opaque internally. |
| UX-ID-02 | `apps/web/src/screens/KnowledgeScreen.tsx:91-99` asks for `Candidate ID`; `:116-124` asks for `Knowledge item ID`. | Confirmed user-input gap. | Navigate from project collections, history, evidence, and graph node actions. |
| UX-ID-03 | `apps/web/src/screens/CaptureScreen.tsx:148-165` displays `Candidate IDs` and sends an opaque candidate ID through a click callback; `apps/web/src/screens/ExtractionScreen.tsx:74-84` renders candidate IDs as review labels. | Confirmed raw-identity presentation gap, even when the ID is not typed. | Show human label/type/status and keep opaque handles in route/diagnostic state only. |
| UX-JSON-01 | `apps/web/src/ui.tsx:54-55` exposes a generic `SafeJson`; `apps/web/src/screens/QuestionScreen.tsx:87-98` renders facts, citations, and meta through it. | Confirmed raw/internal representation gap. Redaction prevents some leaks but does not provide a domain UI. | Replace with typed labeled collections and an explicit diagnostics-only representation. |
| UX-JSON-02 | `apps/web/src/screens/ReviewScreen.tsx:109-113` serializes validation violations into a raw `<pre>`. | Confirmed raw validation presentation gap. | Render stable violation code, field/path, safe message, and remediation affordance. |
| UX-JSON-03 | `apps/web/src/screens/KnowledgeScreen.tsx:75-80,103-109,126-139` displays opaque IDs, activity IDs, source IDs, and `unavailable`/`?` substitutions. | Confirmed identity and missing-data presentation gap. | Use finite typed views with explicit unknown/stale/error states. |

### 2. Project and trusted-context gaps

| ID | Boundary and evidence | Classification | Required resolution |
| --- | --- | --- | --- |
| CTX-01 | `compose.yaml:115-116` defaults `PROJECTA_API_EXPERIENCE_PROJECT_ID` to `local-project` and actor to `local-user`; `apps/api/src/projecta_api/config.py:44-45` repeats those defaults. | Confirmed authority-bearing default. | Make the experience scope explicit and expose a finite server-provided catalog; no browser-controlled project identity. |
| CTX-02 | `compose.yaml:178` sets `SEMANTIC_CORE_TRUSTED_PROJECT_ID` to `ecommerce-checkout`; `apps/api/src/projecta_api/context.py:52-65` injects fixed server-owned context only in experience mode. | Confirmed split fixed-project assumptions. | Define one authorized project-context contract and reject stale/forged selections without reverting to a default project. |
| CTX-03 | `apps/api/src/projecta_api/context.py:19-49` accepts trusted context headers only with a configured secret; production mode rejects the local context. | Existing security control with incomplete product contract. | Preserve server ownership, document the local allowlist boundary, and add catalog/selection tests. |

### 3. Note input and source-artifact gaps

| ID | Boundary and evidence | Classification | Required resolution |
| --- | --- | --- | --- |
| NOTE-01 | `apps/web/src/screens/ExtractionScreen.tsx:14-57` accepts one raw-note textarea and sends `{rawText, extractionVersion}`. | Confirmed unstructured assisted-extraction path. | Produce an editable structured draft; abstention/error must not save a raw fallback. |
| NOTE-02 | `apps/web/src/screens/CaptureScreen.tsx:28-65,77-143` accepts raw text and manually selected typed spans, then calls `captureQuickNote`. | Confirmed manual span-first path. | Composer owns ordered typed items; the server derives canonical source text and exact offsets. |
| NOTE-03 | `apps/api/src/projecta_api/models.py:31-65` exposes raw text plus segments for capture and raw text for extraction; `docs/architecture/application-api.md` documents the released contract. | Existing released contract, not itself a bug. | Preserve compatibility while adding the S8 structured Note contract additively. |
| NOTE-04 | `services/semantic-core/src/main/java/org/projecta/semanticcore/QuickNoteCaptureService.java:163-242` materializes NoteItem/candidate/activity data with project-scoped IRIs and source offsets. | Existing semantic foundation to reuse. | Keep named-graph, provenance, evidence, and lifecycle invariants while changing the authoring experience. |

### 4. Failure, fallback, and retry gaps

| ID | Boundary and evidence | Classification | Required resolution |
| --- | --- | --- | --- |
| FAIL-01 | `apps/api/src/projecta_api/llm/resilience.py:13-48` implements up to one initial provider attempt plus configured retries for retryable errors. | Confirmed reusable retry mechanism; product policy is not yet explicit per operation. | S8-05 must distinguish interactive single-attempt behavior from explicitly selected test/retry modes. |
| FAIL-02 | `apps/web/src/shell/App.tsx:29-43,101-174` turns missing liveness into `API offline` and offers `Retry liveness`; `apps/web/src/screens/DiagnosticsScreen.tsx:45-61` uses `unavailable` when data is absent. | Mixed state: user retry is explicit, but missing response and dependency failure are not yet a frozen finite taxonomy. | Define liveness/readiness/result/error distinctions and preserve request correlation. |
| FAIL-03 | `apps/web/src/screens/QuestionScreen.tsx:87-98` renders empty facts/citations/meta as normal empty sections; `ExtractionScreen.tsx:65-70,105-109` distinguishes abstention and no-entity results but does not yet expose a full error contract. | Potential domain-empty versus operational-failure ambiguity. | S8-02 must classify allowed empty/abstained outcomes and ban substituted empty success. |
| FAIL-04 | `apps/api/src/projecta_api/configuration/connection.py:34-53` collapses provider timeout into `unavailable` and other provider exceptions into `unhealthy`; `docs/architecture/llm-extraction-errors.md` contains a richer private taxonomy that is not yet the Sprint 8 cross-boundary taxonomy. | Confirmed taxonomy mismatch across configuration/provider paths. | S8-03 must unify stable classes, public problems, retryability, and redaction. |
| FAIL-05 | `services/semantic-core/src/main/java/org/projecta/semanticcore/SemanticCoreApplication.java:208-244` translates runtime exceptions at one HTTP boundary, while individual services throw `IllegalStateException` for unavailable replay/store/shape paths. | Existing typed boundary with incomplete operation-level event contract. | S8-02–S8-04 and S8-18–S8-20 must preserve failure identity and terminal evidence. |

### 5. Logging and observability gaps

| ID | Boundary and evidence | Classification | Required resolution |
| --- | --- | --- | --- |
| LOG-01 | `apps/api/src/projecta_api/extraction/telemetry.py:9-34` emits extraction events with request context, but the contract is extraction-specific. | Existing partial correlation. | Generalize one operation/event schema across Web, Nginx, API, Semantic Core, Fuseki, and provider attempts. |
| LOG-02 | `apps/api/src/projecta_api/configuration/audit.py:14-60` records configuration audit fields, but no Sprint 8 shared boundary schema proves operation start/terminal outcome across services. | Existing partial operational audit. | S8-04 defines mandatory fields and denylist; S8-12+ implement propagation. |
| LOG-03 | `apps/web/nginx.conf:1-28` forwards request identity and proxy errors but does not yet define the complete structured access/error outcome schema required by S8-21. | Confirmed contract gap. | Add route class, upstream result, latency, connection outcome, and redaction rules. |
| LOG-04 | `services/semantic-core/src/main/java/org/projecta/semanticcore/FusekiQueryService.java:151-152` converts invalid store responses into an exception; safe operation metadata and result cardinality are not part of one shared event contract. | Confirmed diagnostic gap. | S8-20 defines safe Fuseki query/update diagnostics without SPARQL/RDF payloads. |

## Ownership and test mapping

| Gap group | Primary owner | Regression evidence to add |
| --- | --- | --- |
| UX-ID / UX-JSON | Web screens and typed Application API client | Component/accessibility tests, deterministic browser journeys, no-ID assertions, no raw JSON primary panels. |
| CTX | API context middleware, Compose, Semantic Core trusted boundary | Forged/stale selection tests, cross-project isolation, production/local profile negative tests. |
| NOTE | Note contract, Semantic Core, web composer | Ordered items, Unicode offsets, SHACL rollback, provenance, compatibility fixtures. |
| FAIL | Gateway, API error mapping, web client | Failure injection for timeout/rate limit/schema/Core/Fuseki/Nginx and one correlated terminal error. |
| LOG | Nginx, API, Semantic Core, Fuseki gateway, provider adapter | Correlation/event schema assertions and secret/source/provider-payload leak scans. |

## Decisions deliberately deferred to S8-02 through S8-10

- Which empty results are domain-valid and which are substituted failures.
- The finite internal/public error taxonomy and HTTP mapping.
- The required cross-container event fields and redaction denylist.
- Whether interactive extraction is single-attempt by default and which modes
  may retry.
- The finite authorized project catalog and active-selection lifecycle.
- The graph projection DTOs, limits, filters, accessible renderer, and state
  semantics.
- The competency-backed Note semantic commitments and any ontology extension.

## S8-01 completion criteria

- Every gap family in the S8-01 task is mapped to a concrete current artifact.
- Confirmed gaps are distinguished from valid domain-empty or abstention states.
- Each gap has an owning follow-up task and expected regression evidence.
- No implementation or ontology release is implied by this audit.
