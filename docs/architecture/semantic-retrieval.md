# M4 Semantic Retrieval Contract

`m4.v1` exposes only service-authored query templates:

| Query ID | Purpose | Parameters |
|---|---|---|
| `current-requirements` | effective asserted requirements | `limit` |
| `requirement-history` | supersession/validity chain | `requirementId`, `limit` |
| `unresolved-blockers` | open questions/dependencies blocking work | `limit` |

Parameters are typed, bounded, and project-bound by `TrustedProjectContext`.
Unknown IDs, extra parameters, graph IRIs, project overrides, and arbitrary
SPARQL are rejected before Fuseki access. Result rows use opaque IDs and never
contain raw storage paths. The response includes `queryVersion`, `projectionVersion`,
`sourceRevision`, `asOf`, `partial`, and `stale`.

The three deterministic M4 rules are `m4.unresolved-dependency.v1`,
`m4.delivery-risk.v1`, and `m4.impact-review.v1`. They read asserted data only,
write only the project inferred/provenance graphs, and replace the inferred
snapshot atomically. Failed rebuilds leave the previous snapshot unchanged.

Freshness is governed independently of whether an inferred result row exists.
Each project has an `InferenceSnapshot` marker carrying the asserted
`sourceRevision` and rule version. The source revision is a SHA-256 digest of
the sorted asserted RDF terms, so same-count mutations are detected; the API
also returns a `materializationRevision` for the inferred and provenance
graphs. Rebuild execution time is operational response metadata and is not
written into deterministic derivation activities.
