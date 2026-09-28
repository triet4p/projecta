# Evidence-first Assisted Authoring v1

Status: `IMPLEMENTED_REVIEWED_OFFLINE_EVALUATION_DEFERRED`

This contract makes evidence-first assisted authoring the active successor to
Sprint 12. It does not reopen provider execution, RM-68 external validation,
the frozen dense-hard packets, R6 fresh benchmark design, or R7 independent
evaluation.

## 1. Product direction

Projecta is a human-authored structured capture tool. The default path is:

```text
Human task/question or structured note
→ scoped retrieval/evidence
→ human selects/confirms occurrence/entity
→ server resolves SourceVersion + TextAnchor + opaque identity
→ optional one bounded local AI suggestion
→ explicit human confirm/edit/reject + append-only receipt
→ approved-only assertion materialization
→ inference and projections
```

There is no automatic whole-document graph extraction. Retrieval supplies
context, not authoritative facts. AI is a proposal-only copilot, invoked only
when requested or needed by an allowed workflow.

## 2. Roles and authority

| Role | May do | May not do |
|---|---|---|
| Human author/reviewer | Create note/question, select occurrence, confirm/edit/reject, approve an assertion | Bypass project/tenant policy or provenance requirements |
| Deterministic server | Resolve source revisions, anchors, opaque handles, allowlists, evidence, receipts, budgets, materialization and inference | Invent semantic content or silently approve |
| Retrieval layer | Return project-scoped textual/graph context and candidate matches | Create facts, relations or identity |
| Local AI model | Propose one bounded item/type/link/relation from supplied context | Create global IDs/offsets, call providers in background, approve, bulk-extract or write graph |
| Semantic core | Validate SHACL/lifecycle, materialize approved plans and rebuild inference | Treat candidate/retrieval output as asserted truth |

Relations require two distinct same-project manual captures that are currently
validated and confirmed by receipts matching each current candidate revision,
SourceVersion and TextAnchor. Both endpoints must share the same current
SourceVersion. The reviewer chooses the endpoint pair and direction. Manual
mode uses an explicit allowlisted predicate without a model call; local mode
may return only one allowlisted predicate or abstain. The server derives
endpoint identity, relation identity, and deterministic source-block evidence
from the current anchors and receipts. Model output cannot author endpoint
identity, direction, evidence, offsets or approval. Confirm and reject append a
relation review receipt only; neither decision materializes a graph relation.
## 3. Interaction states

```text
DRAFT_NOTE
→ EVIDENCE_CONTEXT_READY
→ OCCURRENCE_SELECTED
→ ENTITY_CONFIRMED
→ [OPTIONAL SUGGESTION_REQUESTED]
→ SUGGESTION_PRESENTED | MANUAL_CAPTURE_READY
→ HUMAN_DECISION_RECORDED
→ APPROVED_PLAN_READY
→ ASSERTED_MATERIALIZED
→ INFERENCE_REFRESHED
```

Every state transition is project-scoped and auditable. A user can stop at
`MANUAL_CAPTURE_READY`, reject a suggestion, or continue without any model
call. Failed anchor, identity, policy, evidence, budget or validation checks
fail closed and leave no asserted or inferred write.

## 4. Server/model boundary

The server owns SourceVersion, Unicode coordinates, TextAnchor, project scope,
opaque identity, relation endpoint validity, evidence selection, predicate and
direction allowlists, review receipts, budget accounting and approved-only
materialization. Model output is an untrusted proposal envelope. The server
normalizes and validates it; the human decides its semantic meaning.

The server must reject model-authored global IDs and offsets, cross-project
handles, unsupported predicates, endpoint swaps, missing evidence, malformed
propositions and any attempt to finalize without a receipt.

## 5. Cost and privacy boundary

- Deterministic capture and scoped retrieval run before a model call.
- At most one bounded suggestion is requested per user workflow step unless a
  separately approved workflow contract says otherwise.
- Cache and deduplicate by source, item and revision; explicit retry is still
  subject to budget and policy.
- Enforce per-user and per-project budgets, with a visible remaining budget.
- Record cost as local inference-attempt counts, never currency or token estimates.
  A distinct, non-replayed local request and an actual local gateway attempt are
  reported separately; cached replays do not add usage. Manual-only workflows
  report zero model attempts.
- Append raw-content-free events to the application operational SQLite database.
  Events retain only project, actor, workflow, attempt, receipt and assertion
  digests, finite correction dimensions/categories, counts and bounded timing.
  They never retain source text, prompts, provider payloads, model IDs, secrets,
  credentials, free-form reasons or correction values.
