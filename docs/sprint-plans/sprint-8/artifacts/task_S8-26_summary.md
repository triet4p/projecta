# S8-26 summary

## Outcome

Defined the Sprint 8 project workspace read model in
`docs/architecture/project-workspace-read-model.md`.

The contract establishes server-derived catalog projections, opaque navigation
handles, bounded counts/activity/freshness, deterministic ordering, explicit
empty-domain behavior, server-owned selection revisions, and distinct
catalog/selection errors. It also binds the same selected project scope across
overview, graph, notes, candidates, evidence, Q&A, diagnostics, and logs.

## Validation

- `git diff --check` passed.
- Markdown was checked against `.agents/rules/markdown.md`; lists and tables
  have explicit blank-line separation.

## Risks / follow-up

S8-27 through S8-30 implement the Semantic Core query, typed API boundary, and
server-side selection adapter described here. No ontology or production
authorization claim is introduced by this read-model definition.
