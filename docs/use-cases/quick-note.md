# Quick Note Use Case — Slice Boundary

## 1. Purpose

This document defines the precise boundary of the Quick Note use case for Sprint 1. It serves as the authoritative reference for competency questions (S1-02), term inventory (S1-06), and ontology design decisions that follow.

## 2. Use Case: Quick Note Capture

### 2.1. Actor

- BrSE (primary).
- Project Coordinator.
- Technical Business Analyst.

### 2.2. Trigger

The actor is in or preparing for a meeting, reviewing a conversation thread, or processing information from any channel. They need to capture structured knowledge quickly without switching to a formal documentation tool.

### 2.3. Preconditions

- The actor is authenticated.
- A target project exists (the note is always project-scoped).
- The actor has permission to create notes in that project.

### 2.4. Main Flow

1. Actor opens Quick Note in the context of a specific project.
2. Actor writes free-form text — this may span multiple paragraphs and cover multiple topics.
3. Actor optionally tags segments with a type: Requirement, Decision, Question, Task, Risk, Assumption, Constraint, Progress Update, or Research Need.
4. System persists the note as a `SourceArtifact` with:
   - Raw text content.
   - Project reference.
   - Actor identity.
   - Timestamp.
   - Optional type tags per segment.
5. System returns a confirmation with the note identifier.

### 2.5. Postconditions

- A new `Note` entity exists in the project's sources graph.
- The note content is available for downstream candidate extraction (Sprint 2+).
- The note does **not** automatically create asserted knowledge items.
- The note has complete provenance: who wrote it, when, in which project.

### 2.6. Alternative Flows

- **Edit after creation:** Actor may edit the raw text of an existing note. Previous versions are retained.
- **Delete:** Actor may delete a note. Deletion is soft (retained with status metadata).
- **Multi-project note:** Not supported in Sprint 1 — a note belongs to exactly one project.

## 3. Positive Example

### 3.1. Scenario

BrSE Le is in a sprint review meeting for project "Ecommerce Checkout Redesign." They hear several pieces of information and open Quick Note to capture them.

### 3.2. Raw Input

> **2026-07-28 Sprint Review — Ecommerce Checkout**
>
> - Khách hàng yêu cầu thêm bước xác nhận địa chỉ trước khi thanh toán. Cần làm rõ: có bắt buộc với KH đã lưu địa chỉ không? [Requirement]
> - Anh Tuấn (Dev lead) báo rằng API tính thuế bên thứ 3 đang bị timeout 15% request. Cần investigation. [Risk]
> - Team quyết định dùng Redis để cache kết quả tính thuế trong 30 phút. [Decision]
> - Hỗ trợ VNPay — chưa rõ ai làm, chưa có estimate. [Task]
> - Liệu API tính thuế có hỗ trợ batch request không? Cần hỏi bên vendor. [Question]
> - Giả định: KH có thể upload tối đa 3 file đính kèm cho mỗi đơn hàng. [Assumption]

### 3.3. What This Demonstrates

- **One note, multiple item types:** The note captures a Requirement, Risk, Decision, Task, Question, and Assumption — all in a single capture session.
- **Project-scoped:** Everything belongs to "Ecommerce Checkout Redesign."
- **Human-authored:** Le wrote this based on their own understanding; nothing was auto-generated.
- **Source artifact role:** This is raw input. None of these items are asserted knowledge yet — they must go through extraction, validation, and human confirmation before becoming part of the asserted graph.
- **Traceable:** The note has an author, timestamp, and project reference.

## 4. Counterexamples

The following scenarios are explicitly **not** Quick Note captures. They illustrate common misunderstandings of the boundary.

### 4.1. Counterexample A: Meeting Transcript

> **System-generated transcript:**
> "Vâng, em nghĩ là mình nên thêm cái bước xác nhận địa chỉ. Ừ, đúng rồi. Mà cái vụ API tính thuế hình như đang bị chậm, để em check lại xem sao..."

**Why this is NOT a Quick Note:**

