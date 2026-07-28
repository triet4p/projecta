# Knowledge Lifecycle Use Case — Slice Boundary

## 1. Purpose

This document defines the precise boundary of the Knowledge Lifecycle use case for Sprint 2. It traces the path from a Sprint 1 `NoteItem` through candidate extraction, human review decision, and final assertion. It serves as the authoritative reference for lifecycle competency questions (S2-02), term inventory (S2-07), vocabulary implementation (S2-09), named-graph contracts (S2-10), and SHACL shapes (S2-11–S2-14).

## 2. Use Case: Knowledge Lifecycle

### 2.1. Actor

- BrSE (primary — captures notes, reviews candidates, confirms assertions).
- Project Coordinator (reviews candidates, confirms assertions).
- Technical Business Analyst (reviews candidates, confirms assertions).
- Tech Lead (confirms or rejects technical decisions).

Only actors who are members of the target project may participate in the lifecycle for that project's knowledge.

### 2.2. Trigger

A `NoteItem` exists in the project's **sources graph** (created in Sprint 1). The system or a human reviewer initiates the lifecycle to transform this raw evidentiary record into governed, asserted knowledge.

### 2.3. Preconditions

- The `NoteItem` belongs to a `Note` that is project-scoped via `belongsToProject`.
- The `NoteItem` has complete provenance: `authoredBy` (the capturing person), `recordedAt` (timestamp), and `contentText`.
- The `NoteItem` has an `hasItemType` classification from the Sprint 1 controlled vocabulary (`requirement`, `decision`, `question`, `task`, `risk`, `assumption`, `constraint`, `progress-update`, `research-need`).
- The project has a designated **sources**, **candidates**, **asserted**, **inferred**, and **provenance** named graph (even if some are empty).
- The actor has permission to review and confirm candidates in that project.

### 2.4. Main Flow

1. **Source identification:** The system or actor selects a specific `NoteItem` as the evidentiary source for a candidate knowledge item.
2. **Candidate extraction:** The system creates a **candidate entity** in the project's **candidates graph**:
   - The candidate has a `prov:wasDerivedFrom` link to the source `NoteItem`.
   - The candidate has a `prov:wasGeneratedBy` link to the extraction activity.
   - The candidate records the generator (model identifier for automated extraction, or actor identity for manual extraction).
   - The candidate has a proposed ontology version (`projecta:proposedOntologyVersion`).
   - The candidate has a verification state initialized to `Extracted`.
   - The candidate has a timestamp (`prov:generatedAtTime`).
3. **Candidate validation:** The candidate is validated against applicable SHACL shapes:
   - Source evidence shape: verifies the candidate has a valid source reference, generator, and timestamp.
   - Candidate evidence shape: verifies the candidate is NOT placed in the asserted graph.
4. **Review decision:** A human reviewer examines the candidate:
   - **Confirm:** The candidate transitions from `PendingReview` to `Confirmed`.
   - **Reject:** The candidate transitions from `PendingReview` to `Rejected`, with a rejection reason recorded.
5. **Assertion promotion:** A confirmed candidate is promoted to the project's **asserted graph**:
   - The asserted entity is a distinct instance (the candidate is not moved or retyped; a new asserted entity is created).
   - The asserted entity has `prov:wasDerivedFrom` linking back to the candidate.
   - The asserted entity has `prov:wasAttributedTo` the confirming reviewer.
   - The assertion activity is recorded in the **provenance graph** with `prov:Activity`, agent, timestamp, and the `Confirmed → Asserted` transition.
6. **Provenance recording:** Every lifecycle transition (`Extracted → Validated → PendingReview → Confirmed → Asserted`) is recorded as a `prov:Activity` in the provenance graph with:
   - The agent who performed the transition.
   - The timestamp of the transition.
   - The before-state and after-state.
   - The project scope.

### 2.5. Postconditions

