# S8-28 summary

Added the Semantic Core project overview query and private route. It returns
one trusted project with current requirements, questions, tasks, blockers,
risks, recent notes, pending candidates, and evidence coverage. Collections
are bounded and labels/handles are server-derived; the route rejects a path
project that differs from the trusted project context.

Validation: the overview path is covered by
`ProjectWorkspaceQueryServiceTest` and the query module's 2-test targeted run
passed.
