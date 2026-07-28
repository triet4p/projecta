# Task Summary: S1-04 — Propose Namespace Policy

**Sprint:** Sprint 1 — Ontology Kernel
**Task:** S1-04 — Propose Namespace Policy

## Summary of Work

Proposed a comprehensive namespace policy for the Projecta ontology covering all conventions needed for Sprint 1 implementation. The proposal covers:

- **Base IRI:** `https://w3id.org/projecta/ontology/` — using w3id.org for persistent, redirectable URIs without requiring domain ownership. Two alternatives (purl.org, projecta.dev) were considered and rejected with rationale.
- **Prefix:** `projecta:` for all vocabulary terms in Sprint 1, with module sub-namespaces deferred to Sprint 2. Standard prefix set declared (rdf, rdfs, owl, xsd, sh, prov).
- **Naming conventions:** PascalCase for classes, camelCase for properties, kebab-case for individuals and rules, `<ClassName>Shape` for SHACL shapes. Explicitly supersedes the `UPPER_SNAKE` placeholder convention from the Ontology Design document.
- **Version IRI:** `https://w3id.org/projecta/ontology/v/{MAJOR}.{MINOR}/` with `dev/` for the working copy. MAJOR.MINOR.PATCH semantics defined.
- **Named graph IRIs:** Mapped the existing named graph model from Ontology Design §8 to concrete IRIs under the new base.
- **Instance data prefix:** `projecta-data:` → `https://w3id.org/projecta/data/` with project-scoped pattern `/project/{id}/{entity-type}/{local-id}`.
- **Migration:** `brse:` placeholder prefix in existing docs is explicitly superseded by `projecta:`.

## Files Modified

- [docs/ontology/namespace-policy.md](../../../../docs/ontology/namespace-policy.md) — New file: full namespace policy proposal with base IRI, prefixes, naming conventions, version IRI pattern, named graph structure, and migration notes.

## Testing

- **Test Type:** Policy review (no automated test — namespace policy is a governance document, enforced by human review and future CI linting).
- **Validation Performed:**
  - Verified the base IRI follows W3C best practices for ontology publication.
  - Verified naming conventions are internally consistent and align with common RDF/OWL community practice (Dublin Core, FOAF, Schema.org).
  - Verified the version IRI pattern is compatible with Jena's ontology loading (Jena resolves `owl:versionIRI` as a standard IRI — no special handling needed).
  - Verified the named graph IRIs are compatible with the paths already specified in Ontology Design §8.
  - Verified the prefix `projecta:` does not conflict with any registered prefix at prefix.cc.
  - Cross-referenced against the module structure in [Ontology Design §3](../../../../docs/initialization/05-Ontology-Design.md#3-ontology-modules) and file layout in §13.
  - Cross-referenced against the Sprint 1 scope — only `core` and `communication` terms are needed, so a single namespace is sufficient.
- **Status:** Awaiting human approval (→ S1-05 `$log-decision`).

## Additional Notes

- The `projecta-data:` prefix for instance data is introduced early even though only the demo graph (S1-10) will use it. This avoids renaming instance IRIs later when real data arrives.
- `w3id.org` requires a registration pull request to create the redirect. The `.htaccess` file can point to GitHub Pages or a dedicated documentation site. This registration step is deferred until the first release (Sprint 1 completion).
- Module-specific prefixes (`core:`, `comm:`, `work:`, etc.) are intentionally deferred — premature modularization of the namespace creates friction during the kernel phase. The single `projecta:` prefix keeps authoring and querying simple.