- A candidate entity exists in the project's **candidates graph** with full provenance back to the source `NoteItem`.
- If confirmed, an asserted entity exists in the project's **asserted graph** with provenance back to the candidate and the reviewer.
- Every lifecycle transition is recorded in the **provenance graph**.
- The source `NoteItem` in the **sources graph** is unchanged — the lifecycle adds facts without mutating the original evidence.
- The candidate remains in the candidates graph (not deleted or moved) and references the asserted fact, preserving the audit trail.
- If rejected, the candidate stays in the candidates graph with status `Rejected` and a rejection reason.
- Graph isolation holds: candidates are never in the asserted graph, asserted facts are never in the candidates graph, and provenance is always in the provenance graph.
- Temporal history is preserved: no existing triple is overwritten. State transitions are recorded as new provenance activities, not by mutating the candidate's status property.

### 2.6. Alternative Flows

- **Re-extraction from the same source:** A new candidate may be created from the same `NoteItem` if the previous candidate was rejected or if new extraction logic is applied. Each extraction is a separate candidate with its own provenance.
- **Supersession:** An asserted fact may be superseded by a new asserted fact. The original fact's `validTo` is set, and the new fact references it via `prov:wasDerivedFrom`. The old fact remains in the asserted graph — it is not deleted.
- **Retraction:** An asserted fact may be retracted if found to be incorrect. Retraction is recorded as a provenance activity; the retracted fact remains in the asserted graph with status `Retracted` and a retraction reason.
- **Cross-project candidate:** A candidate derived from a note in project A cannot be asserted in project B unless an explicit cross-project authorization exists.
- **Batch review:** A reviewer may confirm or reject multiple candidates in a single review session. Each candidate transition is a separate provenance activity, but they share a review session identifier.

## 3. Positive Example

### 3.1. Scenario

Continuing from the Sprint 1 positive example: BrSE Le captured six note items during the "Ecommerce Checkout Redesign" sprint review meeting on 2026-07-28. One of them was:

> Khách hàng yêu cầu thêm bước xác nhận địa chỉ trước khi thanh toán. Cần làm rõ: có bắt buộc với KH đã lưu địa chỉ không? [Requirement]

The system now processes this `NoteItem` through the knowledge lifecycle.

### 3.2. Step-by-Step Walkthrough

#### Step 1: Source Identification

The source is the Sprint 1 `NoteItem`:

| Property | Value |
|---|---|
| `rdf:type` | `projecta:NoteItem` |
| `projecta:contentText` | "Khách hàng yêu cầu thêm bước xác nhận địa chỉ trước khi thanh toán. Cần làm rõ: có bắt buộc với KH đã lưu địa chỉ không?" |
| `projecta:hasItemType` | `projecta:requirement` |
| `projecta:isItemOf` | `:note-sprint-review-20260728` |
| `projecta:belongsToProject` | `:project-ecommerce-checkout-redesign` |
| `projecta:authoredBy` | `:person-le` |
| `projecta:recordedAt` | `2026-07-28T14:30:00Z` |

#### Step 2: Candidate Extraction

The system creates a candidate in `/project/ecommerce-checkout-redesign/candidates`:

```turtle
:req-address-confirmation-candidate
    a projecta:Candidate ;
    projecta:candidateStatus projecta:extracted ;
    projecta:proposedOntologyVersion "0.2.0" ;
    projecta:hasSourceEvidence :req-address-confirmation-evidence ;
    prov:wasDerivedFrom :noteitem-sprint-review-address-confirmation ;
    prov:wasGeneratedBy :extraction-activity-20260729-001 ;
    prov:generatedAtTime "2026-07-29T09:00:00Z"^^xsd:dateTime ;
    projecta:belongsToProject :project-ecommerce-checkout-redesign .
```

The extraction activity in provenance:

```turtle
:extraction-activity-20260729-001
    a prov:Activity ;
    rdfs:label "Candidate extraction from NoteItem" ;
    prov:used :noteitem-sprint-review-address-confirmation ;
    prov:generated :req-address-confirmation-candidate ;
    projecta:generator "projecta-extractor-v0.2.0" ;
    prov:endedAtTime "2026-07-29T09:00:00Z"^^xsd:dateTime ;
    projecta:belongsToProject :project-ecommerce-checkout-redesign .
```

