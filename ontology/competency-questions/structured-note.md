# Structured Note Semantic Interview — Sprint 8

**Status:** `PROPOSAL_ONLY` / `PENDING_HUMAN_REVIEW` — interview, gap analysis,
and validation mapping only; no ontology vocabulary or runtime data was
changed.

**Tasks:** S8-51 / S8-52

**Purpose:** Establish the meaning and boundary of a structured Note before
proposing any new class or property for the Sprint 8 graph experience. The
interview separates released source semantics from candidate/asserted
knowledge, operational state, and UI projection data.

## Current released baseline

The released Note vocabulary is additive across the communication, evidence,
provenance, and temporal modules:

| Need | Reuse | Current meaning |
| --- | --- | --- |
| Note identity | `projecta:Note` | A human-authored capture event and source artifact. |
| Note item identity | `projecta:NoteItem` | A typed source segment inside one Note. |
| Parent link | `projecta:isItemOf` / `projecta:hasNoteItem` | A NoteItem belongs to exactly one Note under the source shape. |
| Project | `projecta:belongsToProject` | A Note has exactly one project. A NoteItem obtains project context through its parent Note. |
| Author | `projecta:authoredBy` / `projecta:authorOf` | A Note has exactly one `projecta:Person` author. |
| Capture time | `projecta:recordedAt` | The time the source artifact was captured. |
| Raw source | `projecta:rawText` | Canonical complete Note body in the v0.3 evidence contract. |
| Item type | `projecta:hasItemType` | One of the nine released `NoteItemType` individuals. |
| Item text | `projecta:contentText` | Exact source text for the NoteItem. |
| Evidence location | `projecta:evidenceStartOffset` / `projecta:evidenceEndOffset` | Half-open Unicode-code-point range into `rawText` in the v0.3 contract. |
| Extraction provenance | `prov:wasDerivedFrom`, `prov:wasGeneratedBy`, `prov:generatedAtTime` | Candidate provenance from a source NoteItem and extraction activity. |
| Lifecycle | `projecta:candidateStatus`, `projecta:validFrom`, `projecta:validTo`, `projecta:supersededBy` | Candidate review lifecycle and asserted-fact temporal validity; not a generic Note status. |

The exact released IRIs and constraints remain in
`ontology/communication.ttl`, `ontology/evidence.ttl`,
`ontology/shapes/source-shapes.ttl`, and the approved v0.3 evidence proposal.

## Competency questions

These questions are the acceptance boundary for the structured Note model.
They must be answerable without treating UI fields as domain truth.

### Identity and containment

**CQ-S8-NOTE-001 — What is a Note?**

What source capture event does Note `N` represent, and what makes two Note
records the same? A Note is identified by its server-owned IRI for one capture
event. Equal or similar text does not merge two captures. A later correction
must not overwrite the original source record.

**CQ-S8-NOTE-002 — What is a NoteItem?**

Which source segment belongs to Note `N`, and what makes two NoteItems the
same? A NoteItem is the server-owned source segment identity created under one
Note. The same text in two Notes is not the same NoteItem. Re-extraction is a
new Candidate, not a new NoteItem.

**CQ-S8-NOTE-003 — Which items are in a Note?**

The query follows `projecta:hasNoteItem` (or its inverse
`projecta:isItemOf`) and returns only items whose parent is the requested Note.
An orphan NoteItem is invalid source data, not an implicit global item.

### Ordering and item type

**CQ-S8-NOTE-004 — What is the order of NoteItems?**

For an evidence-bearing v0.3 Note, textual order can be derived from the
half-open `evidenceStartOffset` values after canonical LF normalization;
non-overlap is validated. This does not prove a separate editorial/display
order. For legacy Notes without evidence offsets, RDF `hasNoteItem` is an
unordered multi-valued property and no order may be inferred.

**Boundary:** A UI/API array position is retrieval metadata unless a future
use case requires durable authored ordering. No `itemOrder` property is
proposed in S8-09.

**CQ-S8-NOTE-005 — What does an item type mean?**

`projecta:hasItemType` classifies source text using one of the nine released
controlled individuals: requirement, decision, question, task, risk,
assumption, constraint, progress-update, or research-need. It does not assert
that the NoteItem is itself a confirmed Requirement, Task, or other asserted
domain entity. Promotion creates separately governed asserted knowledge.

### Project, author, and responsibility

**CQ-S8-NOTE-006 — Which project contains the Note?**

`projecta:belongsToProject` on the Note is the authoritative project scope and
is exactly one under `NoteShape`. A NoteItem is scoped through its parent Note;
queries and graph routing must apply that closure before returning data.

**CQ-S8-NOTE-007 — Who authored the Note?**

`projecta:authoredBy` identifies exactly one `projecta:Person` for the Note.
The author of the source capture is not automatically the author of a future
asserted KnowledgeItem, nor the assignee of a task mentioned in the text.

**CQ-S8-NOTE-008 — Who is assigned to work?**

If a NoteItem describes a task, the source text may mention an assignee, but
that mention is evidence only. A confirmed work assignment requires a governed
work entity, an actor identity, project scope, and assignment provenance. The
current Note source contract does not justify a direct `assignedTo` property on
Note or NoteItem. No new assignment term is proposed in S8-09.

### Deadline and status

**CQ-S8-NOTE-009 — What deadline is stated?**

A phrase such as “by Friday” is source text, not a canonical deadline. A
canonical deadline would require at least a target work entity, calendar/time
zone policy, distinction between requested and committed date, provenance, and
correction/supersession behavior. The current Note contract does not provide
those semantics. No `deadline` or `dueAt` property is proposed in S8-09.

**CQ-S8-NOTE-010 — What is the status?**

There are three different meanings that must not be collapsed:

