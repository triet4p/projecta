"""Persistence ports and adapters for sessions and additive project roles."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from threading import RLock

from sqlalchemy import Engine, text

from projecta_api.identity.models import LoginAttempt, MembershipRecord, ProjectRole, SessionRecord
from projecta_api.operational.audit import SecurityAuditSink, emit_safe


class IdentityRepository:
    """Persistence contract deliberately smaller than a tenant-admin product."""

    def save_login_attempt(self, attempt: LoginAttempt) -> None: ...

    def consume_login_attempt(self, state: str, now: datetime) -> LoginAttempt | None: ...

    def save_session(self, session: SessionRecord) -> None: ...

    def get_session(self, session_id: str, now: datetime) -> SessionRecord | None: ...

    def revoke_session(self, session_id: str, now: datetime) -> None: ...

    def revoke_all_sessions(self, now: datetime) -> int: ...

    def memberships(self, subject: str) -> tuple[MembershipRecord, ...]: ...

    def remove_membership(self, subject: str, project_id: str) -> None: ...

    def remove_memberships_for_project(self, project_id: str) -> int:
        """Remove every authorization grant for one deleted project scope."""
        ...

class InMemoryIdentityRepository:
    """Deterministic adapter for unit tests and explicitly non-production modes."""

    def __init__(self, audit_sink: SecurityAuditSink | None = None) -> None:
        self._lock = RLock()
        self.attempts: dict[str, LoginAttempt] = {}
        self.sessions: dict[str, SessionRecord] = {}
        self._memberships: dict[tuple[str, str], MembershipRecord] = {}
        self._audit_sink = audit_sink

    def save_login_attempt(self, attempt: LoginAttempt) -> None:
        with self._lock:
            self.attempts[attempt.state] = attempt

    def consume_login_attempt(self, state: str, now: datetime) -> LoginAttempt | None:
        with self._lock:
            attempt = self.attempts.pop(state, None)
        if attempt is None or attempt.expires_at <= now:
            return None
        return attempt

    def save_session(self, session: SessionRecord) -> None:
        with self._lock:
            self.sessions[session.session_id] = session

    def get_session(self, session_id: str, now: datetime) -> SessionRecord | None:
        with self._lock:
            session = self.sessions.get(session_id)
        if session is None or session.revoked_at is not None or session.expires_at <= now:
            return None
        return session

    def revoke_session(self, session_id: str, now: datetime) -> None:
        with self._lock:
            current = self.sessions.get(session_id)
            if current is not None and current.revoked_at is None:
                self.sessions[session_id] = SessionRecord(
                    session_id=current.session_id,
                    subject=current.subject,
                    actor_id=current.actor_id,
                    tenant_id=current.tenant_id,
                    expires_at=current.expires_at,
                    created_at=current.created_at,
                    revoked_at=now,
                    csrf_token=current.csrf_token,
                    session_epoch=current.session_epoch,
                )

    def revoke_all_sessions(self, now: datetime) -> int:
        count = 0
        with self._lock:
            for key, current in tuple(self.sessions.items()):
                if current.revoked_at is None:
                    self.sessions[key] = SessionRecord(
                        session_id=current.session_id,
                        subject=current.subject,
                        actor_id=current.actor_id,
                        tenant_id=current.tenant_id,
                        expires_at=current.expires_at,
                        created_at=current.created_at,
                        revoked_at=now,
                        csrf_token=current.csrf_token,
                        session_epoch=current.session_epoch,
                    )
                    count += 1
        return count

    def memberships(self, subject: str) -> tuple[MembershipRecord, ...]:
        with self._lock:
            return tuple(item for (owner, _), item in self._memberships.items() if owner == subject)

    def replace_membership(self, subject: str, project_id: str, roles: Iterable[ProjectRole]) -> MembershipRecord:
        values = tuple(dict.fromkeys(roles))
        if not values or any(role not in ("project-reader", "reviewer", "connector-admin") for role in values):
            raise ValueError("membership roles must be one or more approved roles")
        current = self._memberships.get((subject, project_id))
        result = MembershipRecord(subject, project_id, values, (current.revision + 1) if current else 1, datetime.now(UTC))
        with self._lock:
            self._memberships[(subject, project_id)] = result
        emit_safe(self._audit_sink, category="membership", action="membership.replace", outcome="changed", correlation_id="membership-revision", project_id=project_id, actor_id=subject, revision=result.revision)
        return result

    def remove_membership(self, subject: str, project_id: str) -> None:
        with self._lock:
            self._memberships.pop((subject, project_id), None)
        emit_safe(self._audit_sink, category="membership", action="membership.remove", outcome="changed", correlation_id="membership-revision", project_id=project_id, actor_id=subject)

    def remove_memberships_for_project(self, project_id: str) -> int:
        with self._lock:
            doomed = [key for key in self._memberships if key[1] == project_id]
            for key in doomed:
                del self._memberships[key]
        emit_safe(self._audit_sink, category="membership", action="membership.remove-scope", outcome="changed", correlation_id="membership-revision", project_id=project_id, actor_id="")
        return len(doomed)


class PostgresIdentityRepository:
    """Production adapter using the existing Projecta PostgreSQL service.

    Keycloak uses a separate database/user in that same PostgreSQL service; this
    repository uses the Projecta application credentials and never shares them
    with the identity provider.
    """

    def __init__(self, engine: Engine, audit_sink: SecurityAuditSink | None = None) -> None:
        self.engine = engine
        self._audit_sink = audit_sink

    def save_login_attempt(self, attempt: LoginAttempt) -> None:
        with self.engine.begin() as connection:
            connection.execute(text("""
                INSERT INTO projecta_oidc_login_attempts
                    (state, nonce, code_verifier, return_path, created_at, expires_at, correlation_id)
                VALUES (:state, :nonce, :verifier, :return_path, :created_at, :expires_at, :correlation_id)
                ON CONFLICT (state) DO UPDATE SET nonce=EXCLUDED.nonce,
                    code_verifier=EXCLUDED.code_verifier, return_path=EXCLUDED.return_path,
                    created_at=EXCLUDED.created_at, expires_at=EXCLUDED.expires_at,
                    correlation_id=EXCLUDED.correlation_id
            """), {"state": attempt.state, "nonce": attempt.nonce, "verifier": attempt.code_verifier,
                   "return_path": attempt.return_path, "created_at": attempt.created_at,
                   "expires_at": attempt.expires_at, "correlation_id": attempt.correlation_id})

    def consume_login_attempt(self, state: str, now: datetime) -> LoginAttempt | None:
        with self.engine.begin() as connection:
            row = connection.execute(text("""
                DELETE FROM projecta_oidc_login_attempts
                WHERE state = :state AND expires_at > :now
                RETURNING state, nonce, code_verifier, return_path, created_at, expires_at, correlation_id
            """), {"state": state, "now": now}).mappings().one_or_none()
        return None if row is None else LoginAttempt(str(row["state"]), str(row["nonce"]), str(row["code_verifier"]), str(row["return_path"]), row["created_at"], row["expires_at"], str(row["correlation_id"]))

    def save_session(self, session: SessionRecord) -> None:
        with self.engine.begin() as connection:
            connection.execute(text("""
                INSERT INTO projecta_sessions
                    (session_id, subject, actor_id, tenant_id, expires_at, created_at, revoked_at, csrf_token, session_epoch)
                VALUES (:id, :subject, :actor, :tenant, :expires_at, :created_at, :revoked_at, :csrf, :epoch)
                ON CONFLICT (session_id) DO UPDATE SET revoked_at=EXCLUDED.revoked_at,
                    expires_at=EXCLUDED.expires_at, session_epoch=EXCLUDED.session_epoch
            """), {"id": session.session_id, "subject": session.subject, "actor": session.actor_id,
                   "tenant": session.tenant_id,
                   "expires_at": session.expires_at, "created_at": session.created_at,
                   "revoked_at": session.revoked_at, "csrf": session.csrf_token,
                   "epoch": session.session_epoch})

    def get_session(self, session_id: str, now: datetime) -> SessionRecord | None:
        with self.engine.begin() as connection:
            row = connection.execute(text("""
                SELECT session_id, subject, actor_id, tenant_id, expires_at, created_at, revoked_at, csrf_token, session_epoch
                FROM projecta_sessions
                WHERE session_id = :id AND expires_at > :now AND revoked_at IS NULL
            """), {"id": session_id, "now": now}).mappings().one_or_none()
        return None if row is None else SessionRecord(str(row["session_id"]), str(row["subject"]), str(row["actor_id"]), str(row["tenant_id"]) if row["tenant_id"] is not None else None, row["expires_at"], row["created_at"], row["revoked_at"], str(row["csrf_token"]), int(row["session_epoch"]))

    def revoke_session(self, session_id: str, now: datetime) -> None:
        with self.engine.begin() as connection:
            connection.execute(text("UPDATE projecta_sessions SET revoked_at = :now WHERE session_id = :id AND revoked_at IS NULL"), {"id": session_id, "now": now})

    def revoke_all_sessions(self, now: datetime) -> int:
        with self.engine.begin() as connection:
            result = connection.execute(text("UPDATE projecta_sessions SET revoked_at = :now WHERE revoked_at IS NULL"), {"now": now})
            return int(result.rowcount)

    def memberships(self, subject: str) -> tuple[MembershipRecord, ...]:
        with self.engine.begin() as connection:
            rows = connection.execute(text("SELECT subject, project_id, roles, revision, updated_at FROM projecta_project_memberships WHERE subject = :subject"), {"subject": subject}).mappings().all()
        return tuple(MembershipRecord(str(row["subject"]), str(row["project_id"]), tuple(row["roles"]), int(row["revision"]), row["updated_at"]) for row in rows)

    def replace_membership(self, subject: str, project_id: str, roles: Iterable[ProjectRole]) -> MembershipRecord:
        values = tuple(dict.fromkeys(roles))
        if not values or any(role not in ("project-reader", "reviewer", "connector-admin") for role in values):
            raise ValueError("membership roles must be one or more approved roles")
        with self.engine.begin() as connection:
            row = connection.execute(text("""
                INSERT INTO projecta_project_memberships(subject, project_id, roles, revision, updated_at)
                VALUES (:subject, :project_id, :roles, 1, CURRENT_TIMESTAMP)
                ON CONFLICT (subject, project_id) DO UPDATE SET roles=EXCLUDED.roles,
                    revision=projecta_project_memberships.revision + 1, updated_at=CURRENT_TIMESTAMP
                RETURNING subject, project_id, roles, revision, updated_at
            """), {"subject": subject, "project_id": project_id, "roles": list(values)}).mappings().one()
        result = MembershipRecord(str(row["subject"]), str(row["project_id"]), tuple(row["roles"]), int(row["revision"]), row["updated_at"])
        emit_safe(self._audit_sink, category="membership", action="membership.replace", outcome="changed", correlation_id="membership-revision", project_id=project_id, actor_id=subject, revision=result.revision)
        return result

    def remove_membership(self, subject: str, project_id: str) -> None:
        with self.engine.begin() as connection:
            connection.execute(text("DELETE FROM projecta_project_memberships WHERE subject = :subject AND project_id = :project_id"), {"subject": subject, "project_id": project_id})
        emit_safe(self._audit_sink, category="membership", action="membership.remove", outcome="changed", correlation_id="membership-revision", project_id=project_id, actor_id=subject)

    def remove_memberships_for_project(self, project_id: str) -> int:
        with self.engine.begin() as connection:
            result = connection.execute(text("DELETE FROM projecta_project_memberships WHERE project_id = :project_id"), {"project_id": project_id})
            removed = int(result.rowcount)
        emit_safe(self._audit_sink, category="membership", action="membership.remove-scope", outcome="changed", correlation_id="membership-revision", project_id=project_id, actor_id="")
        return removed
