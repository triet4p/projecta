# Project Membership Runtime Contract — Sprint 11

Projecta owns the exact project and installation authorization decision. The
three approved roles are additive: `project-reader`, `reviewer`, and
`connector-admin`. A connector administrator is not implicitly a reviewer.

Every production project context is resolved from the authenticated session's
server-side selection and membership. Candidate validation/edit/confirmation/
rejection require reviewer capability. Connector operations resolve through the
production principal adapter and require the connector-admin role for writes.
Unknown or cross-project resources retain the existing safe not-found/forbidden
surface.

Membership provisioning is an idempotent operator CLI reading an untracked JSON
file. It is deliberately not an admin UI or a general tenant-management
product. Membership changes are revisioned; a cold recovery invalidates
Projecta sessions, requiring users to authenticate again.
