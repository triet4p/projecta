# Competency Questions — Knowledge Lifecycle (Sprint 2)

## Purpose

This document defines the competency questions that the Sprint 2 ontology (v0.2) must answer for the Knowledge Lifecycle slice. Each question has a stable identifier, a natural-language formulation, and an expected answer shape.

These questions drive the v0.2 term inventory (S2-07), vocabulary implementation (S2-09), named-graph contracts (S2-10), SHACL shapes (S2-11–S2-14), and SPARQL query implementation (S2-15).

## Scope

All questions are scoped to the Knowledge Lifecycle use case defined in [docs/use-cases/knowledge-lifecycle.md](../../docs/use-cases/knowledge-lifecycle.md). Questions about API endpoints, UI workflows, LLM extraction logic, connector-specific activities, or automated inference rules (beyond what deterministic business rules require) are deferred to Sprint 3+.

The questions reuse the Sprint 1 demo scenario: BrSE Le, project "Ecommerce Checkout Redesign," and the six NoteItems from the 2026-07-28 sprint review note.

---

## Knowledge Status (Lifecycle States)

### CQ-LC-001 — Current status of a candidate

**Question:** Candidate C đang ở trạng thái lifecycle nào?

**Expected answer shape:**

| Variable | Type | Description |
|---|---|---|
| `?candidateStatus` | IRI | Current lifecycle state (`Extracted`, `Validated`, `PendingReview`, `Confirmed`, `Rejected`) |

**Example mapping:** The candidate `:req-address-confirmation-candidate` initially returns `projecta:extracted`, then `projecta:confirmed` after Le's review.

### CQ-LC-002 — All candidates in a given lifecycle state within a project

**Question:** Những candidate nào trong project P đang ở trạng thái S?

**Expected answer shape:**

| Variable | Type | Description |
|---|---|---|
| `?candidate` | IRI | Candidate identifier |
| `?candidateStatus` | IRI | The lifecycle state |
| `?sourceNoteItem` | IRI | The source NoteItem this candidate was derived from |
| `?recordedAt` | xsd:dateTime | When the candidate was extracted |

**Example mapping:** Filtering by `projecta:pending-review` in "Ecommerce Checkout Redesign" returns all candidates awaiting human review.

### CQ-LC-003 — Full lifecycle history of a candidate

**Question:** Candidate C đã trải qua những trạng thái lifecycle nào, theo thứ tự thời gian?

**Expected answer shape:**

| Variable | Type | Description |
|---|---|---|
| `?activityType` | IRI | Type of transition activity |
| `?fromState` | IRI | State before the transition |
| `?toState` | IRI | State after the transition |
| `?agent` | IRI | Agent who performed the transition |
| `?transitionTime` | xsd:dateTime | When the transition occurred |

**Example mapping:** `:req-address-confirmation-candidate` shows: Extracted at 2026-07-29T09:00 (by extraction activity), Validated at 2026-07-29T09:01 (by validation activity), PendingReview at 2026-07-29T09:01, Confirmed at 2026-07-29T10:15 (by Le).

**Note:** This question exercises temporal history without overwrite — every transition is a separate provenance activity; the answer is reconstructed from the provenance graph, not by reading a single mutable status field.

---

## Evidence and Source Traceability

### CQ-EV-001 — Source evidence for a candidate

**Question:** Candidate C được trích xuất từ nguồn nào, ai là tác giả của nguồn đó?

**Expected answer shape:**

| Variable | Type | Description |
|---|---|---|
| `?sourceNoteItem` | IRI | The source NoteItem |
| `?sourceContentText` | xsd:string | Content of the source NoteItem |
| `?sourceType` | IRI | The NoteItemType (e.g., requirement, decision) |
| `?sourceNote` | IRI | The parent Note |
| `?sourceAuthor` | IRI | The original author of the Note |
| `?sourceAuthorName` | xsd:string | Display name of the author |
| `?sourceRecordedAt` | xsd:dateTime | When the source was captured |

**Example mapping:** Candidate `:req-address-confirmation-candidate` traces back to the NoteItem about address confirmation, in the sprint review note authored by Le on 2026-07-28.

