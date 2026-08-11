"""Provider-neutral evidence port and safe bounded value objects."""

from __future__ import annotations

from collections.abc import AsyncIterable, AsyncIterator
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True, slots=True)
class EvidencePutRequest:
    project_scope: str
    content_type: str
    declared_size: int
    declared_sha256: str
    source_reference: str
    retention_class: str = "connector-default"


@dataclass(frozen=True, slots=True)
class EvidenceGetRequest:
    project_scope: str
    evidence_reference: str


@dataclass(frozen=True, slots=True)
class EvidenceHeadRequest:
    project_scope: str
    evidence_reference: str


@dataclass(frozen=True, slots=True)
class EvidenceRetentionRequest:
    project_scope: str
    evidence_reference: str
    retain_until: datetime


@dataclass(frozen=True, slots=True)
class EvidenceMetadata:
    evidence_reference: str
    project_scope: str
    sha256: str
    size_bytes: int
    content_type: str
    created_at: datetime
    retention_class: str
    retain_until: datetime | None
    source_reference: str
    contract_version: str = "connector-evidence.v1"


@dataclass(frozen=True, slots=True)
class EvidenceReceipt:
    evidence_reference: str
    sha256: str
    size_bytes: int
    content_type: str
    idempotent_reuse: bool


class EvidenceError(RuntimeError):
    """Finite safe error with no storage path, payload, or stack trace in its message."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class EvidenceStore(Protocol):
    async def put(
        self,
        request: EvidencePutRequest,
        content: AsyncIterable[bytes],
        *,
        deadline: float | None = None,
        cancellation: object | None = None,
    ) -> EvidenceReceipt: ...

    async def get(
        self,
        request: EvidenceGetRequest,
        *,
        max_bytes: int,
        deadline: float | None = None,
        cancellation: object | None = None,
    ) -> tuple[EvidenceMetadata, AsyncIterator[bytes]]: ...

    async def head(self, request: EvidenceHeadRequest, *, deadline: float | None = None) -> EvidenceMetadata: ...

    async def mark_for_retention_purge(
        self, request: EvidenceRetentionRequest, *, deadline: float | None = None
    ) -> str: ...
