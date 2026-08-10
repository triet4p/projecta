# Task Summary: Make manual candidates reviewable

**Sprint:** Sprint 9 — Provider Runtime Truthfulness
**Task:** S9-12

## Summary of Work

Changed the candidate projection to derive manual candidate labels and proposed
semantic types from their canonical source NoteItems. The query also retains
support for LLM `EntityCandidate` records with direct proposed fields.

## Files Modified

* `services/semantic-core/src/main/java/org/projecta/semanticcore/FusekiQueryService.java`
* `services/semantic-core/src/test/java/org/projecta/semanticcore/FusekiQueryServiceProjectionTest.java`

## Testing

* Regression test verifies manual candidates without stored `rdfs:label`.
* Existing data exposes 3 Review Queue entries: `Requirement`, `Task`, and
  `ResearchFinding`.

## Additional Notes

The fix is backward-compatible with already committed notes and candidates.
