# LLM Candidate Extraction Use Case — M3 Executable Boundary

**Status:** IMPLEMENTATION_BASELINE
**Task:** S5-01

## Purpose

This is the Sprint 5 executable boundary for proposing typed knowledge from an
untyped Quick Note. It extends the released M2 capture lifecycle with an
untrusted, provider-neutral extraction step. The result is zero or more
reviewable candidates; it never asserts facts, changes the ontology, or runs
inference.

## Actors and Preconditions

The capture actor is the trusted project member established by the M2
application boundary. Middleware supplies `projectId`, `actorId`, and
`requestId`; the request body supplies only the immutable raw note and an
idempotency key is required. The project context is authorized before any
source text or entity-link context is sent downstream.

The Semantic Core remains the only service allowed to mutate RDF graphs. The
FastAPI orchestration layer may call a finite project-scoped read for bounded
entity-link context and an `LLMGateway`, then submits normalized candidates to
the Core's atomic ingestion operation.

## Canonical Request and Result

```json
{
  "rawText": "The checkout team owns the tax API timeout investigation.",
  "extractionVersion": "sprint-5.v1"
}
```

The server canonicalizes line endings before offsets are calculated. Model
output is parsed into a versioned typed contract containing entity candidates,
relation candidates, optional bounded entity-link proposals, exact half-open
Unicode-code-point evidence spans, confidence, and abstention reasons. IDs,
classes, predicates, and link targets are server-validated allowlisted values;
arbitrary RDF, IRIs, SPARQL, or model-created target IDs are forbidden.

The response returns the existing opaque note identity plus candidate IDs,
status, source evidence references, extraction activity metadata, and request
correlation. It does not return provider payloads or secrets. A valid empty
model result is a successful capture with zero candidates and an explicit
abstention/result reason.

## Main Flow and Graph Diff

1. FastAPI validates trusted context, note size/emptiness, extraction version,
   and idempotency input.
2. The application obtains a bounded set of existing entity IDs, types, and
   labels for the same project; no cross-project data is eligible.
3. The application calls the provider-neutral gateway with the versioned
   schema, prompt package, ontology allowlist, note, and bounded context.
4. The application normalizes ordering and duplicates, recomputes evidence
   text from source offsets, validates types/predicates/links, and classifies
   every failure before persistence.
5. Semantic Core atomically writes the immutable source, candidate entities,
   candidate relations/links, and extraction provenance in the project graphs.
6. The existing validation, review, confirmation/rejection, current-knowledge,
   and evidence-read flows remain the only path to asserted knowledge.

| Graph | Required M3 effect |
|---|---|
| sources | One immutable Note containing the canonical raw text. |
| candidates | Zero or more normalized entity, relation, and link proposals, all project-scoped and reviewable. |
| provenance | Extraction activity with model/provider-neutral ID, model/prompt/schema/ontology versions, usage metadata, and source evidence links. |
| asserted | Unchanged during extraction. |
| inferred | Unchanged during extraction. |

## Idempotency, Atomicity, and Failure Behavior

The idempotency key is scoped to trusted project and canonical request
fingerprint. An identical replay returns the original result without another
semantic write. Reusing a key with different content returns a conflict.

No source, candidate, link, relation, or provenance write is visible if
normalization, allowlist validation, SHACL validation, provider response
handling, or semantic storage fails. Provider timeout, rate limit, missing
credential/model configuration, malformed output, unsupported type/relation,
invalid evidence, hallucinated or cross-project links, and explicit abstention
are classified through the S5 error taxonomy. A provider failure is not
silently converted into a candidate.

Latency and cost are bounded by configured request timeout, retry policy,
maximum note/context size, and provider usage limits. Retries may repeat a
provider invocation before persistence; idempotency guarantees one semantic
outcome, not exactly-once model invocation.

## Acceptance Scenario

Given trusted context for project `ecommerce-checkout`, Le submits the raw note
`The checkout team owns the tax API timeout investigation.` The replay adapter
returns one `Task` candidate with an exact source span and a link proposal only
to a bounded existing project entity. The system stores one source Note, one
candidate, one extraction activity, and the evidence chain; asserted and
inferred graphs remain unchanged. The candidate can be validated and then
confirmed through the existing human-review operation.

The same request replay returns the original opaque IDs without duplicate
graphs. A fixture containing a fabricated target ID, cross-project target,
unsupported predicate, invalid Unicode offsets, prompt-injection text, or
malformed schema produces the corresponding error and leaves all semantic
graphs unchanged. An abstention fixture succeeds with zero candidates and an
abstention reason.

## Explicit Non-Goals

- Auto-confirmation, auto-assertion, auto-rejection, inference, or policy decisions.
- Ontology term creation, arbitrary predicates/IRIs, SPARQL, or graph routing.
- Bulk extraction, background orchestration, note edit/delete, or frontend UI.
- Cross-project entity linking, general entity resolution, retrieval, or answer generation.
- Reproducible live-provider output in canonical CI.
