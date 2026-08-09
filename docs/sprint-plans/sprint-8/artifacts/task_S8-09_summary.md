# Task Summary: Structured Note semantic interview

**Sprint:** Sprint 8
**Task:** S8-09

## Summary of Work

Completed a competency-question-driven interview for Note and NoteItem
identity, lifecycle, ordering, item type, project, author, assignee, deadline,
status, provenance, and temporal semantics. The result reuses the released
Note vocabulary and explicitly defers `itemOrder`, `assignedTo`, `deadline`/
`dueAt`, generic `status`, and Note revision semantics until the missing domain
commitments are answered by a human.

No ontology Turtle, SHACL, rule, migration, or runtime artifact was changed.

## Files Modified

* [structured-note.md](../../../../ontology/competency-questions/structured-note.md) - Competency questions, semantic interview, examples, compatibility boundary, and unresolved human questions.
* [sprint-8.md](../sprint-8.md) - Marked S8-09 complete.

## Testing

* **Test File:** N/A; this task produces a governed semantic interview artifact.
* **Status:** Passed.
* **Execution Command:** `git diff --check`; repository search of released Note vocabulary, shapes, examples, and Semantic Core capture path.

## Governance Status

`PENDING_HUMAN_REVIEW`. No new term is approved or implemented by this task.
