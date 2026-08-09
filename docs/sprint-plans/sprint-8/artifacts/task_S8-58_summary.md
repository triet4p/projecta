# Task Summary: S8-58 — Structured candidate editing

**Status:** Complete

Added finite correction fields for type, label, relation, entity link, date, and
assignment. Each edit is schema-validated, revisioned, project-scoped, stored
as an immutable operational audit, and returned with actor/request/time
provenance. Entity links and assignments are selected from bounded labeled
options rather than typed as opaque handles. Review validation returns the
audited correction revision; confirmation rejects stale revisions and applies
the validated Requirement label/type/date instead of confirming the original
candidate silently.

Deferred fields remain source/candidate workflow metadata; no unapproved RDF
assignment, deadline, or generic Note status term is written.
