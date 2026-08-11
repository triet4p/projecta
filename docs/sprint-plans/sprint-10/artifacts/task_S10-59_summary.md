# Task Summary: S10-59 — Isolated recovery drill

Added `connector_recovery_drill.py` to restore a version-checked backup into an
isolated root and verify unique evidence references. The backup tool now also
supports an explicitly configured PostgreSQL tool image when the host does not
have `pg_dump`/`pg_restore`; the database password remains environment-only.

The live drill used two isolated PostgreSQL 16.4 containers and verified the
restored installation, terminal run, cursor, evidence bytes/digest, one-run
cardinality, and replay outcome. The focused connector replay test additionally
proves that a replay does not invoke Semantic Core again or advance the cursor.

Testing: recovery contract tests passed; backup created with manifest version
`connector-backup.v1`; restore reported one evidence object; post-restore
verification reported `runRows=1`, `replayOutcome=replayed`,
`cursorRevision=1`, `cursorCheckpoint=cursor-1`, and 32 restored bytes.
