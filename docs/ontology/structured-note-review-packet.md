# Structured Note Semantic Review Packet — S8-51 / S8-52

**Status:** `HUMAN_APPROVED_FOR_IMPLEMENTATION`
**Scope:** S8-50 through S8-54 semantic boundary
**Prepared:** 2026-08-10

**Human approval recorded:** 2026-08-10 — user approved all listed semantic
decisions and authorized continuation through S8-60.

## Proposed outcome

Approve the smallest compatible outcome: add no ontology class, property,
individual, SHACL shape, inference rule, or migration. Reuse the released
`Note`, `NoteItem`, nine `NoteItemType` individuals, project, author, evidence,
provenance, candidate lifecycle, and temporal vocabulary.

The S8-50 application contract is not an ontology extension. `draftStatus` is
workflow state, `sourceMetadata` is optional origin metadata, and the ordered
array is a server projection. `title` maps to released `projecta:name`; item
order is textual order derived from released evidence offsets after LF
normalization.

## Semantic commitment decisions

| Concern | Proposal | Boundary |
| --- | --- | --- |
| Item order | Sort evidence-bearing items by `evidenceStartOffset`. | This is textual source order only; no `itemOrder` term. Legacy offsetless items remain unordered. |
| Assignee/requester | Keep mentions as source evidence. | No `assignedTo` or requester property on Note/NoteItem. |
| Due/effective date | Keep date phrases as source evidence; reuse valid-time terms only for governed asserted facts. | No bare `deadline`/`dueAt` literal and no inferred effective date. |
| Work status | Keep `draftStatus` operational and candidate lifecycle separate. | No generic Note/NoteItem `status`. |
| Source context | Reuse Note project, author, recorded time, evidence, and provenance. | No second project scope or UI-only RDF context term. |

## Validation matrix

| Artifact | Coverage | Expected result |
| --- | --- | --- |
| `ontology/examples/structured-note-s8-50-positive.trig` | Title, project, author, raw text, typed items, ordered Unicode/code-point offsets | RDF syntax valid; released source/evidence shapes conform |
| `ontology/examples/negative-note-no-timestamp.trig` | Missing required capture time | Existing `NoteShape` rejects it |
| `ontology/examples/negative-noteitem-no-content.ttl` | Missing item content | Existing `NoteItemShape` rejects it |
| `ontology/examples/negative-invalid-itemtype.trig` | Closed item vocabulary | Existing `NoteItemShape` rejects it |
| `ontology/examples/negative-orphan-noteitem.trig` | Missing parent Note | Existing source shape rejects it |
| `ontology/competency-questions/structured-note-s8-queries.rq` | Title/containment/order/deferred-term boundary | Read-only query artifact; no runtime mutation |

These fixtures intentionally exercise released constraints. No draft SHACL is
created because the proposal adds no semantic term or validation behavior.

## Compatibility and rollback

No migration, deprecation, released IRI rename, named-graph change, or data
backfill is proposed. Existing raw/segment captures remain valid and continue
to be handled by the v0.3 contract. If this proposal is rejected, remove the
S8-50 application module and its tests; no ontology or shared data rollback is
needed. If a later approved decision introduces durable order, assignment,
deadline, status, or Note revision, it must come with new competency questions,
SHACL/query/negative fixtures, provenance and temporal semantics, and a
versioned migration/rollback plan.

## S8-53 human approval

The following exact approval is required before S8-54 changes Semantic Core,
ontology loading, SHACL behavior, or source write validation:

- [x] Approve reuse of released Note/NoteItem/evidence/provenance terms with no
  new ontology vocabulary.
- [x] Approve S8-50 canonical raw text: normalized item content joined by one
  LF; title is Note metadata and not part of evidence text.
- [x] Approve half-open Unicode-code-point offsets derived server-side from
  canonical raw text.
- [x] Approve `draftStatus` and `sourceMetadata` as operational fields only.
- [x] Approve deferring `itemOrder`, `assignedTo`, requester, `deadline`/`dueAt`,
  generic Note/NoteItem status, and Note revision.
- [x] Approve no migration and backward compatibility with released raw/segment
  captures.

The approved outcome authorizes S8-54 semantic implementation under these exact
boundaries. It does not authorize future ontology additions or a migration
outside this packet.
