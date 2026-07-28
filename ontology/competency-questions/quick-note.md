# Competency Questions — Quick Note Slice (Sprint 1)

## Purpose

This document defines the competency questions that the Sprint 1 ontology kernel must answer for the Quick Note vertical slice. Each question has a stable identifier, a natural-language formulation, and an expected answer shape.

These questions drive vocabulary design (S1-06–S1-09), the demo graph (S1-10), and SPARQL query implementation (S1-11).

## Scope

All questions are scoped to the Quick Note use case defined in [docs/use-cases/quick-note.md](../../docs/use-cases/quick-note.md). Questions about candidate extraction, entity linking, confirmation workflow, or inference are deferred to Sprint 2+.

---

## Note Retrieval

### CQ-NOTE-001 — List notes in a project

**Question:** Những note nào thuộc project P?

**Expected answer shape:**

| Variable | Type | Description |
|---|---|---|
| `?note` | IRI | Note identifier |
| `?title` | xsd:string | Note title or first-line label |
| `?recordedAt` | xsd:dateTime | Capture timestamp |

**Example mapping:** For project "Ecommerce Checkout Redesign," the result set includes the sprint review note dated 2026-07-28.

### CQ-NOTE-002 — Retrieve author of a note

**Question:** Ai là tác giả của note N?

**Expected answer shape:**

| Variable | Type | Description |
|---|---|---|
| `?author` | IRI | Person who authored the note |
| `?authorName` | xsd:string | Display name of the author |

**Example mapping:** Note "2026-07-28 Sprint Review — Ecommerce Checkout" was authored by Le.

### CQ-NOTE-003 — Retrieve creation timestamp

**Question:** Note N được tạo khi nào?

**Expected answer shape:**

| Variable | Type | Description |
|---|---|---|
| `?recordedAt` | xsd:dateTime | Capture timestamp |

**Example mapping:** The sprint review note returns `2026-07-28T...`.

### CQ-NOTE-004 — Retrieve project of a note

**Question:** Note N thuộc project nào?

**Expected answer shape:**

| Variable | Type | Description |
|---|---|---|
| `?project` | IRI | Project identifier |
| `?projectName` | xsd:string | Project name |

**Example mapping:** The sprint review note belongs to project "Ecommerce Checkout Redesign."

---

## Note Item Retrieval

### CQ-NOTEITEM-001 — List items in a note

**Question:** Note N chứa những note item nào, mỗi item thuộc loại gì?

**Expected answer shape:**

| Variable | Type | Description |
|---|---|---|
| `?noteItem` | IRI | NoteItem identifier |
| `?itemType` | IRI | Type of the item (Requirement, Decision, Question, Task, Risk, Assumption, Constraint, ProgressUpdate, ResearchNeed) |
| `?contentText` | xsd:string | The text content of the item |

**Example mapping:** The sprint review note contains 6 items: one Requirement, one Risk, one Decision, one Task, one Question, and one Assumption.

### CQ-NOTEITEM-002 — Filter items by type in a project

**Question:** Những note item nào thuộc loại T trong project P?

**Expected answer shape:**

| Variable | Type | Description |
|---|---|---|
| `?noteItem` | IRI | NoteItem identifier |
| `?contentText` | xsd:string | Text content |
| `?note` | IRI | Parent note |
| `?noteTitle` | xsd:string | Parent note title |

**Example mapping:** Filtering by type "Risk" in "Ecommerce Checkout Redesign" returns one item about the tax API timeout.

### CQ-NOTEITEM-003 — Retrieve full content of a note item

**Question:** Nội dung đầy đủ của note item I là gì?

**Expected answer shape:**

| Variable | Type | Description |
|---|---|---|
| `?contentText` | xsd:string | Full text content |
| `?itemType` | IRI | Type of the item |

**Example mapping:** The Requirement item returns "Khách hàng yêu cầu thêm bước xác nhận địa chỉ trước khi thanh toán. Cần làm rõ: có bắt buộc với KH đã lưu địa chỉ không?"

---

## Author and Provenance

### CQ-PROV-001 — Notes authored by a person in a project

**Question:** Người A đã tạo những note nào trong project P?

**Expected answer shape:**

