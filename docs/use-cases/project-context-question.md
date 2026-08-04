# Project Context Question — M4 Executable Boundary

## Use case

Given a trusted project-scoped question, Projecta interprets only three supported
intents: current requirements, requirement history, and unresolved blockers. It
executes a versioned Semantic Core query, maps the rows into a typed projection,
and returns a grounded answer with opaque citations, knowledge status, freshness,
and rule derivations. The application never accepts caller-supplied SPARQL,
graph IRIs, tenant IDs, or arbitrary filters.

## Contract

- Input: non-empty question, trusted `projectId`, `actorId`, and `requestId`.
- Output: `answerVersion=m4.v1`, `queryVersion=m4.v1`, intent/query ID,
  structured facts, citations, `asserted`/`inferred` status, as-of metadata,
  derivations, and explicit `complete`/`abstained` state.
- Empty results are complete with zero facts; ambiguity, no evidence, stale
  projection, inaccessible scope, and dependency failures are distinct errors.
- Limits are 1–100 and ordering is stable by effective time then opaque ID.
- The request path is read-only and has no semantic mutation side effect.

## Acceptance scenarios

1. “What changed in the checkout requirement?” returns the supersession chain,
   both requirement versions, transition evidence, and confirmation actors.
2. “What is blocking checkout?” returns open questions/dependencies and the
   task they block; when none exist it returns an explicit empty result.
3. A question naming another project, an unsupported filter, or an arbitrary
   query is rejected without revealing whether the foreign entity exists.

## Latency assumption

The bounded Fuseki-only path is expected to complete within 2 seconds at the
vertical-slice dataset size. The response carries elapsed milliseconds so a
future projection can be compared without changing truth semantics.
