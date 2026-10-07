"""Scoped native-only project purge exception for projecta-deletion.v1.

Revision ID: 0012_project_purge_exception
Revises: 0011_review_receipts_append_only

Approved policy: docs/sprint-plans/sprint-14/project-data-deletion-contract.md
§4.2 (owner-approved 2026-10-06, `.agents/memory/decisions.md`). This migration
creates ONE constrained helper, ``projecta_purge_project_scope``, that deletes
exactly one confirmed ``project_id`` scope from the two trigger-guarded history
tables. It is the only code path allowed to remove guarded rows.

Invariant (also enforced by the API purge service, never by session flags):

- named-trigger-only: inside its own transaction the helper disables ONLY the
  two named row triggers (``review_decision_receipts_append_only``,
  ``correction_burden_events_append_only``) and re-enables them before commit.
  No ``session_replication_role`` change, no global trigger drop, no other
  table touched.
- single-scope: the helper refuses an empty/missing predicate and refuses when
  the predicate would match no guarded row at all (fail closed); the caller
  (``ProjectDeletionService``) additionally asserts the scope is the explicitly
  confirmed project.
- ordinary guards unchanged: after the helper commits, both triggers exist and
  an ordinary ``UPDATE``/``DELETE`` on either table raises exactly as before.
  Concurrent writers serialize on the API fence + the helper's row locks; a
  concurrent ordinary write to the same rows blocks until commit, then sees
  zero rows (never a half-purged scope).
- rollback: any failure before commit rolls the whole purge transaction back,
  triggers included (``ALTER TABLE ... DISABLE/ENABLE TRIGGER`` is
  transactional), so a failed purge leaves guards enforcing and rows intact.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_project_purge_exception"
down_revision: str | None = "0011_review_receipts_append_only"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PURGE_FUNCTION = """
CREATE OR REPLACE FUNCTION projecta_purge_project_scope(target_project_id TEXT)
RETURNS TABLE(purged_table TEXT, purged_rows BIGINT)
LANGUAGE plpgsql
AS $$
DECLARE
    receipt_count BIGINT := 0;
    correction_count BIGINT := 0;
BEGIN
    IF target_project_id IS NULL OR target_project_id = '' THEN
        RAISE EXCEPTION 'project purge scope must be an explicit project id';
    END IF;
    IF target_project_id !~ '^[a-z0-9][a-z0-9-]{0,62}$' THEN
        RAISE EXCEPTION 'project purge scope is not a valid project id';
    END IF;
    SELECT count(*) INTO receipt_count
    FROM review_decision_receipts WHERE project_id = target_project_id;
    SELECT count(*) INTO correction_count
    FROM correction_burden_events WHERE project_id = target_project_id;
    IF receipt_count = 0 AND correction_count = 0 THEN
        RAISE EXCEPTION 'project purge scope matches no guarded history rows';
    END IF;
    -- Transaction-local named-trigger-only window. Both statements run inside
    -- the caller's purge transaction; any error rolls guards and rows back.
    ALTER TABLE review_decision_receipts DISABLE TRIGGER review_decision_receipts_append_only;
    ALTER TABLE correction_burden_events DISABLE TRIGGER correction_burden_events_append_only;
    BEGIN
        DELETE FROM review_decision_receipts WHERE project_id = target_project_id;
        GET DIAGNOSTICS receipt_count = ROW_COUNT;
        DELETE FROM correction_burden_events WHERE project_id = target_project_id;
        GET DIAGNOSTICS correction_count = ROW_COUNT;
    EXCEPTION WHEN OTHERS THEN
        ALTER TABLE review_decision_receipts ENABLE TRIGGER review_decision_receipts_append_only;
        ALTER TABLE correction_burden_events ENABLE TRIGGER correction_burden_events_append_only;
        RAISE;
    END;
    ALTER TABLE review_decision_receipts ENABLE TRIGGER review_decision_receipts_append_only;
    ALTER TABLE correction_burden_events ENABLE TRIGGER correction_burden_events_append_only;
    -- Verify guards are enforcing again before the caller may commit.
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger
        WHERE tgname = 'review_decision_receipts_append_only' AND tgenabled = 'O'
    ) OR NOT EXISTS (
        SELECT 1 FROM pg_trigger
        WHERE tgname = 'correction_burden_events_append_only' AND tgenabled = 'O'
    ) THEN
        RAISE EXCEPTION 'project purge guard verification failed';
    END IF;
    RETURN QUERY VALUES ('review_decision_receipts', receipt_count), ('correction_burden_events', correction_count);
END;
$$;
"""


def upgrade() -> None:
    op.execute(_PURGE_FUNCTION)
    op.execute("COMMENT ON FUNCTION projecta_purge_project_scope(TEXT) IS 'projecta-deletion.v1 scoped purge exception: deletes exactly one confirmed project scope from guarded history; ordinary UPDATE/DELETE guards stay enforcing outside this helper'")
    # Existing databases must keep enforcing guards outside the helper.
    rows = op.get_bind().execute(
        sa.text(
            "SELECT count(*) FROM pg_trigger WHERE tgname IN "
            "('review_decision_receipts_append_only', 'correction_burden_events_append_only') "
            "AND tgenabled = 'O'"
        )
    ).scalar_one()
    if rows != 2:
        raise RuntimeError("append-only guard verification failed during purge-exception migration")


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS projecta_purge_project_scope(TEXT)")
