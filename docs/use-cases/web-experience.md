# Web Experience Use Case — Sprint 7 M5 Journey

**Status:** IMPLEMENTATION_BASELINE
**Task:** S7-01

## Purpose

This document defines the first user-facing Projecta journey across the
released M2 manual capture, M3 LLM extraction, candidate review, and M4
grounded retrieval capabilities. It is a product and acceptance boundary for
the web client; it does not define the frontend framework, secret-store
implementation, authentication provider, or new ontology terms.

The user must be able to move from opening the local Projecta experience to
configuring an LLM profile, capturing or extracting a note, reviewing a
candidate, and reading grounded project context. The browser calls only the
Application API. It never chooses trusted project or actor identity, accesses
Semantic Core/Fuseki, sends arbitrary SPARQL, or receives a deployment secret.

## Actors and Preconditions

The actor is a BrSE, Project Coordinator, or Technical Business Analyst using
the local experience profile. A deployment-owned experience adapter establishes
the project ID, actor ID, and request ID before project-scoped application work
begins. The browser may display the selected project context, but it cannot
override that context or submit the shared trust secret.

The canonical Compose stack is running with the Application API, Semantic Core,
and Fuseki healthy. The user either has the headless environment LLM profile
from `PROJECTA_LLM_*` or configures an interactive profile through the Sprint 7
settings boundary. Interactive settings return metadata and redacted status
only; raw credentials remain server-owned.

## Journey Overview

| Stage | User intent | Application boundary | Released behavior or Sprint 7 seam |
|---|---|---|---|
| Open | Start working in one project | Experience context and health surfaces | New S7 local context/diagnostics seam; fail closed outside the explicit local profile. |
| Configure | Make live extraction usable | Runtime configuration and secret-store ports | New S7 settings workflow; read is redacted, writes/rotation/removal are explicit. |
| Extract | Turn an untyped note into reviewable proposals | `POST /v1/quick-notes/extractions` with `Idempotency-Key` | Released M3 candidate-only extraction, exact evidence, bounded links, and abstention. |
| Capture | Record typed evidence manually | `POST /v1/quick-notes` with `Idempotency-Key` | Released M2 ordered, non-overlapping Unicode-code-point spans. |
| Review | Decide what becomes knowledge | Validation, confirmation, and rejection routes | Released lifecycle; confirmation is limited to `Requirement`. |
| Inspect | Understand current knowledge and evidence | Current items, candidate history, and evidence reads | Released bounded project-scoped reads using opaque IDs. |
| Ask | Get grounded project context | `POST /v1/project-context/answers` | Released M4 intents: current requirements, requirement history, unresolved blockers. |

Settings and local-context route names are deliberately left to S7-02/S7-08;
the existing released paths above are the source of truth for the semantic
workflow.

## Main Flow

1. The user opens the web app. The shell shows that the experience is local,
   identifies the server-established project context without exposing trust
   material, and reports whether the API and semantic dependencies are usable.
2. The user opens Settings and supplies provider type, base URL, model, and a
   credential. The server validates the allowlist and URL policy, stores the
   credential through the approved secret boundary, and returns only provider
   metadata, active revision, and credential-configured/health status. The
   credential field is cleared from frontend state after submission.
3. The user enters an untyped note and selects **Extract**. The application
   sends the canonical raw text and an idempotency key. The extraction path
   obtains bounded same-project link context, calls the provider-neutral
   gateway, normalizes model output, recomputes evidence from Unicode
   code-point offsets, and persists only normalized reviewable candidates.
4. The UI displays extracted entities, relations, links, evidence spans, model
   metadata safe for the client contract, and an explicit abstention state when
   the model returns no candidate. Provider payloads and credentials are never
   displayed.
5. Alternatively, the user selects exact typed spans in the manual capture
   flow. The UI previews the selected text and rejects empty, overlapping,
   unordered, out-of-range, or mismatched spans before sending the M2 request.
6. The user opens a candidate, requests validation, and sees the semantic
   validation result and current lifecycle state. The UI enables **Confirm**
   only for the released `Requirement` assertion shape. Other candidate types
   can be rejected but cannot be presented as confirmable assertions.
7. On confirmation, the application sends the assertion label, valid-from date,
   and idempotency key. On rejection, it sends a non-empty reason and
   idempotency key. The result shows the terminal state and request ID; a
   repeated decision is rendered as a replay or conflict according to the
   released contract.
8. The user opens the knowledge/evidence view. Current knowledge, candidate
   history, and evidence are read through bounded project-scoped routes. The
   UI displays opaque IDs, source text/evidence spans, actors, timestamps, and
   provenance without exposing RDF IRIs, graph names, or storage URLs.
