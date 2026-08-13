# Sprint 11 Teams Ontology Reuse Audit — S11-13

**Status:** `G1_APPROVED`

**Task:** S11-13

**Semantic outcome proposed:** `NO_ONTOLOGY_CHANGE_REQUIRED`

## Competency questions

1. Can Projecta retain a bounded Teams message/reply as source evidence for a
   selected project?
2. Can the import produce a reviewable candidate with evidence and provenance?
3. Can a reviewer confirm an eligible candidate through the existing lifecycle?
4. Can the project-scoped retrieval surface show the resulting knowledge and
   evidence without provider-shaped public fields?
5. Can repeated, edited, deleted, or partially imported observations remain
   operationally idempotent without becoming new RDF vocabulary?
6. Can actor information remain a bounded external identity hint without
   automatically merging a Projecta `Person`?

## Reuse mapping

| Teams need | Released semantic/operational boundary | Result |
| --- | --- | --- |
| Source message/reply | Note/source capture and immutable evidence boundary | Reuse |
| Message body/span | Evidence content and bounded source offsets | Reuse |
| Candidate extraction | Existing extracted/validated/pending-review lifecycle | Reuse |
| Human confirmation | Existing candidate confirmation/provenance path | Reuse |
| Project scope | Existing project-scoped graphs and server policy | Reuse |
| Actor/display identity | Existing bounded actor hint/external identity handling; no auto-merge | Reuse |
| Event ID, cursor, revision, retry | PostgreSQL connector operational state | Keep outside RDF |
| Secret reference/token | Server-side `SecretStore` and PostgreSQL metadata | Keep outside RDF |
| Provider tenant/team/channel IDs | Internal installation/evidence metadata | Keep outside public/RDF domain vocabulary |
| Edit/delete/truncation outcome | Operational run/event outcome and evidence metadata | Keep outside RDF unless a future competency question requires otherwise |

## Semantic safety checks

- Teams content is source evidence, not asserted truth.
- The adapter cannot create `Requirement`, `Task`, `Person`, or any other
  asserted domain fact directly.
- Evidence, candidate, provenance, and project scope remain in their released
  graph/lifecycle boundaries.
- External display names are not identity authority.
- Operational connector state never enters RDF.
- No Teams-specific class, property, controlled individual, or graph name is
  introduced by this audit.

## Gap assessment

No current competency question requires a new ontology term. Cursor, edit,
delete, retry, dead-letter, installation, provider tenant, and secret concepts
are operational concerns already owned by PostgreSQL/evidence/secret
boundaries. A future requirement for graph-queryable external resources or
connector identity would require a new governed proposal.

## Proposed conclusion

`NO_ONTOLOGY_CHANGE_REQUIRED` is approved for the Sprint 11 scope. This is
not a release of a new ontology version. Any future requirement for vocabulary
must stop dependent implementation and invoke
`projecta-evolve-ontology` with competency questions, shapes, migration, and
human semantic approval.

## References

- [Ontology design](../initialization/05-Ontology-Design.md)
- [Sprint 10 connector reuse decision](../../.agents/memory/decisions.md)
- [Sprint 10 ontology reuse-gap audit](sprint-10-connector-reuse-gap.md)
