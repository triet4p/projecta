# Connector operator runbook

## Deployment boundary

The connector PostgreSQL service and evidence volume are separate from
Semantic Core. Run the standalone migration command before API replicas and
verify readiness. Local connector authorization is an experience-mode seam;
production mode must fail closed unless a separately reviewed principal
adapter is installed. JSON/Mock is not evidence of real-connector readiness.

## Diagnostics

Correlate the request ID/operation ID with the connector start and terminal
telemetry event. Expect one start and one terminal event per run attempt. Safe
telemetry contains connector type, hashed project scope, outcome, duration,
bounded event/replay counts, and no credentials, payloads, RDF, SQL, paths, or
internal resource identifiers. Audit rows cover installation lifecycle, run,
retry, and terminal outcome.

## Backup and restore

Use `scripts/connector_backup.py backup` with
`PROJECTA_CONNECTOR_BACKUP_DATABASE_URL` and
`PROJECTA_CONNECTOR_BACKUP_DATABASE_PASSWORD` environment variables. The tool
creates a versioned PostgreSQL dump, evidence archive, and manifest. Passwords
are never command-line arguments. Stop connector write traffic first, verify no
sync is running, and pass `--confirm-quiesced`; the tool refuses to claim a
cross-store backup without that explicit operator confirmation. Restore
requires `--confirm-isolated` and a clean isolated target; never point it at a
shared or production volume.

Run `scripts/connector_recovery_drill.py` against that isolated backup. Verify
installation revisions, cursor checkpoints, run terminal outcomes, evidence
metadata, and one explicit replay. The replay must not duplicate source,
candidate, assertion, or cursor advancement.

## Failure and reset

Database/evidence/Core outages, malformed adapter output, deadline expiry, and
dead-letter persistence failure must produce a correlated safe terminal state.
Do not enable automatic retries. Preserve the failed run and dead letter for
review; retry only after the dependency and revision are verified. Reset only
an isolated local fixture stack using its named volumes and migration path.