### CQ-EV-002 — Full provenance chain from asserted fact to source

**Question:** Fact F trong asserted graph có thể truy ngược về nguồn gốc ban đầu như thế nào (qua những candidate, extraction activity và source NoteItem nào)?

**Expected answer shape:**

| Variable | Type | Description |
|---|---|---|
| `?sourceNoteItem` | IRI | The original source NoteItem |
| `?candidate` | IRI | The intermediate candidate |
| `?extractionActivity` | IRI | The activity that generated the candidate |
| `?generator` | xsd:string | The extraction model or tool |
| `?reviewer` | IRI | The human who confirmed the candidate |
| `?assertionActivity` | IRI | The activity that promoted to asserted |
| `?assertionTime` | xsd:dateTime | When assertion occurred |

**Example mapping:** The asserted requirement `:req-address-confirmation` chains back through the candidate `:req-address-confirmation-candidate`, extraction activity `:extraction-activity-20260729-001`, to the source NoteItem. The reviewer is Le.

### CQ-EV-003 — Generator identity for a candidate

**Question:** Candidate C được tạo bởi công cụ hoặc model nào, phiên bản nào?

**Expected answer shape:**

| Variable | Type | Description |
|---|---|---|
| `?generator` | xsd:string | Identifier of the extraction model or tool |
| `?proposedOntologyVersion` | xsd:string | Ontology version under which the candidate was proposed |

**Example mapping:** Candidate `:req-address-confirmation-candidate` returns generator `projecta-extractor-v0.2.0` and proposed ontology version `0.2.0`.

---

## Reviewer and Review Decision

### CQ-REV-001 — Review decision for a candidate

**Question:** Ai đã review candidate C, quyết định là gì, và khi nào?

**Expected answer shape:**

| Variable | Type | Description |
|---|---|---|
| `?reviewer` | IRI | Person who performed the review |
| `?reviewerName` | xsd:string | Display name of the reviewer |
| `?reviewDecision` | IRI | `projecta:confirmed` or `projecta:rejected` |
| `?reviewTime` | xsd:dateTime | When the review occurred |

**Example mapping:** For candidate `:req-address-confirmation-candidate`, reviewer is Le, decision is confirmed, time is 2026-07-29T10:15:00Z.

### CQ-REV-002 — Rejection reason for a rejected candidate

**Question:** Tại sao candidate C bị từ chối?

**Expected answer shape:**

| Variable | Type | Description |
|---|---|---|
| `?rejectionReason` | xsd:string | Explanation of why the candidate was rejected |
| `?reviewer` | IRI | Person who rejected the candidate |
| `?reviewTime` | xsd:dateTime | When the rejection occurred |

**Example mapping:** A candidate extracted from a task-type NoteItem that was incorrectly classified as a Requirement would be rejected with reason "NoteItem type 'task' does not support extraction as Requirement."

### CQ-REV-003 — All review decisions made by a specific reviewer

**Question:** Người R đã thực hiện những review decision nào trong project P?

**Expected answer shape:**

| Variable | Type | Description |
|---|---|---|
| `?candidate` | IRI | The candidate reviewed |
| `?reviewDecision` | IRI | `confirmed` or `rejected` |
| `?reviewTime` | xsd:dateTime | When the review occurred |

**Example mapping:** Filtering by Le in "Ecommerce Checkout Redesign" returns all candidates Le reviewed, with their decisions and timestamps.

---

## Current and Historical View (Temporal Queries)

### CQ-TEMP-001 — Current asserted facts derived from a project's sources

**Question:** Những fact nào hiện đang có hiệu lực trong asserted graph của project P (không bao gồm fact đã bị supersede hoặc retract)?

**Expected answer shape:**

| Variable | Type | Description |
|---|---|---|
| `?assertedFact` | IRI | The asserted fact |
| `?factType` | IRI | The rdf:type of the fact (e.g., projecta:Requirement) |
| `?factLabel` | xsd:string | Human-readable label |
| `?validFrom` | xsd:date | When the fact became valid |
| `?sourceCandidate` | IRI | The candidate this fact was promoted from |

**Example mapping:** Query returns `:req-address-confirmation` as a Requirement with validFrom 2026-07-29, but does NOT return any superseded or retracted facts.

