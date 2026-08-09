# Structured Note Proposal — Sprint 8

**Status:** `PROPOSAL_ONLY`

**Tasks:** S8-50 / S8-51 / S8-52

## Outcome

The Sprint 8 structured Note proposal introduces no new ontology vocabulary.
The released `Note`, `NoteItem`, `NoteItemType`, project, authorship,
evidence, candidate-lifecycle, provenance, and temporal terms are sufficient
for the current source-capture boundary. The Graph experience may project
human-readable labels, derived text order, evidence, and provenance, but it may
not promote source wording into confirmed assignee, deadline, status, or task
facts.

The supporting competency questions, validation references, and semantic
commitment interview are in
[structured-note.md](../../ontology/competency-questions/structured-note.md)
and the [S8-52 review packet](structured-note-review-packet.md).

The application contract in S8-50 is deliberately separate from this semantic
proposal. `draftStatus`, `sourceMetadata`, and the server-derived item array
are operational/projection fields; they do not become RDF terms. `title` maps
to the released Note name, while item order is derived only from canonical
evidence offsets.

## Reuse and defer matrix

| Concern | Reuse now | Do not do in Sprint 8 discovery |
| --- | --- | --- |
| Note identity | `projecta:Note` server-owned capture identity | Do not merge by text/title or overwrite a source capture. |
| NoteItem identity | `projecta:NoteItem` under one Note | Do not treat repeated text or repeated extraction as the same identity. |
| Item order | Evidence offsets for textual order in v0.3 Notes | Do not add `itemOrder` for an unapproved editorial/UI ordering. |
| Item type | Nine released `projecta:NoteItemType` individuals | Do not create a class for each source label or assert domain truth from a tag. |
| Project | `projecta:belongsToProject` on Note; parent closure for NoteItem | Do not add a second project scope or client-selected graph IRI. |
| Author | `projecta:authoredBy` on Note | Do not equate author with mentioned person, requester, or assignee. |
| Assignee | Future governed work assignment | Do not add `assignedTo` directly to Note/NoteItem. |
| Deadline | Future time-qualified work commitment | Do not add a bare `deadline`/`dueAt` literal to source evidence. |
| Status | Candidate lifecycle and future work/asserted status separately | Do not add a generic Note/NoteItem `status`. |
| Provenance | Existing Note → NoteItem → Candidate/activity chain | Do not put candidate/asserted provenance in source text or UI state. |
| Time | `recordedAt`, evidence offsets, and asserted validity retain distinct meanings | Do not conflate capture time, evidence position, effective time, and due time. |
| Edit history | Existing capture boundary preserves source records | Do not overwrite a Note or run an unapproved migration. |

## Compatibility and migration

No migration is proposed. All released IRIs remain unchanged; existing v0.1,
v0.2, and v0.3 source/candidate fixtures remain the compatibility baseline.
The UI/API may consume the finite projection contract only after enforcing
project scope and preserving the source/evidence/lifecycle boundary.

If a future semantic decision adds assignment, deadline, durable order, status,
or Note revision, it must include its own competency questions, complete
semantic commitment interview, SHACL/query fixtures, provenance and temporal
rules, cross-project tests, compatibility impact, and migration/rollback plan.

## Human decision

This proposal is not an authorization to edit ontology Turtle, SHACL, rules,
fixtures, runtime code, or shared data. Human approval must be recorded in the
[S8-53 approval section](structured-note-review-packet.md#s8-53-human-approval)
before semantic write-boundary implementation begins.