- This is a system-generated transcript, not a human-authored note.
- It contains filler, hesitation, and conversational noise — not structured capture.
- The system cannot determine which parts are decisions, questions, or off-topic remarks.
- Transcripts are explicitly out of scope per [Project Scope §3.1](../initialization/02-Project-Scope.md#31-transcript-first-meeting-intelligence).

### 4.2. Counterexample B: Direct Jira Task Creation

> Actor opens Jira, creates a new task "Implement address confirmation step" with description, assignee, story points, sprint assignment, and acceptance criteria.

**Why this is NOT a Quick Note:**

- This bypasses the semantic core entirely — no source artifact is created.
- It creates an asserted WorkItem directly in an external system without any Projecta provenance linking it to the decision context.
- Jira is a connector — task creation through it is a downstream action (Sprint 3+), not the capture mechanism.

### 4.3. Counterexample C: AI-Generated Summary Without Human Input

> System listens to a Teams meeting, transcribes it, and outputs: "Based on the meeting, the following requirements were identified: 1. Add address confirmation step. 2. Fix tax API timeout issue..."

**Why this is NOT a Quick Note:**

- No human authored this — the BrSE did not actively capture information.
- There is no human judgment about what matters and what does not.
- The output skips the candidate stage and presents AI output as if it were asserted knowledge.
- This violates both the "no transcript dependency" principle and the "candidate before assertion" principle from the [Project Overview](../initialization/01-Project-Overview.md#73-deterministic-where-possible).

### 4.4. Counterexample D: Free-Form Personal Note Without Project Scope

> BrSE writes in their personal notepad: "Nhớ hỏi anh Tuấn về API tax. Còn vụ VNPay chưa biết ai làm."

**Why this is NOT a Quick Note (in the Projecta sense):**

- No project scope — the system cannot associate this with "Ecommerce Checkout Redesign."
- No structured capture boundary — the system cannot separate this from the actor's personal notes.
- No source artifact with provenance metadata — it is a private memory aid, not a system entity.

## 5. Non-Goals for Sprint 1

The following capabilities are explicitly excluded from the Sprint 1 Quick Note slice:

| Non-Goal | Reason | Target Sprint |
|---|---|---|
| LLM-powered candidate extraction from note text | Sprint 1 focuses on the ontology kernel and use case boundary, not AI extraction | Sprint 2+ |
| Automatic classification of note segments | Classification is a candidate-extraction concern | Sprint 2+ |
| Entity linking (linking note items to existing ontology entities) | Requires an asserted graph and inference rules | Sprint 3+ |
| SHACL validation of extracted candidates | Validation machinery is in scope for Sprint 1 ontology, but validating extracted candidates requires extraction first | Sprint 2 |
| Human confirmation workflow UI | Confirmation lifecycle is modeled in the ontology, but the interaction flow is not part of Sprint 1 | Sprint 3+ |
| Editing or deleting notes after creation | Core capture is the priority; mutation flows are a subsequent concern | Sprint 3+ |
| Cross-project or shared notes | Single-project scope only | Not scheduled |
| Connector-triggered note creation (e.g., from Teams message) | Manual capture only; connector integration is future work | Sprint 3+ |
| Note templates or structured forms | Free-text capture only; templates are a UX concern | Not scheduled |
| Full-text search across notes | Retrieval infrastructure is out of scope for Sprint 1 | Sprint 4+ |

## 6. What the Ontology Kernel Must Support

For Sprint 1, the ontology kernel must define:

- **`Note`** as a subclass of `SourceArtifact` — a human-authored capture event.
- **`NoteItem`** as a typed segment within a Note, with one of the following types: Requirement, Decision, Question, Task, Risk, Assumption, Constraint, ProgressUpdate, ResearchNeed.
- **`belongsToProject`** — the mandatory project scope for every Note.
- **`hasNoteItem`** — the relationship between a Note and its typed segments.
- **`authoredBy`** — the Actor (Person) who wrote the note.
- **`recordedAt`** — the timestamp of capture.
- **Provenance:** Every Note and NoteItem must be traceable to its author, project, and timestamp via PROV-O properties.

The ontology does **not** need to model in Sprint 1:

- Full semantic lifecycle states (Extracted → Validated → … → Asserted) beyond what the Core Ontology requires — complete transition logic is Sprint 2.
- Extraction rules or LLM prompt templates.
- UI or API contracts.
- Connector-specific Note origins.

## 7. Acceptance Criteria for This Slice

- [x] The Quick Note use case is documented with actor, trigger, preconditions, main flow, and postconditions.
- [x] A concrete positive example demonstrates a realistic multi-type capture scenario.
- [x] At least three counterexamples clarify what Quick Note is NOT.
- [x] Non-goals are explicitly listed with rationale and target sprint.
- [x] The ontology kernel requirements derived from this use case are identified.
- [x] Human reviewer confirms the use case boundary before S1-02 (competency questions) proceeds.