### CQ-TEMP-002 — Historical view of an asserted fact's lifecycle

**Question:** Fact F đã trải qua những thay đổi gì từ khi được assert (bao gồm supersession, retraction, và các lần review trước đó)?

**Expected answer shape:**

| Variable | Type | Description |
|---|---|---|
| `?activity` | IRI | The provenance activity |
| `?activityType` | IRI | Type of activity (extraction, review, assertion, supersession, retraction) |
| `?agent` | IRI | Agent associated with the activity |
| `?activityTime` | xsd:dateTime | When the activity occurred |
| `?description` | xsd:string | Human-readable description |

**Example mapping:** A fact that was asserted then later superseded returns: assertion activity (by Le, 2026-07-29), supersession activity (by reviewer, later date), with the superseding fact reference.

**Note:** This question explicitly validates that historical data is not overwritten — all activities are queryable as distinct provenance records.

### CQ-TEMP-003 — Facts that were superseded within a time window

**Question:** Những fact nào trong project P đã bị supersede trong khoảng thời gian từ T1 đến T2?

**Expected answer shape:**

| Variable | Type | Description |
|---|---|---|
| `?supersededFact` | IRI | The fact that was superseded |
| `?supersededAt` | xsd:dateTime | When supersession occurred |
| `?supersededBy` | IRI | The fact that replaced it |
| `?supersedingAgent` | IRI | Who performed the supersession |

**Example mapping:** Querying 2026-08-01 to 2026-09-01 returns facts superseded in August, with their replacements and responsible agents.

### CQ-TEMP-004 — Temporal validity interval of an asserted fact

**Question:** Fact F có hiệu lực trong khoảng thời gian nào (`validFrom` đến `validTo`)?

**Expected answer shape:**

| Variable | Type | Description |
|---|---|---|
| `?validFrom` | xsd:date | Start of validity (may be absent if not yet set) |
| `?validTo` | xsd:date | End of validity (absent if still current) |
| `?isCurrent` | xsd:boolean | Derived: true if validTo is unset or in the future |

**Example mapping:** A current requirement (not yet superseded) returns its `validFrom` date and no `validTo`, with `isCurrent = true`.

---

## Graph Isolation

### CQ-ISO-001 — Detect candidates in the asserted graph

**Question:** Có candidate nào bị đặt nhầm vào asserted graph không?

**Expected answer shape:**

| Variable | Type | Description |
|---|---|---|
| — | xsd:boolean | ASK query result |

**Expected value:** `false` — no `projecta:Candidate` instances should appear in any asserted named graph.

### CQ-ISO-002 — Detect asserted facts in the candidates graph

**Question:** Có fact nào đã được assert nhưng vẫn nằm trong candidates graph không?

**Expected answer shape:**

| Variable | Type | Description |
|---|---|---|
| — | xsd:boolean | ASK query result |

**Expected value:** `false` — entities that are the object of an assertion activity should not remain in a candidates graph.

### CQ-ISO-003 — Verify provenance graph contains all lifecycle transitions

**Question:** Mọi candidate có trạng thái ngoài `Extracted` có bản ghi provenance activity cho transition đó không?

**Expected answer shape:**

| Variable | Type | Description |
|---|---|---|
| `?candidate` | IRI | Candidate with a non-initial state |
| `?currentState` | IRI | Current lifecycle state |
| `?lastActivity` | IRI | The most recent provenance activity for this candidate |
| `?missingTransition` | xsd:boolean | True if a state transition has no corresponding activity |

**Example mapping:** A candidate in `Confirmed` state must have at least one review activity. A candidate that somehow reached `Confirmed` without a corresponding `prov:Activity` in the provenance graph is flagged.

---

## Project Scope

### CQ-SCOPE-001 — All lifecycle entities belonging to a project

**Question:** Những entity lifecycle nào (candidate, asserted fact, activity) thuộc về project P?

**Expected answer shape:**

| Variable | Type | Description |
|---|---|---|
| `?entity` | IRI | Entity identifier |
| `?entityType` | IRI | rdf:type of the entity |
| `?entityGraph` | IRI | Named graph the entity resides in (candidates, asserted, provenance) |