- Manual-edit `semanticEditCount` counts each submitted correction field,
  including date; `correctionEventCount` includes the full manual-edit event.
  Correction categories use only recognized RM-65 dimensions and RM-67
  precedence: type, predicate, endpoint or evidence is `major`; span or label is
  `minor`. A field without an RM-65 dimension contributes its edit count but
  not a category. Therefore, a date-only manual edit contributes to both edit
  metrics but has no category; a date field in a composite edit does not
  suppress the category from its recognized dimensions. Reviews without a
  semantic/evidence correction remain `unchanged`. No date or correction value
  is stored in telemetry.
- **Owner amendment (2026-09-28; provenance:** `.agents/memory/decisions.md`,
  “Accept S13-05 telemetry denominators and date classification”): the owner
  accepted the current §5 metrics. The mean local-attempt cost is null when
  there are no cost-known accepted assertions; review-latency samples require
  a recorded workflow start and durable receipt time, and a missing start is
  excluded rather than imputed. The decision also confirms the field-level
  date exclusion above; RM-67 precedence still applies to recognized
  dimensions in composite edits. These descriptive metrics are not RM-67 study
  denominators or results.
- Expose these project- and actor-scoped metrics at
  `GET /v1/projects/{handle}/authoring-metrics`. No provider execution is part
  of this sprint; zero-model manual mode remains a supported product path.

## 6. Reuse of accepted Sprint 12 contracts

Sprint 13 reuses, rather than weakens, the accepted RM-55--RM-65 boundaries:

| Contract | Sprint 13 use |
|---|---|
| RM-55 SourceVersion/source receipt | Bind every capture to immutable source revision |
| RM-56 TextAnchor | Server-owned Unicode anchor and revision validation |
| RM-57 per-item validation/quarantine | Fail closed on malformed or unsupported suggestion |
| RM-58 confirmed-entity relation gate | Entity-first endpoint confirmation |
| RM-59 deterministic evidence selection | Evidence for relation/proposition is server-selected |
| RM-60 constrained relation | Allowlisted predicate/direction and same-project scope |
| RM-61 append-only review receipts | Explicit human decision and replay/idempotency |
| RM-62 source-first review workbench | Human sees source and evidence before decision |
| RM-63 approved-only materialization | Candidate never becomes asserted implicitly |
| RM-64 invalidation/rebuild | Revision changes invalidate stale current projection |
| RM-65 correction telemetry | Measure corrections without raw data leakage |

RM-66 adversarial/default-path tests and RM-67 closed-world burden definitions
remain safety and measurement constraints. They do not authorize an evaluation
or a provider call.

## 7. Explicit non-goals and locks

- No automatic whole-document extraction or background provider calls.
- No model-authored offsets, global IDs, hidden confirmation or bulk relation
  approval.
- No unreviewed candidate/assertion/inference materialization.
- No ontology production changes; use `$projecta-evolve-ontology` separately.
- No R6 fresh benchmark, R7 independent evaluation, human study, business
  acceptance, held-out access, RM-68 issuance, provider execution, selection,
  promotion or release.
- Dense-hard v1--v4 and v5 easy baseline remain immutable historical evidence;
  they are not pooled, retuned or relabeled by this contract.

## 8. Go/no-go gates

Implementation can proceed through the first vertical slice only when:

- Manual capture succeeds with zero model calls.
- No suggestion can reach asserted or inferred memory without a valid receipt
  and approved assertion plan.
- Invalid/stale/cross-project anchors and endpoint swaps fail closed.
- Relation proposals require confirmed same-project endpoints, deterministic
  evidence and allowlisted predicate/direction.
- Budget, cache/dedup and cost-per-accepted-assertion telemetry are observable
  without raw data.
- RM55--RM66 regression and adversarial tests remain green.

Any later offline evaluation requires a separate owner decision. If authorized,
the RM-67 targets remain the reference: at least 70% unchanged, at least 85%
unchanged-or-minor, mean edits at most 2, median review at most 45 seconds,
and at least 30% faster than a manual baseline, with zero unsafe or unsupported
finalized assertions. These are gates, not current claims.

## 9. Dense-hard R1--R5 mapping

| Historical remediation item | Evidence-first implementation response |
|---|---|
| R1 occurrence coverage | Human selects occurrence; server binds every occurrence to a revisioned anchor and opaque handle |
| R2 relation grounding | Relation-on-demand after confirmed endpoints, deterministic evidence and constrained predicate/direction |
| R3 proposition routing | One bounded suggestion with per-item validation, quarantine and explicit receipt |
| R4 utility/safety routing | Manual path is always available; suggestion is optional and cannot force abstention or finalization |
| R5 candidate contract tests | Mutation/adversarial tests cover duplicate occurrences, endpoint swaps, stale anchors, quarantine and unsupported finalization |

R1--R5 are design/implementation guidance only. R6 and R7 remain closed and
are not tasks in Sprint 13 unless separately authorized.
