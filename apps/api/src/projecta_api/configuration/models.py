"""Provider-neutral runtime configuration models.

The persisted profile model intentionally contains metadata only. The resolved
snapshot carries a SecretStr for server-side gateway composition and is not a
browser/API response model.
"""

from dataclasses import dataclass
from typing import Literal

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, SecretStr

LLMProviderType = Literal["openai-response", "openai"]


class LLMProfile(BaseModel):
    """Non-secret interactive profile metadata suitable for persistence."""

    model_config = ConfigDict(extra="forbid")

    profile_id: str = Field(alias="profileId", min_length=1, max_length=128)
    provider_type: LLMProviderType = Field(alias="providerType")
    base_url: AnyHttpUrl = Field(alias="baseUrl")
    model: str = Field(min_length=1, max_length=128)
    active: bool = True
    revision: int = Field(ge=1)
    credential_configured: bool = Field(alias="credentialConfigured")
    health: Literal["unknown", "healthy", "unhealthy", "unavailable"] = "unknown"
    last_checked_at: str | None = Field(default=None, alias="lastCheckedAt")
    created_at: str | None = Field(default=None, alias="createdAt")
    updated_at: str | None = Field(default=None, alias="updatedAt")
    secret_reference: str | None = Field(
        default=None,
        alias="secretReference",
        exclude=True,
        repr=False,
    )


@dataclass(frozen=True, slots=True)
class LLMConfigurationSnapshot:
    """Server-only immutable configuration used for one gateway composition."""

    provider_type: LLMProviderType
    base_url: str
    model: str
    api_key: SecretStr
    revision: str

    def redacted_profile(self) -> LLMProfile:
        """Return metadata safe for a future settings read response."""
        return LLMProfile(
            profileId=f"runtime-{self.revision}",
            providerType=self.provider_type,
            baseUrl=AnyHttpUrl(self.base_url),
            model=self.model,
            active=True,
            revision=1,
            credentialConfigured=bool(self.api_key.get_secret_value()),
            health="unknown",
        )


class LLMProfileWrite(BaseModel):
    """Validated settings mutation payload; the credential is write-only."""

    model_config = ConfigDict(extra="forbid")

    provider_type: LLMProviderType = Field(alias="providerType")
    base_url: AnyHttpUrl = Field(alias="baseUrl")
    model: str = Field(min_length=1, max_length=128)
    credential: SecretStr | None = Field(default=None, repr=False)
    expected_revision: int | None = Field(default=None, alias="expectedRevision", ge=1)


class LLMProfileRemove(BaseModel):
    """Explicit remove confirmation and optional optimistic revision."""

    model_config = ConfigDict(extra="forbid")

    expected_revision: int | None = Field(default=None, alias="expectedRevision", ge=1)
    confirm: Literal[True]


class ConnectionCheckResult(BaseModel):
    """Sanitized provider connectivity outcome."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["healthy", "unhealthy", "unavailable"]
    credential_configured: bool = Field(alias="credentialConfigured")
    detail: str
    checked_at: str = Field(alias="checkedAt")