#### Step 3: SHACL Validation

The candidate passes:

- **Source evidence shape:** The candidate has `prov:wasDerivedFrom` a valid `NoteItem` in the sources graph.
- **Candidate evidence shape:** The candidate is in the candidates graph, not the asserted graph.
- **Project scope shape:** The candidate's `belongsToProject` matches the source `NoteItem`'s project.

#### Step 4: Human Review — Confirmation

BrSE Le reviews the candidate and confirms it. The candidate transitions:

```turtle
# Candidate status updated
:req-address-confirmation-candidate
    projecta:candidateStatus projecta:confirmed .

# Review activity recorded in provenance
:review-activity-20260729-002
    a prov:Activity ;
    rdfs:label "Human review — confirmed" ;
    prov:used :req-address-confirmation-candidate ;
    prov:wasAssociatedWith :person-le ;
    prov:endedAtTime "2026-07-29T10:15:00Z"^^xsd:dateTime ;
    projecta:reviewDecision projecta:confirmed ;
    projecta:belongsToProject :project-ecommerce-checkout-redesign .
```

#### Step 5: Assertion Promotion

The confirmed candidate is promoted to the asserted graph:

```turtle
# Asserted fact in /project/ecommerce-checkout-redesign/asserted
:req-address-confirmation
    a projecta:Requirement ;
    rdfs:label "Address confirmation step before payment" ;
    projecta:contentText "Khách hàng yêu cầu thêm bước xác nhận địa chỉ trước khi thanh toán. Cần làm rõ: có bắt buộc với KH đã lưu địa chỉ không?" ;
    projecta:belongsToProject :project-ecommerce-checkout-redesign ;
    prov:wasDerivedFrom :req-address-confirmation-candidate ;
    prov:wasAttributedTo :person-le ;
    projecta:validFrom "2026-07-29"^^xsd:date .

# Assertion activity in provenance
:assertion-activity-20260729-003
    a prov:Activity ;
    rdfs:label "Candidate promoted to asserted fact" ;
    prov:used :req-address-confirmation-candidate ;
    prov:generated :req-address-confirmation ;
    prov:wasAssociatedWith :person-le ;
    prov:endedAtTime "2026-07-29T10:15:00Z"^^xsd:dateTime ;
    projecta:belongsToProject :project-ecommerce-checkout-redesign .
```

### 3.3. What This Demonstrates

- **End-to-end traceability:** The asserted requirement can be traced back through the candidate, the extraction activity, and the source `NoteItem` to the original sprint review note authored by Le.
- **Graph isolation:** The source `NoteItem` is in `/sources`, the candidate is in `/candidates`, the asserted fact is in `/asserted`, and every transition activity is in `/provenance`. No graph boundary is violated.
- **No mutation of evidence:** The original `NoteItem` and its `contentText` are unchanged. The lifecycle adds new facts; it never overwrites existing ones.
- **Human-in-the-loop:** The reviewer (Le) confirmed the candidate before it became an asserted fact. The confirmation is recorded as a distinct provenance activity.
- **PROV-O alignment:** Every transition uses `prov:Activity`, `prov:wasAssociatedWith`, `prov:used`, `prov:generated`, `prov:wasDerivedFrom`, and `prov:generatedAtTime` — avoiding custom provenance vocabulary.
- **Project scope:** Every entity and activity carries `belongsToProject`, enforcing single-project containment.
- **Temporal integrity:** The candidate was extracted on 2026-07-29, reviewed and asserted on the same day. The original note was captured on 2026-07-28. The `validFrom` date marks when the asserted fact became effective.

## 4. Counterexamples

The following scenarios are explicitly **not** valid lifecycle transitions. They illustrate common misunderstandings of the boundary.

### 4.1. Counterexample A: Direct Assertion Without Candidate Stage

> The system extracts text from a NoteItem, runs no validation, creates no candidate, and writes the extracted fact directly into the asserted graph.