1. Source capture state: the Note is recorded at `recordedAt`.
2. Candidate review state: `candidateStatus` and provenance activities govern
   extraction/review/promotion.
3. Work or asserted-fact state: a future Task/KnowledgeItem contract may have
   its own controlled status and temporal rules.

`progress-update` is an item type, not a current status. No generic `status`
property is proposed for Note or NoteItem.

### Provenance and time

**CQ-S8-NOTE-011 — What is the provenance chain?**

For source evidence, traverse NoteItem → Note → author/project/capture time.
For extracted candidates, traverse Candidate → NoteItem via
`prov:wasDerivedFrom`, then the source chain; use the extraction activity and
`prov:generatedAtTime` to identify how and when the candidate was produced.
Candidate evidence remains separate from asserted knowledge and inferred
results.

**CQ-S8-NOTE-012 — Which time is which?**

`projecta:recordedAt` is capture time, not the time a statement becomes true.
`projecta:evidenceStartOffset` and `projecta:evidenceEndOffset` are positions,
not temporal validity. `projecta:validFrom` and `projecta:validTo` apply to
asserted KnowledgeItem validity under the temporal contract. Any future
deadline or effective-date semantics need their own identity, provenance,
timezone, correction, and historical query decisions.

## Semantic commitment interview outcome

S8-09 introduces no new class, object property, datatype property, controlled
individual, SHACL shape, or inference rule. The interview therefore records
reuse/defer outcomes rather than permanent-looking new IRIs.

### Terms considered but not proposed

| Candidate term | Classification after interview | Decision |
| --- | --- | --- |
| `itemOrder` | Retrieval/UI ordering or possible source assertion | Defer. Evidence offsets provide textual order only for v0.3 Notes; no durable editorial-order requirement is approved. |
| `assignedTo` | Work assignment relation, not Note authorship | Defer. Model on a governed work/assignment entity only after identity, actor role, temporal, and provenance semantics are approved. |
| `deadline` / `dueAt` | Time-qualified work commitment | Defer. Do not attach a date literal directly to source Note evidence. |
| generic `status` | State vocabulary/property | Defer. Reuse candidate lifecycle and future work/asserted status contracts separately. |
| Note-level `revision` | Source lifecycle/version assertion | Defer. Note edit/versioning is outside the approved capture boundary; corrections must preserve source history. |

### Mandatory interview answers for the deferred terms

For each deferred candidate, the answer is the same at this stage: the
meaning is not yet independent enough from a UI field or future workflow to
commit a stable term. The relevant competency questions are CQ-S8-NOTE-004,
008, 009, 010, and 012. Positive examples are a source text segment whose
offset orders it, a confirmed task assignment with actor and provenance, a
confirmed task due date with timezone, and a candidate moving from extracted to
validated. Counterexamples are an array index mistaken for domain order, an
author mistaken for assignee, “Friday” without timezone treated as a canonical
instant, and a progress-update item treated as a lifecycle status.

No existing released Projecta term expresses all of the deferred meaning. The
safe outcome is to keep these as source evidence, operational state, or future
work/assertion modeling until the missing identity, lifecycle, domain/range,
temporal, project, and provenance commitments are answered by a human.

## Positive and boundary examples

### Positive source example

```turtle
:note-1 a projecta:Note ;
    projecta:belongsToProject :project-p ;
    projecta:authoredBy :person-a ;
    projecta:recordedAt "2026-08-09T10:00:00Z"^^xsd:dateTime ;
    projecta:rawText "Confirm address. Assign Le by Friday." .

:item-1 a projecta:NoteItem ;
    projecta:isItemOf :note-1 ;
    projecta:hasItemType projecta:requirement ;
    projecta:contentText "Confirm address." ;
    projecta:evidenceStartOffset 0 ;
    projecta:evidenceEndOffset 15 .
```

The text “Assign Le by Friday” remains source evidence. It does not create an
assignee, deadline, or Task assertion merely because it contains those words.

### Boundary examples

| Example | Correct interpretation |
| --- | --- |
| Same sentence captured in two Notes | Two Note/NoteItem identities; no name-based merge. |
| Two NoteItems with adjacent evidence ranges | Textual order can be derived from offsets. |
| Legacy NoteItems without offsets | No durable order may be claimed. |
| `projecta:task` item type | Source classification only; not an asserted `projecta:Task`. |
| Note author mentions another person | Mention is evidence; not `authoredBy` or `assignedTo`. |
| “Next Friday” with no timezone | Unresolved source phrase; no canonical `dueAt`. |
| Candidate status `validated` | Candidate lifecycle only; not work completion. |

## Compatibility and implementation boundary

| Consumer | S8-09 result |
| --- | --- |
| Released ontology | No changes; all released IRIs remain stable. |
| SHACL | No changes; existing Note/NoteItem and evidence shapes remain authoritative. |
| Semantic Core | No changes; capture continues to create source evidence and candidates only. |
| Graph projection | Projection may expose derived textual order and source provenance, but must label them as projection data and respect project scope. |
| UI | Must not render author, assignee, deadline, or status as confirmed facts unless backed by the corresponding governed resource/contract. |
| Migration | None proposed. Note edit/version migration remains out of scope. |
| Security/isolation | Traverse project context from Note; reject cross-project evidence and do not broaden source visibility. |

## Human review questions

1. Is the distinction between textual order from evidence offsets and durable
   editorial order acceptable for the Sprint 8 Graph view?
2. Should future assignment/deadline semantics be modeled on promoted
   `Task`/assignment resources rather than directly on source NoteItems?
3. Should Note editing/versioning remain outside the current capture contract,
   with corrections represented as new source records and provenance?

Until these answers are recorded, S8-09 remains `PENDING_HUMAN_REVIEW` and no
new Note vocabulary may be implemented.
