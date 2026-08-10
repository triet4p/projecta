# Task Summary: Project structured Notes into Graph

**Sprint:** Sprint 9 — Provider Runtime Truthfulness
**Task:** S9-11

## Summary of Work

Extended the bounded Graph projection to include committed `Note` and
`NoteItem` resources from the project source graph, together with their
`hasNoteItem` edges and explicit unverified/source-backed states.

## Files Modified

* `services/semantic-core/src/main/java/org/projecta/semanticcore/FusekiQueryService.java`
* `services/semantic-core/src/test/java/org/projecta/semanticcore/FusekiQueryServiceProjectionTest.java`

## Testing

* Semantic Core: `49 passed, 7 skipped`.
* Existing `Meeting 10/08` data: 7 Graph nodes and 6 edges through the public API.

## Additional Notes

No ontology vocabulary or persisted RDF was changed.