| Variable | Type | Description |
|---|---|---|
| `?note` | IRI | Note identifier |
| `?title` | xsd:string | Note title |
| `?recordedAt` | xsd:dateTime | Capture timestamp |

**Example mapping:** Filtering by author "Le" in "Ecommerce Checkout Redesign" returns the sprint review note.

### CQ-PROV-002 — Provenance chain for a note item

**Question:** Note item I có nguồn gốc từ đâu (note nào, ai viết, khi nào)?

**Expected answer shape:**

| Variable | Type | Description |
|---|---|---|
| `?note` | IRI | Parent note |
| `?noteTitle` | xsd:string | Parent note title |
| `?author` | IRI | Author of the note |
| `?authorName` | xsd:string | Author display name |
| `?recordedAt` | xsd:dateTime | When the note was captured |

**Example mapping:** The Decision item ("Redis cache cho thuế") traces back to the sprint review note, authored by Le on 2026-07-28.

### CQ-PROV-003 — All items from notes authored by a specific person

**Question:** Người A đã capture những note item nào (trên tất cả project)?

**Expected answer shape:**

| Variable | Type | Description |
|---|---|---|
| `?noteItem` | IRI | NoteItem identifier |
| `?itemType` | IRI | Type of item |
| `?contentText` | xsd:string | Text content |
| `?project` | IRI | Project the note belongs to |

**Example mapping:** Filtering by Le returns all 6 items from the sprint review note, each with its project context.

---

## Aggregation

### CQ-COUNT-001 — Item count by type in a project

**Question:** Trong project P, mỗi loại note item có bao nhiêu mục?

**Expected answer shape:**

| Variable | Type | Description |
|---|---|---|
| `?itemType` | IRI | Type of item |
| `?count` | xsd:integer | Number of items of that type |

**Example mapping:** For "Ecommerce Checkout Redesign," the result shows one item each for Requirement, Risk, Decision, Task, Question, and Assumption.

### CQ-COUNT-002 — Note count in a project

**Question:** Project P có bao nhiêu note?

**Expected answer shape:**

| Variable | Type | Description |
|---|---|---|
| `?count` | xsd:integer | Number of notes |

**Example mapping:** For "Ecommerce Checkout Redesign," the result is `1` (only the sprint review note exists in the demo graph).

---

## Boundary and Data Quality

### CQ-BOUND-001 — Detect notes without project assignment

**Question:** Có note nào không thuộc project nào không?

**Expected answer shape:**

| Variable | Type | Description |
|---|---|---|
| — | xsd:boolean | ASK query result |

**Expected value:** `false` — every note must have a `belongsToProject` relationship.

### CQ-BOUND-002 — Detect note items without a parent note

**Question:** Có note item nào không thuộc note nào không?

**Expected answer shape:**

| Variable | Type | Description |
|---|---|---|
| — | xsd:boolean | ASK query result |

**Expected value:** `false` — every NoteItem must be connected to a Note via `hasNoteItem` (inverse: every NoteItem must be the object of exactly one `hasNoteItem` assertion).

---

## Summary

| ID | Short Description | Query Type |
|---|---|---|
| CQ-NOTE-001 | List notes in a project | SELECT |
| CQ-NOTE-002 | Author of a note | SELECT |
| CQ-NOTE-003 | Creation timestamp of a note | SELECT |
| CQ-NOTE-004 | Project of a note | SELECT |
| CQ-NOTEITEM-001 | Items in a note with types | SELECT |
| CQ-NOTEITEM-002 | Items of a given type in a project | SELECT |
| CQ-NOTEITEM-003 | Full content of a note item | SELECT |
| CQ-PROV-001 | Notes by a person in a project | SELECT |
| CQ-PROV-002 | Provenance chain for a note item | SELECT |
| CQ-PROV-003 | All items captured by a person | SELECT |
| CQ-COUNT-001 | Item count by type per project | SELECT (GROUP BY) |
| CQ-COUNT-002 | Note count per project | SELECT (COUNT) |
| CQ-BOUND-001 | Orphan notes (no project) | ASK |
| CQ-BOUND-002 | Orphan note items (no parent note) | ASK |

**Total:** 14 competency questions across 5 categories.
