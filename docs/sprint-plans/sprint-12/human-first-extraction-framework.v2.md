# Sprint 12 Human-First Extraction Framework v2

Status: `REVISED_AND_ACCEPTED_FOR_RM55_CONTRACT_DEFINITION_ONLY`

Source design: [`human-first-extraction-framework.v1.md`](human-first-extraction-framework.v1.md)

Source design digest: `sha256:724e24098b88904c27fde8959eefb12bdd0a8ae1318c14408b3530c183939699`

Dependency: `S12-RM-53` accepted offline custody only

Provider calls: `0`

This revision resolves the kernel policies required by `S12-RM-54`. It is a
design contract for `S12-RM-55` through later owner-gated tasks; it does not
implement code, change the ontology, open a provider, or authorize evaluation.
The v1 source remains unchanged and is the immutable design-input record.

## 1. Adopted kernel and authority boundary

The extraction kernel is source-first, server-anchored, project-scoped and
human-authorized:

- A committed `SourceVersion` is the only coordinate authority. Model output
  may propose a quote, type, opaque handle and context, but may not supply
  trusted offsets, global identity, asserted RDF, tool calls or authorization.
- Candidates, asserted facts, inferred projections and provenance remain
  separate. Only an approved, revision-matched `ApprovedAssertionPlan` may
  atomically materialize asserted facts and provenance.
- Every rejection, abstention, quarantine, edit, approval and materialization
  has a finite state, actor/reviewer authority, source/candidate revision and
  durable receipt.
- Unknown, missing, stale, ambiguous, out-of-source and conflicting evidence
  fail closed. They never become a guessed span, relation or assertion.

The semantic-core boundary remains the authority for project-scoped identity,
ontology-versioned predicates/types, SHACL/provenance validation and asserted
graph mutation. The extraction gateway remains proposal-only. Operational queue
and telemetry details may live outside RDF, but their receipts must bind the
semantic revisions they describe.

## 2. Immutable SourceVersion and receipt policy

`SourceVersion` identifies one immutable logical source artifact in one project:

- A note/document/import payload is one source version; chunks and blocks are
  deterministic derived views and never independent source authorities.
- Required identity is project ID, source artifact ID, source version ID,
  parent/superseded version, capture timestamp, media/encoding metadata,
  original-content digest and canonical-content digest.
- Input bytes are decoded as UTF-8 only after the connector declares an
  encoding. Invalid or undeclared encoding is quarantined; silent replacement
  characters are forbidden.
- Canonicalization preserves Unicode scalar values and does not apply Unicode
  normalization. CRLF and CR become LF only in the canonical view; the
  original digest and newline map remain available for custody and display.
- A source version is committed once, can be superseded only by a new version,
  and cannot be deleted while referenced by a candidate, receipt, assertion,
  provenance activity or inferred revision. Retention periods are owner-gated
  metadata, not a permission to break references.
- A source receipt records the exact source-version ID, both digests,
  canonicalization/coordinate versions, parent lineage, project scope and
  custody status. Telemetry stores receipt IDs and digests, never raw source.

Replay requires the same source-version digest, configuration digest and
idempotency key. A different body under the same key is a conflict.

## 3. Coordinate and TextAnchor contract

Canonical offsets are zero-based, half-open Unicode code-point offsets over the
committed canonical source view. `TextAnchor` requires:

```text
sourceVersionId, start, end, exactQuote, quoteDigest, blockId,
occurrence, coordinateSystemVersion
```

The server owns mappings between original bytes, canonical code points, line
endings and UTF-16 display positions. The UI receives a mapping and never
reinterprets canonical offsets. Emoji, combining marks, CJK, surrogate pairs,
CRLF/LF and chunk base offsets are covered by property tests.

The server searches the exact quote in the declared source version. A unique
match is anchored; repeated matches require block/context/occurrence
resolution; an equally ranked or unresolved match becomes `NEEDS_REVIEW`; a
missing, empty, reversed, out-of-source or stale span becomes quarantined.
There is no offset fallback, quote widening, remapping to a newer source or
model-supplied authority.

## 4. Finite lifecycle and failure dispositions

The following transitions are the only materializable lifecycle transitions:

```text
SourceVersion:
  RECEIVED -> CANONICALIZED -> COMMITTED -> SUPERSEDED
  RECEIVED/CANONICALIZED -> QUARANTINED

Run:
  CREATED -> AUTHORIZED -> PROVIDER_ATTEMPTED -> RESPONSE_CAPTURED
  RESPONSE_CAPTURED -> COMPLETED | PARTIAL | FAILED | QUARANTINED

CandidateRevision:
  PROPOSED -> CONTRACT_VALID -> GROUNDED -> REVIEW_PENDING
  REVIEW_PENDING -> EDITED -> REVIEW_PENDING
  REVIEW_PENDING -> APPROVED | REJECTED | ABSTAINED | QUARANTINED | STALE
  APPROVED -> MATERIALIZED
```

Transitions are append-only and revision-bound. A stale source or candidate
cannot be remapped silently. Per-item invalidity does not discard unrelated
valid items, but every invalid item remains non-materializable until a new
revision passes its guards.

