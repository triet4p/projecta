# S8-27 summary

Implemented `ProjectWorkspaceQueryService` and the private Semantic Core
catalog route. The query accepts only a finite server-owned allowlist, queries
each project's named graphs, derives bounded counts/activity/freshness, and
sorts by status, normalized name, and stable project identifier. It does not
accept arbitrary filters, graph IRIs, or client SPARQL.

Validation: `mvn --batch-mode -Dtest=ProjectWorkspaceQueryServiceTest test`
passed (2 tests).
