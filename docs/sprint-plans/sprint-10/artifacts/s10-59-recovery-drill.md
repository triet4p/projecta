# S10-59 recovery drill evidence

The drill ran on 2026-08-10 against two explicitly named temporary PostgreSQL
16.4 containers:

- source: `projecta-s10-59-postgres`, host port `55439`
- restore: `projecta-s10-59-restore-postgres`, host port `55440`

The source stack was migrated, seeded with one `json-mock` installation, one
accepted run, one accepted event, cursor `cursor-1`, and one evidence object.
`connector_backup.py backup` produced manifest version `connector-backup.v1`.
`connector_recovery_drill.py restore --confirm-isolated` restored one evidence
object into the separate restore root and database.

Post-restore assertions:

- installation revision: `1`
- terminal run rows: `1`, outcome: `accepted`
- cursor revision/checkpoint: `1` / `cursor-1`
- evidence: `32` bytes, original SHA-256 preserved
- replay of `event-recovery`: `replayed`
- run cardinality remained `1`; replay did not advance the cursor

The connector kernel replay test separately observed one source capture call and
one cursor advancement across first delivery plus replay, covering the semantic
source/candidate/assertion no-duplication boundary. The temporary containers and
directories were explicitly removed after verification.
