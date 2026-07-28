# Task Summary: S1-09 — Add Ontology Metadata

**Sprint:** Sprint 1 — Ontology Kernel
**Task:** S1-09 — Add Ontology Metadata

## Summary of Work

Completed ontology metadata for both Turtle modules per the approved namespace policy (S1-04/S1-05). Ensured every term has `rdfs:label` and `rdfs:comment`, the ontology IRI carries full version and provenance metadata, and the module structure supports offline Jena loading.

**core.ttl changes:**
- Added `rdfs:comment` with a one-sentence summary of the Sprint 1 kernel scope.
- Added `dcterms:description` with a paragraph covering what the ontology includes and explicitly excludes (SHACL, rules, extraction, connectors).
- Added `rdfs:seeAlso` linking to the term inventory document for human readers.
- Unified label to "Projecta Ontology — Sprint 1 Kernel" (removed "Core" to reflect it's the shared root).

**communication.ttl changes:**
- Replaced the broken `owl:imports` (self-referential — `v/0.1/` importing `v/0.1/core` when core also uses `v/0.1/`) with a full metadata block matching the namespace policy template.
- Added `a owl:Ontology`, `owl:versionIRI`, `owl:versionInfo`, `rdfs:label`, `rdfs:comment`, `dcterms:created`, `dcterms:creator`.
- Added a structural comment explaining both files are co-members of the same ontology graph, loaded together not imported.
- Added `dcterms:` prefix for metadata properties.

**New file: `infra/docker/fuseki/config/location-mapping.ttl`** — Jena `FileManager` mapping for offline IRI resolution. Maps the ontology IRI to local file paths. Includes commented-out PROV-O mapping for future offline use.

## Files Modified

- [ontology/core.ttl](../../../../ontology/core.ttl) — Extended ontology metadata block with `rdfs:comment`, `dcterms:description`, `rdfs:seeAlso`.
- [ontology/communication.ttl](../../../../ontology/communication.ttl) — Replaced broken `owl:imports` with full metadata block.
- [infra/docker/fuseki/config/location-mapping.ttl](../../../../infra/docker/fuseki/config/location-mapping.ttl) — New file: Jena offline resolution mapping.

## Testing

- **Parse result:** Both files pass `rdflib` Turtle parsing.
- **Metadata verification:**
  - `owl:versionIRI`: present (1 value) ✓
  - `owl:versionInfo`: "0.1.0" ✓
  - `rdfs:label` on ontology: 2 values (one per module) ✓
  - `dcterms:description`: present ✓
  - `dcterms:created`: "2026-07-28" ✓
  - `rdfs:seeAlso`: links to term inventory ✓
  - 27 terms with `rdfs:label` (9 classes + 6 obj props + 3 data props + 9 individuals) ✓
  - 27 terms with `rdfs:comment` ✓
  - 117 total triples (was 113 in S1-08; +4 metadata triples) ✓
- **Execution command:** `uv run --with rdflib python -c "g = rdflib.Graph(); g.parse('ontology/core.ttl', format='turtle'); g.parse('ontology/communication.ttl', format='turtle')"`
- **Checks not run:** Jena `riot --validate` (Jena CLI not yet installed); OWL profile check (no OWL reasoner configured).

## Additional Notes

- The module structure uses **co-membership, not imports**: both files declare the same ontology IRI (`v/0.1/`) and are loaded together. This avoids the self-referential `owl:imports` that existed in S1-08's communication.ttl. When Sprint 2 adds more modules (`project.ttl`, `work.ttl`), the same pattern applies — or a proper import hierarchy can be introduced.
- `dcterms:license` is not yet declared — this is a governance decision requiring human input. Flagged for the reviewer.
- The `rdfs:seeAlso` link uses a `https://w3id.org/projecta/docs/` IRI that is not yet registered — this is a forward reference, acceptable for a dev/snapshot version.
