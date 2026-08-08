"""Application service for redacted LLM profile lifecycle operations."""

from __future__ import annotations

from secrets import token_urlsafe
from time import monotonic
from urllib.parse import urlsplit

from projecta_api.configuration.audit import ConfigurationAudit
from projecta_api.configuration.errors import ConfigurationDisabled, ConfigurationProblem
from projecta_api.configuration.models import (
    ConnectionCheckResult,
    LLMProfile,
    LLMProfileRemove,
    LLMProfileWrite,
)
from projecta_api.configuration.ports import SecretStore
from projecta_api.configuration.storage import LLMProfileRepository
from projecta_api.context import TrustedRequestContext


class LLMConfigurationService:
    """Coordinate secret writes and non-secret metadata without partial activation."""

    def __init__(
        self,
        repository: LLMProfileRepository,
        secret_store: SecretStore,
        audit: ConfigurationAudit,
        *,
        runtime_mode: str,
    ) -> None:
        self._repository = repository
        self._secret_store = secret_store
        self._audit = audit
        self._runtime_mode = runtime_mode

    def read(self, context: TrustedRequestContext) -> LLMProfile | None:
        self._ensure_enabled()
        profile = self._repository.get_active(context.project_id)
        return profile.public_model() if profile else None

    def save(self, context: TrustedRequestContext, payload: LLMProfileWrite) -> LLMProfile:
        self._ensure_enabled()
        started = monotonic()
        _validate_url(str(payload.base_url), local=self._runtime_mode == "experience")
        _validate_model(payload.model)
        current = self._repository.get_active(context.project_id)
        if current is not None and payload.credential is None:
            if not current.secret_reference:
                raise ConfigurationProblem(
                    "CONFIGURATION_INVALID", "A credential is required for this profile."
                )
            secret_reference = current.secret_reference
        else:
            credential = payload.credential
            if credential is None:
                raise ConfigurationProblem(
                    "CONFIGURATION_INVALID", "A credential is required for a new profile."
                )
            secret_reference = self._secret_store.create(credential)
        try:
            stored = self._repository.upsert(
                scope=context.project_id,
                profile_id=current.profile_id if current else f"profile_{token_urlsafe(12)}",
                provider_type=payload.provider_type,
                base_url=str(payload.base_url),
                model=payload.model,
                secret_reference=secret_reference,
                expected_revision=payload.expected_revision,
            )
        except Exception:
            if current is None or payload.credential is not None:
                self._secret_store.delete(secret_reference)
            self._audit.record(
                scope=context.project_id,
                actor_id=context.actor_id,
                request_id=context.request_id,
                operation="write",
                outcome="failed",
                provider_type=payload.provider_type,
                base_url=str(payload.base_url),
                revision_before=current.revision if current else None,
                latency_ms=_elapsed_ms(started),
            )
            raise
        if current and current.secret_reference and current.secret_reference != secret_reference:
            self._secret_store.delete(current.secret_reference)
        self._audit.record(
            scope=context.project_id,
            actor_id=context.actor_id,
            request_id=context.request_id,
            operation="write",
            outcome="success",
            provider_type=stored.provider_type,
            base_url=stored.base_url,
            revision_before=current.revision if current else None,
            revision_after=stored.revision,
            latency_ms=_elapsed_ms(started),
        )
        return stored.public_model()

    def rotate(self, context: TrustedRequestContext, payload: LLMProfileWrite) -> LLMProfile:
        """Require a replacement credential and an explicit profile revision."""
        if payload.credential is None:
            raise ConfigurationProblem("CONFIGURATION_INVALID", "A replacement credential is required.")
        if payload.expected_revision is None:
            raise ConfigurationProblem("CONFIGURATION_INVALID", "expectedRevision is required for rotation.")
        return self.save(context, payload)

    def remove(self, context: TrustedRequestContext, payload: LLMProfileRemove) -> LLMProfile | None:
        self._ensure_enabled()
        started = monotonic()
        prior = self._repository.remove(context.project_id, payload.expected_revision)
        if prior is not None:
            self._secret_store.delete(prior.secret_reference)
        self._audit.record(
            scope=context.project_id,
            actor_id=context.actor_id,
            request_id=context.request_id,
            operation="remove",
            outcome="success",
            provider_type=prior.provider_type if prior else None,
            base_url=prior.base_url if prior else None,
            revision_before=prior.revision if prior else None,
            revision_after=(prior.revision + 1) if prior else None,
            latency_ms=_elapsed_ms(started),
        )
        return None

    def record_connection_check(
        self, context: TrustedRequestContext, revision: str, result: ConnectionCheckResult
    ) -> None:
        """Persist health only when the checked snapshot is still active."""
        if not revision.isdigit():
            return
        self._repository.update_health(
            context.project_id,
            int(revision),
            result.status,
            result.checked_at,
        )

    def _ensure_enabled(self) -> None:
        if self._runtime_mode != "experience":
            raise ConfigurationDisabled()


def _validate_url(value: str, *, local: bool) -> None:
    parsed = urlsplit(value)
    if parsed.scheme not in ({"http", "https"} if local else {"https"}) or not parsed.hostname:
        raise ConfigurationProblem("CONFIGURATION_INVALID", "The provider URL is not allowed.")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ConfigurationProblem("CONFIGURATION_INVALID", "The provider URL contains unsafe components.")


def _validate_model(value: str) -> None:
    if any(character.isspace() or ord(character) < 32 for character in value):
        raise ConfigurationProblem("CONFIGURATION_INVALID", "The model identifier is not allowed.")


def _elapsed_ms(started: float) -> int:
    return int((monotonic() - started) * 1000)
