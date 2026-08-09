# Task Summary: S8-50 — Structured Note draft contract

**Sprint:** Sprint 8
**Task:** S8-50
**Status:** Complete

## Outcome

Added a strict application-layer structured Note draft contract in
`apps/api/src/projecta_api/structured_note.py`.

- `title`, ordered typed `items`, item `content`, optional `sourceMetadata`,
  and explicit operational `draftStatus` are modeled with closed Pydantic
  vocabularies and forbidden extra fields.
- The nine released NoteItem types are reused; no ontology term is introduced.
- The server canonicalizes CRLF/CR to LF and derives `rawText` by joining item
  content with one LF. The title remains Note metadata and is not evidence text.
- Each item receives a half-open `startOffset`/`endOffset` measured in Unicode
  code points. Repeated content remains distinct because offsets are positional.
- Empty drafts are valid during editing; commit-time semantic requirements are
  explicitly deferred to S8-54 after the S8-53 approval gate.

## Validation

- `uv run pytest tests/test_structured_note_contract.py` — passed.
- `uv run ruff check src/projecta_api/structured_note.py tests/test_structured_note_contract.py` — passed.
- `uv run pyright` — passed.
- `git diff --check` — passed.

## Governance boundary

This is an operational contract only. `draftStatus`, `sourceMetadata`, and the
derived ordering projection do not authorize changes to ontology Turtle,
SHACL, inference, Semantic Core, or shared data. Those changes remain
`PROPOSAL_ONLY` until S8-53 human approval.
