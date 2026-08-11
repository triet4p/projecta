# Connector operational migration boundary

**Contract:** `connector-operational-migrations.v1`
**Scope:** S10-12 through S10-19

Connector PostgreSQL schema changes run from the standalone
`projecta_api.operational.migrate upgrade` entry point. API replicas do not
run migrations during import or startup. Compose models this as the
`connector-migrate` one-shot service and gates the API on its successful
completion.

The runner requires the connector PostgreSQL host, database, user, and password
from deployment environment variables. It fails nonzero when configuration or
database readiness is unavailable. Alembic records the applied revision in its
own version table and takes a PostgreSQL advisory lock so two migration jobs
cannot apply the same revision concurrently.

The first revision creates only connector operational tables: installations,
event inbox/idempotency, runs and single attempts, cursors, dead letters, and
safe audit records. It stores no raw event body, evidence bytes, credential, or
RDF identifier.

Rollback boundary:

- application operations roll back their own short PostgreSQL transaction;
- a failed forward migration is transactional on PostgreSQL and leaves the
  previous applied revision intact;
- the application entry point intentionally exposes no downgrade command;
- destructive schema rollback requires a reviewed backup/restore or a
  forward-fix procedure in an isolated recovery workflow, and may not silently
  rewind semantic commits or source cursors.

Repeated `upgrade` is a no-op after the revision is recorded. Production
deployment must run the migration image/version explicitly before replicas and
must provide an immutable API image reference in the production Compose
override.