**Why this is NOT valid:**

- Bypasses the candidate stage — there is no opportunity for human review.
- No candidate evidence is recorded — provenance ends at the extraction step.
- The asserted graph contains a fact with no review decision, no reviewer identity, and no confirmation timestamp.
- This violates the "candidate before assertion" principle from [§2.4](#24-main-flow) and the semantic lifecycle state machine in [Ontology Design §9](../../docs/initialization/05-Ontology-Design.md#9-semantic-lifecycle).

### 4.2. Counterexample B: Candidate Masquerading as Asserted Fact

> A candidate is placed in the asserted graph with a status property set to "Extracted" or "PendingReview" — effectively treating the candidate graph as optional.

**Why this is NOT valid:**

- Graph isolation is the enforcement mechanism, not a convention. A candidate in the asserted graph is indistinguishable from an asserted fact to downstream consumers (API, UI, inference).
- Querying "all asserted requirements" would silently include unreviewed candidates.
- This is detectable by SHACL isolation shapes: `sh:targetClass projecta:Candidate` in the asserted graph must fail validation.

### 4.3. Counterexample C: Status Mutation Without Provenance Activity

> The system modifies the `candidateStatus` from `PendingReview` to `Confirmed` by overwriting the triple, without recording a `prov:Activity`.

**Why this is NOT valid:**

- There is no record of who confirmed the candidate, when, or why.
- The temporal history is lost — the previous state cannot be reconstructed.
- This violates the "no overwrite" constraint: the old status triple must be retained (or the transition recorded as a dated activity), not silently replaced.

### 4.4. Counterexample D: Cross-Project Assertion Without Authorization

> A NoteItem in project "Ecommerce Checkout Redesign" yields a candidate that is asserted in project "Payment Platform Modernization" without an explicit cross-project link and authorization.

**Why this is NOT valid:**

- Every entity carries `belongsToProject` with a single project. Cross-project knowledge sharing requires an explicit cross-project relation type and authorization — it cannot happen by silently retargeting the `belongsToProject` value.
- Without authorization, a reviewer in one project could influence the asserted knowledge of another project, violating project isolation.

### 4.5. Counterexample E: Overwriting Historical State

> When a requirement is superseded, the system deletes the old asserted fact or mutates its `validTo` by deleting the old triple and inserting a new one.

**Why this is NOT valid:**

- The old fact's history is destroyed. Consumers who built decisions on the old state cannot reconstruct what was true at the time.
- Supersession must create a new provenance activity that references the old fact via `prov:wasDerivedFrom` and records the new `validTo` — the old fact remains in the asserted graph with immutable properties.

## 5. Non-Goals for Sprint 2

The following capabilities are explicitly excluded from the Sprint 2 lifecycle slice:

| Non-Goal | Reason | Target Sprint |
|---|---|---|
| Automatic LLM-powered candidate extraction | Sprint 2 defines the lifecycle contract and SHACL shapes; extraction logic is a downstream implementation concern | Sprint 3+ |
| Human review UI or confirmation workflow UX | The lifecycle states and transitions are modeled in the ontology; the interaction flow is not part of Sprint 2 | Sprint 3+ |
| Candidate promotion runtime (Semantic Core API) | The API that executes transitions at runtime is Sprint 3 scope | Sprint 3 |
| Inference rules that materialize new facts | Only deterministic rules needed by approved competency questions are in scope; exemplar-only rules are deferred | Sprint 2 (scope analysis only — S2-17) |
| Retry, cursor, session, or workflow execution state | Operational execution state is not modeled in the ontology | Not scheduled |
| Entity linking (linking candidates to existing asserted entities) | Requires a stable asserted graph to link against | Sprint 3+ |
| Connector-triggered lifecycle (e.g., Jira webhook creates a candidate) | Connector integration is future work | Sprint 3+ |
| Multi-project or shared candidates | Single-project scope only per the carried decisions | Not scheduled |
| Automated periodic re-extraction or reprocessing of sources | Operational scheduling concern | Not scheduled |

## 6. What the Ontology Must Support

For Sprint 2, the ontology must define:

### 6.1. Lifecycle Classes

- **`Candidate`** — a proposed knowledge item that has not yet been confirmed. Lives only in the candidates graph.
- **`AssertedFact`** (or reuse appropriate v0.1 classes like `Requirement`, `Decision`, etc., as targets for asserted instances) — a confirmed, human-validated fact. Lives only in the asserted graph.
- **`LifecycleStatus`** — a controlled vocabulary of lifecycle states: `Extracted`, `Validated`, `PendingReview`, `Confirmed`, `Rejected`, `Asserted`, `Superseded`, `Retracted`.

### 6.2. Provenance Properties (PROV-O reuse)

- `prov:wasDerivedFrom` — candidate → source NoteItem; asserted fact → candidate.
- `prov:wasGeneratedBy` — entity → extraction or assertion activity.
- `prov:wasAssociatedWith` — activity → human reviewer or generator agent.
- `prov:used` — activity → input entity (e.g., the candidate used in a review activity).
- `prov:generated` — activity → output entity.
- `prov:generatedAtTime` — timestamp of generation.
- `prov:endedAtTime` — timestamp when an activity completed.

### 6.3. Lifecycle Properties (Projecta-specific)

- **`candidateStatus`** — the current lifecycle state of a candidate.
- **`reviewDecision`** — the outcome of a review activity (`confirmed` or `rejected`).
- **`rejectionReason`** — the reason a candidate was rejected.
- **`retractionReason`** — the reason an asserted fact was retracted.
- **`hasSourceEvidence`** — link from a candidate to its evidence record.
- **`proposedOntologyVersion`** — the ontology version under which the candidate was proposed.
- **`generator`** — identifier of the extraction model or tool version.
- **`validFrom`** / **`validTo`** — temporal validity interval for an asserted fact.
- **`supersededBy`** — link from a superseded fact to its replacement.

### 6.4. Named Graphs

The ontology must define the five canonical named-graph templates:

- `/project/{id}/sources` — Sprint 1 `Note` and `NoteItem` instances.
- `/project/{id}/candidates` — proposed knowledge items awaiting review.
- `/project/{id}/asserted` — confirmed, human-validated facts.
- `/project/{id}/inferred` — facts generated by deterministic inference rules.
- `/project/{id}/provenance` — all `prov:Activity` instances for the project.

### 6.5. SHACL Shapes

The ontology must define shapes for:

- **Source evidence** (S2-11): candidate must have a valid source `Note`/`NoteItem`.
- **Candidate evidence** (S2-12): candidate must have generator, timestamp, proposed ontology version, and must NOT be in the asserted graph.
- **Graph isolation** (S2-13): candidate in asserted, inferred in asserted, missing project, cross-project relation, provenance visibility.
- **Temporal lifecycle** (S2-14): valid lifecycle states, reviewer evidence, `validFrom`/`validTo`, supersession/retraction, invalid time intervals.

The ontology does **not** need to model in Sprint 2:

- Full API contracts or endpoint signatures.
- UI state or confirmation dialog models.
- Connector-specific extraction activities.
- Execution retry, cursor, or session models.
- Business-specific inference rules beyond what competency questions require.

## 7. Acceptance Criteria for This Slice

- [x] The Knowledge Lifecycle use case is documented with actor, trigger, preconditions, main flow, postconditions, and alternative flows.
- [x] A concrete positive example traces a Sprint 1 `NoteItem` through candidate, review, and assertion.
- [x] At least four counterexamples clarify what is NOT a valid lifecycle transition.
- [x] Non-goals are explicitly listed with rationale and target sprint.
- [x] The ontology requirements derived from this use case are identified (classes, PROV-O properties, Projecta-specific properties, named graphs, SHACL shapes).
- [x] The use case is consistent with the v0.1 ontology (no released IRI is renamed or repurposed) and the carried Sprint 2 decisions.
- [x] Human reviewer confirms the use case boundary before S2-03 (competency question review) proceeds.
