# M4 Retrieval Baseline Benchmark

The bounded vertical slice compares service-authored SPARQL, full-text indexing,
and vector retrieval against the same synthetic M4 dataset.

| Path | Recall | Isolation | Rebuild cost | Operational complexity |
|---|---:|---|---|---|
| Service-authored SPARQL | 1.00 | Strong named-graph boundary | Low | Low |
| Full-text index | 0.86 | Requires post-filtering | Medium | Medium |
| Vector index | 0.79 | Requires post-filtering | High | High |

At the bounded dataset size, exact graph predicates already answer the supported
questions. Fuseki-only is therefore the Sprint 6 technology baseline; an external
index remains a future rebuildable optimization and is not a source of truth.
