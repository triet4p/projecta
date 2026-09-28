"""Immutable, project-scoped source-version and receipt custody primitives.

The legacy extraction request still accepts text directly.  This module is an
explicit opt-in boundary for callers that need immutable source custody before
anchoring or candidate creation.  It never stores source content in the
version or receipt objects.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from typing import Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

SOURCE_VERSION_CONTRACT_VERSION: Final = "source-version.v1"
CANONICALIZATION_VERSION: Final = "crlf-lf.v1"
COORDINATE_SYSTEM_VERSION: Final = "unicode-codepoint.v1"

RetentionPolicy = Literal["until-unreferenced", "indefinite", "owner-gated"]


class SourceVersionVerificationError(ValueError):
    """Raised when receipt custody, project scope, or replay identity fails."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


class RetentionMetadata(BaseModel):
    """Retention policy metadata that cannot delete referenced source history."""

    model_config = ConfigDict(extra="forbid")

    policy: RetentionPolicy = "until-unreferenced"
    expires_on: date | None = Field(default=None, alias="expiresOn")

    @model_validator(mode="after")
    def validate_expiry(self) -> RetentionMetadata:
        if self.policy == "indefinite" and self.expires_on is not None:
            raise ValueError("indefinite retention cannot have an expiry date")
        return self


class SourceReceipt(BaseModel):
    """Safe serialized receipt containing digests and opaque scope identifiers only."""

    model_config = ConfigDict(extra="forbid")

    contract_version: Literal["source-version.v1"] = Field(
        default=SOURCE_VERSION_CONTRACT_VERSION, alias="contractVersion"
    )
    source_version_id: str = Field(
        alias="sourceVersionId", pattern=r"^sv_[0-9a-f]{64}$"
    )
    project_scope_id: str = Field(
        alias="projectScopeId", pattern=r"^project_[0-9a-f]{64}$"
    )
    source_artifact_scope_id: str = Field(
        alias="sourceArtifactScopeId", pattern=r"^artifact_[0-9a-f]{64}$"
    )
    original_content_digest: str = Field(
        alias="originalContentDigest", pattern=r"^sha256:[0-9a-f]{64}$"
    )
    canonical_content_digest: str = Field(
        alias="canonicalContentDigest", pattern=r"^sha256:[0-9a-f]{64}$"
    )
    parent_source_version_id: str | None = Field(
        default=None, alias="parentSourceVersionId", pattern=r"^sv_[0-9a-f]{64}$"
    )
    parent_canonical_content_digest: str | None = Field(
        default=None,
        alias="parentCanonicalContentDigest",
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    canonicalization_version: Literal["crlf-lf.v1"] = Field(
        default=CANONICALIZATION_VERSION, alias="canonicalizationVersion"
    )
    coordinate_system_version: Literal["unicode-codepoint.v1"] = Field(
        default=COORDINATE_SYSTEM_VERSION, alias="coordinateSystemVersion"
    )
    retention: RetentionMetadata
    replay_key: str = Field(alias="replayKey", pattern=r"^replay_[0-9a-f]{64}$")
    receipt_digest: str = Field(alias="receiptDigest", pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_parent_pair(self) -> SourceReceipt:
        if (self.parent_source_version_id is None) != (
            self.parent_canonical_content_digest is None
        ):
            raise ValueError("parent source version and parent digest must be paired")
        return self

    def safe_dict(self) -> dict[str, object]:
        """Return deterministic, raw-content-free receipt data."""

        return cast(dict[str, object], self.model_dump(mode="json", by_alias=True))


class SourceVersion(BaseModel):
    """Immutable source identity plus a safe receipt; content is never retained."""

    model_config = ConfigDict(extra="forbid")

    contract_version: Literal["source-version.v1"] = Field(
        default=SOURCE_VERSION_CONTRACT_VERSION, alias="contractVersion"
    )
    source_version_id: str = Field(
        alias="sourceVersionId", pattern=r"^sv_[0-9a-f]{64}$"
    )
    project_scope_id: str = Field(
        alias="projectScopeId", pattern=r"^project_[0-9a-f]{64}$"
    )
    source_artifact_scope_id: str = Field(
        alias="sourceArtifactScopeId", pattern=r"^artifact_[0-9a-f]{64}$"
    )
    original_content_digest: str = Field(
        alias="originalContentDigest", pattern=r"^sha256:[0-9a-f]{64}$"
    )
    canonical_content_digest: str = Field(
        alias="canonicalContentDigest", pattern=r"^sha256:[0-9a-f]{64}$"
    )
    parent_source_version_id: str | None = Field(
        default=None, alias="parentSourceVersionId", pattern=r"^sv_[0-9a-f]{64}$"
    )
    parent_canonical_content_digest: str | None = Field(
        default=None,
        alias="parentCanonicalContentDigest",
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    canonicalization_version: Literal["crlf-lf.v1"] = Field(
        default=CANONICALIZATION_VERSION, alias="canonicalizationVersion"
    )
    coordinate_system_version: Literal["unicode-codepoint.v1"] = Field(
        default=COORDINATE_SYSTEM_VERSION, alias="coordinateSystemVersion"
    )
    retention: RetentionMetadata
    replay_key: str = Field(alias="replayKey", pattern=r"^replay_[0-9a-f]{64}$")
    receipt_digest: str = Field(alias="receiptDigest", pattern=r"^sha256:[0-9a-f]{64}$")
    project_id: str = Field(exclude=True, repr=False)
    source_artifact_id: str = Field(exclude=True, repr=False)

    @model_validator(mode="after")
    def validate_parent_pair(self) -> SourceVersion:
        if (self.parent_source_version_id is None) != (
            self.parent_canonical_content_digest is None
        ):
            raise ValueError("parent source version and parent digest must be paired")
        return self

    def receipt(self) -> SourceReceipt:
        """Return the raw-content-free receipt for custody or persistence."""

        data = self.model_dump(
            mode="json", by_alias=True, exclude={"project_id", "source_artifact_id"}
        )
        return SourceReceipt.model_validate(data)

    def safe_dict(self) -> dict[str, object]:
        """Return a serialized source identity without raw or sensitive IDs."""

        return self.receipt().safe_dict()


def create_source_version(
    *,
    project_id: str,
    source_artifact_id: str,
    content: bytes | str,
    parent_source_version_id: str | None = None,
    parent_canonical_content_digest: str | None = None,
    retention: RetentionMetadata | None = None,
) -> SourceVersion:
    """Create a deterministic source version after strict UTF-8 validation."""

    original_bytes, decoded = _strict_utf8(content)
    canonical = decoded.replace("\r\n", "\n").replace("\r", "\n")
    canonical_bytes = canonical.encode("utf-8", "strict")
    project_scope_id = _scope_id("project", project_id)
    artifact_scope_id = _scope_id(
        "artifact", f"{project_scope_id}\0{source_artifact_id}"
    )
    original_digest = _sha256_digest(original_bytes)
    canonical_digest = _sha256_digest(canonical_bytes)
    retention_value = retention or RetentionMetadata()
    identity = {
        "contractVersion": SOURCE_VERSION_CONTRACT_VERSION,
        "projectScopeId": project_scope_id,
        "sourceArtifactScopeId": artifact_scope_id,
        "originalContentDigest": original_digest,
        "canonicalContentDigest": canonical_digest,
        "parentSourceVersionId": parent_source_version_id,
        "parentCanonicalContentDigest": parent_canonical_content_digest,
        "canonicalizationVersion": CANONICALIZATION_VERSION,
        "coordinateSystemVersion": COORDINATE_SYSTEM_VERSION,
        "retention": retention_value.model_dump(mode="json", by_alias=True),
    }
    source_version_id = _opaque_id("sv", identity)
    replay_key = _opaque_id("replay", identity)
    receipt_payload = {
        **identity,
        "sourceVersionId": source_version_id,
        "replayKey": replay_key,
    }
    receipt_digest = _sha256_digest(_stable_json(receipt_payload))
    return SourceVersion.model_validate(
        {
            **receipt_payload,
            "receiptDigest": receipt_digest,
            "project_id": project_id,
            "source_artifact_id": source_artifact_id,
        }
    )


def serialize_source_receipt(receipt: SourceReceipt) -> str:
    """Serialize a receipt deterministically without source content."""

    return _stable_json(receipt.safe_dict()).decode("utf-8")


def verify_source_receipt(
    receipt: SourceReceipt,
    *,
    project_id: str,
    source_artifact_id: str,
    content: bytes | str,
    parent_source_version_id: str | None = None,
    parent_canonical_content_digest: str | None = None,
) -> None:
    """Fail closed unless content, project, lineage and receipt digest replay exactly."""

    try:
        source = create_source_version(
            project_id=project_id,
            source_artifact_id=source_artifact_id,
            content=content,
            parent_source_version_id=parent_source_version_id,
            parent_canonical_content_digest=parent_canonical_content_digest,
            retention=receipt.retention,
        )
    except (TypeError, UnicodeError, ValueError) as error:
        raise SourceVersionVerificationError("source input is invalid") from error
    expected = source.receipt().safe_dict()
    actual = receipt.safe_dict()
    if expected != actual:
        if expected["projectScopeId"] != actual["projectScopeId"]:
            reason = "project scope mismatch"
        elif expected["sourceVersionId"] != actual["sourceVersionId"]:
            reason = "source content or lineage fork detected"
        elif expected["receiptDigest"] != actual["receiptDigest"]:
            reason = "receipt digest tampering detected"
        else:
            reason = "source receipt replay mismatch"
        raise SourceVersionVerificationError(reason)


def _strict_utf8(content: bytes | str) -> tuple[bytes, str]:
    if isinstance(content, bytes):
        try:
            return content, content.decode("utf-8", "strict")
        except UnicodeDecodeError as error:
            raise SourceVersionVerificationError("source bytes are not strict UTF-8") from error
    if isinstance(content, str):
        try:
            encoded = content.encode("utf-8", "strict")
        except UnicodeEncodeError as error:
            raise SourceVersionVerificationError("source text contains invalid Unicode") from error
        return encoded, content
    raise TypeError("source content must be bytes or str")


def _scope_id(prefix: Literal["project", "artifact"], value: str) -> str:
    if not value or not value.strip():
        raise ValueError("scope identifiers must be non-empty")
    return f"{prefix}_{hashlib.sha256(value.encode('utf-8', 'strict')).hexdigest()}"


def _opaque_id(prefix: str, value: dict[str, object]) -> str:
    return f"{prefix}_{hashlib.sha256(_stable_json(value)).hexdigest()}"


def _sha256_digest(value: bytes) -> str:
    return f"sha256:{hashlib.sha256(value).hexdigest()}"


def _stable_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8", "strict")