9. The user asks a supported project question. The Application API maps it to
   one of the released M4 intents and returns a grounded answer with structured
   facts, citations, asserted/inferred status, derivation, completeness, and
   freshness warnings. The UI does not provide a query editor or arbitrary
   filter control.

## Recovery and Failure Paths

| Situation | User experience | Semantic guarantee |
|---|---|---|
| Missing/invalid local context | Show the experience as unavailable and do not show project data. | Request is rejected before payload processing with `PROJECT_CONTEXT_REQUIRED`. |
| Settings validation failure | Keep the prior active profile, show field-safe validation, and clear the submitted credential field. | Invalid provider/model/URL/credential is not activated or returned. |
| Secret store unavailable | Show a retryable configuration error with request ID. | No partial profile activation and no raw credential in logs or response. |
| Provider timeout/rate limit/failure | Preserve the note in the editor, show a retry action, and do not invent candidates. | No semantic mutation is committed by a failed extraction. |
| Valid extraction abstention | Show “no candidates proposed” plus the abstention reason when safe. | A successful empty extraction remains auditable and does not become an error or assertion. |
| Invalid evidence/model output | Show a sanitized extraction failure and allow a bounded retry. | Invalid evidence, links, schema, or normalization stops before persistence. |
| Manual span validation error | Highlight the offending span and keep the note editable. | No capture request or semantic mutation is made. |
| Candidate decision conflict/double click | Disable duplicate submission, show the terminal/conflicting state, and preserve the request ID. | Idempotency and lifecycle rules prevent duplicate or contradictory assertions. |
| Semantic Core unavailable | Show dependency-unavailable state and retain unsent local form input only for the current workflow. | No graph detail, stack trace, or partial write is exposed. |
| Stale/partial M4 projection | Show the answer with explicit completeness/freshness warning or abstain. | Stale context is never presented as current truth without metadata. |
| Browser reload during review | Recover only from released read/list contracts; otherwise require the user to retain the opaque candidate ID in the active workflow. | Sprint 7 does not promise candidate recovery until a stable list/read contract exists. |
| Production profile selected | Disable the local experience adapter and show setup guidance. | Local fixed/allowlisted context cannot become production authentication. |

## Acceptance Examples

### A. Configure and extract an untyped note

Given the local experience is bound to project `ecommerce-checkout` and actor
`le`, the user saves a valid interactive LLM profile and submits:

```json
{
  "rawText": "The checkout team owns the tax API timeout investigation.",
  "extractionVersion": "m3.v1"
}
```

The API returns a successful extraction result containing only normalized,
opaque candidate data and exact evidence. The UI can validate the candidate,
but it does not offer a generic assertion action. Repeating the request with
the same project-scoped idempotency key returns the original semantic result
without duplicate source, candidate, or provenance records.

### B. Manual capture, review, and Requirement confirmation

The user captures:

```text
Confirm address before payment. Tax API timeout is 15%.
```

with an exact `requirement` span and `risk` span. The UI previews both spans,
submits the M2 capture, validates the candidates, confirms the requirement, and
rejects the risk with a reason. One asserted Requirement is created and linked
to its candidate and source evidence; rejection creates no asserted item.

### C. Grounded project questions

The user asks:

- “What are the current requirements?”
- “What changed in the checkout requirement?”
- “What is blocking checkout?”

Each question produces only the corresponding released M4 intent. The UI
renders facts, citations, asserted/inferred status, derivations, and freshness.
An unsupported filter, arbitrary query, or question naming another project is
rejected without revealing foreign-project data.

### D. Safety and secret boundary

After saving, rotating, and removing a credential, the credential does not
appear in the settings response, browser storage, rendered DOM after submit,
network response, client bundle, application logs, telemetry, RDF, fixtures, or
review artifacts. A missing or unavailable secret store fails closed.

## Explicit Non-Goals

- Teams, Outlook, Jira, webhooks, polling, OAuth, outbound actions, or connector state.
- Full authentication, RBAC/ABAC administration, tenant management, or production identity selection.
- Candidate confirmation for types other than the released `Requirement` assertion.
- Arbitrary SPARQL, graph browsing, raw RDF/IRI access, storage URLs, or unrestricted search.
- Offline semantic runtime, browser-local graph replication, desktop packaging, or OS keyring integration.
- Note edit/delete, bulk capture, background extraction, or reload recovery beyond released read contracts.
- Ontology, SHACL, inference-rule, or semantic vocabulary changes.

## Source Contracts

- [Quick Note Use Case — M2](quick-note.md)
- [LLM Candidate Extraction Use Case — M3](llm-candidate-extraction.md)
- [Project Context Question — M4](project-context-question.md)
- [Application API Contract](../architecture/application-api.md)
- [Web Experience Capability Matrix](../architecture/web-experience-capability-matrix.md)
- [Semantic Core API Contract](../architecture/semantic-core-api.md)
