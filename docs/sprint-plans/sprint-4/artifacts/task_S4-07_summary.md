# Task Summary: S4-07 — Extend the Semantic Core contract

**Sprint:** Sprint 4
**Task:** S4-07

## Summary of Work

Defined the private source/candidate ingestion operation, including trusted
inputs, server-owned identifiers and graph routing, atomic writes, replay
semantics, failures, and downstream test requirements.

## Files Modified

- `docs/architecture/semantic-core-ingestion-api.md` — ingestion contract.

## Testing

- **Test File:** Not applicable; this is a pre-implementation contract.
- **Status:** Cross-checked with named-graph and lifecycle contracts; released
  ontology regression passed (73/73).
- **Execution Command:** `docker compose run --build --rm ontology-test`

## Additional Notes

The operation deliberately does not expose Fuseki, graph IRIs, RDF, or SPARQL.
