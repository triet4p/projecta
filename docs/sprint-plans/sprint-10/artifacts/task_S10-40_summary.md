# Task Summary: S10-40 — Commit connector sources through Semantic Core

Added `ConnectorSemanticSourceCommitter`, which reads immutable evidence with
a 1 MiB bound, maps it to the existing capture contract, and calls the
project-scoped `SemanticCoreClient.capture` boundary. No connector adapter
writes RDF or bypasses Semantic Core.

Testing: source-mapping/committer tests and Semantic Core compile/test passed.
