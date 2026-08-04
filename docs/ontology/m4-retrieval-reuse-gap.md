# M4 Released-Contract Reuse and Gap Audit

## Reuse

`Requirement`, `Task`, `Question`, `blocks`, `implements`, `supersededBy`,
`validFrom`, `validTo`, `belongsToProject`, PROV-O, and the five project graphs
already exist in v0.4/v0.3. They cover current facts, temporal history, evidence,
and project isolation.

## Additive governed gap

M4 needs explicit status values for retrieval (`Open`, `Blocked`) and rule output
identifiers/version plus derivation links. These are not new domain facts: they
make already-defined inferred outcomes auditable. The additive module
`ontology/m4-retrieval.ttl`, its shapes, rules, fixtures, and competency queries
provide those terms without changing released IRIs or requiring migration.

## Compatibility

Existing v0.1–v0.4 graphs remain valid. New shapes target only v0.5 M4 derived
resources. Candidate and asserted graphs are untouched; inference is rebuildable.