**Example mapping:** For "Ecommerce Checkout Redesign," returns all candidates, asserted facts, and provenance activities scoped to that project, each with its graph location.

### CQ-SCOPE-002 — Detect lifecycle entities without project assignment

**Question:** Có candidate, asserted fact, hoặc provenance activity nào không có `belongsToProject` không?

**Expected answer shape:**

| Variable | Type | Description |
|---|---|---|
| — | xsd:boolean | ASK query result |

**Expected value:** `false` — every lifecycle entity must have a `belongsToProject` relationship.

### CQ-SCOPE-003 — Detect cross-project provenance without authorization

**Question:** Có quan hệ `prov:wasDerivedFrom` nào nối entity thuộc project A với entity thuộc project B không?

**Expected answer shape:**

| Variable | Type | Description |
|---|---|---|
| `?sourceEntity` | IRI | Source entity (in project A) |
| `?sourceProject` | IRI | Project of the source |
| `?targetEntity` | IRI | Target entity (in project B) |
| `?targetProject` | IRI | Project of the target |

**Example mapping:** An empty result set in the normal case. If a candidate in "Ecommerce Checkout Redesign" derived from a NoteItem in "Payment Platform Modernization," this query surfaces the violation.

---

## Summary

| ID | Short Description | Query Type | Category |
|---|---|---|---|
| CQ-LC-001 | Current status of a candidate | SELECT | Knowledge Status |
| CQ-LC-002 | Candidates in a given lifecycle state | SELECT | Knowledge Status |
| CQ-LC-003 | Full lifecycle history of a candidate | SELECT | Knowledge Status |
| CQ-EV-001 | Source evidence for a candidate | SELECT | Evidence |
| CQ-EV-002 | Full provenance chain to source | SELECT | Evidence |
| CQ-EV-003 | Generator identity for a candidate | SELECT | Evidence |
| CQ-REV-001 | Review decision for a candidate | SELECT | Reviewer |
| CQ-REV-002 | Rejection reason for a candidate | SELECT | Reviewer |
| CQ-REV-003 | All reviews by a specific reviewer | SELECT | Reviewer |
| CQ-TEMP-001 | Current asserted facts (no superseded/retracted) | SELECT | Temporal |
| CQ-TEMP-002 | Historical view of a fact's lifecycle | SELECT | Temporal |
| CQ-TEMP-003 | Facts superseded within a time window | SELECT | Temporal |
| CQ-TEMP-004 | Temporal validity interval of a fact | SELECT | Temporal |
| CQ-ISO-001 | Candidates in asserted graph | ASK | Graph Isolation |
| CQ-ISO-002 | Asserted facts in candidates graph | ASK | Graph Isolation |
| CQ-ISO-003 | Missing provenance for state transitions | SELECT | Graph Isolation |
| CQ-SCOPE-001 | All lifecycle entities in a project | SELECT | Project Scope |
| CQ-SCOPE-002 | Lifecycle entities without project | ASK | Project Scope |
| CQ-SCOPE-003 | Cross-project provenance violations | SELECT | Project Scope |

**Total:** 19 competency questions across 5 categories.

---

## Deferred Questions

The following question patterns were considered but are explicitly deferred because they require capabilities outside Sprint 2 scope:

| Question Pattern | Why Deferred | Relevant Sprint |
|---|---|---|
| "Which candidates were extracted by LLM model M vs model N?" | Requires multiple extraction models to compare; Sprint 2 models one extraction path | Sprint 3+ |
| "Show me the confirmation UI state for candidate C" | UI state is not an ontology concern | Sprint 3+ |
| "Automatically promote all confirmed candidates to asserted" | Runtime promotion logic is Semantic Core API concern | Sprint 3 |
| "Which candidates should I review next?" (ranked) | Requires priority/ranking logic not in ontology | Sprint 4+ |
| "How many candidates were automatically vs manually extracted?" | Requires connector and extraction execution tracking | Sprint 3+ |
| "What inference rules were triggered by asserting fact F?" | Inference rule execution tracking; S2-17 only analyzes scope | Sprint 3+ |