Finite quarantine reasons are:
`INVALID_SOURCE_ENCODING`, `SOURCE_DIGEST_CONFLICT`,
`OUT_OF_SOURCE_SPAN`, `AMBIGUOUS_SPAN`, `MISSING_EVIDENCE`,
`INVALID_CONTRACT`, `UNKNOWN_HANDLE`, `CROSS_PROJECT_HANDLE`,
`STALE_REVISION`, `PROMPT_INJECTION_CONTENT`, `ACCOUNTING_UNKNOWN`, and
`IDEMPOTENCY_CONFLICT`. `ABSTAINED` means the system deliberately produced no
claim; `QUARANTINED` means a safety or custody guard blocks further processing.
Release from quarantine requires an authorized human disposition and a new
revision; no automatic release exists.

## 5. Ontology-versioned identity and relation allowlists

Every candidate carries the active released ontology version and contract
revision. Type and predicate allowlists are resolved server-side from that
version. Model-created global IDs, raw IRIs, free-text predicates and labels
cannot cross the boundary.

Entity handles are opaque, project-scoped and server-resolved. A relation may
use only confirmed handles from the same project and active source version.
Cross-project relations are denied by default; any future exception requires a
separate owner decision, explicit allowlist entry, project authorization and
dedicated tests. Unknown handles, stale confirmations, self-relations,
unsupported direction, polarity, modality or temporal qualifiers remain
pending, abstained or quarantined.

This gate makes no ontology production change and releases no new ontology
term. If later contracts require new semantic terms, the ontology-evolution
workflow must provide competency questions, SHACL/rule impacts, migration,
versioning and human approval before release.

## 6. Deterministic evidence and relation boundary

Evidence is selected only from server-owned source blocks and confirmed
endpoint/trigger anchors. The deterministic rule is the smallest source clause
that contains the required endpoints and trigger; sentence/block boundaries
are used only when the clause index cannot establish containment.

If evidence is missing, out of source, stale, ambiguous or equally ranked, the
item receives an explicit review/abstain/quarantine disposition. The system
never generates, guesses, widens or substitutes evidence. Relation predicates,
direction, endpoint scope, polarity, modality, temporal qualifiers and evidence
status are validated before review and again before materialization.

## 7. Reviewer authority and decision receipts

Human confirmation, edit, rejection and abstention require an authenticated
reviewer role authorized for the project and decision type. Quarantine release
requires the designated release role; no model, queue default or service
account may impersonate that action. Relation approval always requires explicit
human action. Hidden auto-confirmation and bulk relation approval are
prohibited.

Each append-only receipt contains actor/role, project, source-version ID,
candidate ID and revision, action, normalized decision body, decision digest,
ontology/contract versions, timestamp, expected graph revision and
idempotency key. A stale expected revision fails without mutation. Replaying
the same key with the same body is idempotent; the same key with a different
body is an `IDEMPOTENCY_CONFLICT` and cannot overwrite history.

## 8. ApprovedAssertionPlan and recovery

The only assertion input is:

```text
ApprovedAssertionPlan {
  sourceVersionId
  approvedCandidateRevisions[]
  reviewerDecisionDigests[]
  expectedAssertedGraphRevision
  ontologyVersion
  provenanceActivityId
  idempotencyKey
}
```

Before commit, every candidate must be approved, revision-matched, non-stale,
allowlisted, SHACL-valid, provenance-complete and body-matched to its receipt;
the expected asserted revision must match. One transaction writes asserted
facts, provenance, review receipts and materialization revision together.

On conflict or partial failure, the transaction is retried by idempotency or
left visibly pending for recovery. Asserted truth is never rolled back into
candidate or inferred state, and no partially acknowledged plan is silently
replayed. Inference runs only from asserted data.

## 9. Inference invalidation and telemetry

Inferred projections bind asserted revision, source-version revision, ontology
version and rule revision. Correction, rejection, supersession or retraction
marks dependent projections stale before rebuild. A failed rebuild preserves
asserted truth and publishes no stale inference as current.

Telemetry contains allowlisted lifecycle IDs, receipt/decision digests,
revision IDs, reason codes, timing, conflicts, outcomes and accounting status.
It excludes raw source text, secrets, provider payloads, sensitive identifiers,
prompt contents and self-asserted reconciliation flags. Retention is
owner-configurable metadata, with a default sufficient for custody/audit and
deletion blocked while a receipt is required by an active evidence chain.
Unknown accounting remains `null`/unknown rather than zero.

## 10. Human-study deferral

Human-study sample size, reviewer roles, languages, manual baseline, blinding or
counterbalancing, correction taxonomy, thresholds and abort rules are
explicitly deferred to `S12-RM-67` and `S12-RM-68`. This design records no
human-study result and makes no business-quality, tenant-readiness or human-
evidence claim. Model metrics and offline tests cannot substitute for that
evidence.

## 11. Prompt injection and tool authority

Source text, quotes, labels and model output are data, never instructions.
Prompt-injection content is retained only as a finite quarantine reason and
cannot invoke tools, change project scope, alter policy, authorize a reviewer,
or write asserted data. Tool authority remains server-side and separately
authorized; the model has no direct SPARQL, filesystem, provider or graph-write
authority.

## 12. Explicit non-goals and next gate

This RM-54 disposition does not authorize:

- provider reopening, runtime execution, rerun, retry or implementation;
- auto-approval, hidden confirmation or bulk relation approval;
- a production ontology change or ontology release;
- validation data, held-out data, Stage B, candidate selection or promotion;
- release, deployment, tenant readiness or business-quality claims;
- completion of RM-55 through RM-68.

The sole next action is `S12-RM-55`, definition of the immutable
`SourceVersion` and source-receipt contract. Subsequent implementation and
evaluation remain separately gated by the Sprint plan and owner decisions.
