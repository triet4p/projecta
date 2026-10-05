"""Local persistent evidence adapter with an S3-compatible port seam."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import re
import shutil
import tempfile
import uuid
from collections.abc import AsyncIterable, AsyncIterator, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from projecta_api.evidence.ports import (
    EvidenceError,
    EvidenceGetRequest,
    EvidenceHeadRequest,
    EvidenceMetadata,
    EvidencePutRequest,
    EvidenceReceipt,
    EvidenceRetentionRequest,
)

_PROJECT = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
_REFERENCE = re.compile(r"^ev_[A-Za-z0-9_-]{22}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ALLOWED_CONTENT_TYPES = frozenset({"application/json", "text/plain"})
_MAX_BYTES = 1024 * 1024
_CHUNK_BYTES = 64 * 1024


def _safe_project(value: str) -> bool:
    return bool(_PROJECT.fullmatch(value))


class LocalEvidenceStore:
    """Write immutable objects below a dedicated root, never from a client key."""

    def __init__(self, root: Path, *, max_bytes: int = _MAX_BYTES) -> None:
        self._root = root.resolve()
        self._max_bytes = max(1, min(max_bytes, _MAX_BYTES))
        (self._root / "objects").mkdir(parents=True, exist_ok=True)
        (self._root / "references").mkdir(parents=True, exist_ok=True)
        self._write_lock = asyncio.Lock()

    async def put(
        self,
        request: EvidencePutRequest,
        content: AsyncIterable[bytes],
        *,
        deadline: float | None = None,
        cancellation: object | None = None,
    ) -> EvidenceReceipt:
        self._validate_request(request)
        temp_path: Path | None = None
        observed = 0
        digest = hashlib.sha256()
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb", dir=self._root / "objects", prefix=".tmp-", delete=False
            ) as temporary:
                temp_path = Path(temporary.name)
                async for chunk in content:
                    self._check(deadline, cancellation)
                    if not chunk:
                        raise EvidenceError("EVIDENCE_CONTENT_INVALID")
                    observed += len(chunk)
                    if observed > self._max_bytes or observed > request.declared_size:
                        raise EvidenceError("EVIDENCE_SIZE_EXCEEDED")
                    digest.update(chunk)
                    await asyncio.to_thread(temporary.write, chunk)
                await asyncio.to_thread(temporary.flush)
                await asyncio.to_thread(os.fsync, temporary.fileno())
            if observed != request.declared_size:
                raise EvidenceError("EVIDENCE_SIZE_MISMATCH")
            actual_digest = digest.hexdigest()
            if actual_digest != request.declared_sha256 or not _SHA256.fullmatch(actual_digest):
                raise EvidenceError("EVIDENCE_DIGEST_MISMATCH")
            async with self._write_lock:
                target_dir = self._object_dir(request.project_scope, actual_digest)
                target_dir.mkdir(parents=True, exist_ok=True)
                metadata_path = target_dir / "metadata.json"
                object_path = target_dir / "content"
                if metadata_path.exists() and object_path.exists():
                    existing = self._read_metadata(metadata_path, request.project_scope)
                    if (
                        existing.sha256 != actual_digest
                        or existing.size_bytes != observed
                        or existing.content_type != request.content_type
                    ):
                        raise EvidenceError("EVIDENCE_CONTENT_CONFLICT")
                    self._write_reference_index(existing)
                    temp_path.unlink(missing_ok=True)
                    return EvidenceReceipt(
                        existing.evidence_reference,
                        actual_digest,
                        observed,
                        request.content_type,
                        True,
                    )
                evidence_reference = self._content_reference(request.project_scope, actual_digest)
                created_at = datetime.now(UTC)
                metadata = EvidenceMetadata(
                    evidence_reference=evidence_reference,
                    project_scope=request.project_scope,
                    sha256=actual_digest,
                    size_bytes=observed,
                    content_type=request.content_type,
                    created_at=created_at,
                    retention_class=request.retention_class,
                    retain_until=None,
                    source_reference=request.source_reference,
                )
                if not object_path.exists():
                    await asyncio.to_thread(os.replace, temp_path, object_path)
                    temp_path = None
                else:
                    if object_path.stat().st_size != observed:
                        raise EvidenceError("EVIDENCE_CONTENT_CONFLICT")
                    temp_path.unlink(missing_ok=True)
                self._write_metadata(metadata_path, metadata)
                self._write_reference_index(metadata)
                return EvidenceReceipt(
                    evidence_reference,
                    actual_digest,
                    observed,
                    request.content_type,
                    False,
                )
        except asyncio.CancelledError as exc:
            raise EvidenceError("EVIDENCE_CANCELLED") from exc
        except EvidenceError:
            raise
        except Exception as exc:  # noqa: BLE001 - map adapter failures to a finite safe code.
            raise EvidenceError("EVIDENCE_WRITE_INTERRUPTED") from exc
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)

    async def head(
        self, request: EvidenceHeadRequest, *, deadline: float | None = None
    ) -> EvidenceMetadata:
        self._check(deadline, None)
        return self._resolve(request.project_scope, request.evidence_reference)

    async def get(
        self,
        request: EvidenceGetRequest,
        *,
        max_bytes: int,
        deadline: float | None = None,
        cancellation: object | None = None,
    ) -> tuple[EvidenceMetadata, AsyncIterator[bytes]]:
        self._check(deadline, cancellation)
        metadata = await self.head(
            EvidenceHeadRequest(request.project_scope, request.evidence_reference),
            deadline=deadline,
        )
        if max_bytes < 1 or max_bytes < metadata.size_bytes or max_bytes > self._max_bytes:
            raise EvidenceError("EVIDENCE_READ_LIMIT_EXCEEDED")
        object_path = self._object_dir(metadata.project_scope, metadata.sha256) / "content"
        if not object_path.is_file():
            raise EvidenceError("EVIDENCE_NOT_FOUND")

        async def stream() -> AsyncIterator[bytes]:
            observed = 0
            digest = hashlib.sha256()
            try:
                with object_path.open("rb") as source:
                    while True:
                        self._check(deadline, cancellation)
                        chunk = await asyncio.to_thread(source.read, _CHUNK_BYTES)
                        if not chunk:
                            break
                        observed += len(chunk)
                        if observed > max_bytes:
                            raise EvidenceError("EVIDENCE_READ_LIMIT_EXCEEDED")
                        digest.update(chunk)
                        yield chunk
                if observed != metadata.size_bytes or digest.hexdigest() != metadata.sha256:
                    raise EvidenceError("EVIDENCE_INTEGRITY_FAILED")
            except EvidenceError:
                raise
            except (OSError, asyncio.CancelledError) as exc:
                raise EvidenceError("EVIDENCE_UNAVAILABLE") from exc

        return metadata, stream()

    async def list_project(self, project_scope: str) -> tuple[EvidenceMetadata, ...]:
        """Enumerate only the metadata references owned by one canonical project."""
        if not _safe_project(project_scope):
            raise EvidenceError("EVIDENCE_PROJECT_FORBIDDEN")
        async with self._write_lock:
            return await asyncio.to_thread(self._list_project_sync, project_scope)

    async def restore_portable(
        self,
        project_scope: str,
        reference: Mapping[str, object],
        content_path: Path,
    ) -> None:
        """Restore one already-validated archive object with its stable reference metadata."""
        if not _safe_project(project_scope):
            raise EvidenceError("EVIDENCE_PROJECT_FORBIDDEN")
        async with self._write_lock:
            await asyncio.to_thread(self._restore_portable_sync, project_scope, reference, content_path)

    def _restore_portable_sync(
        self,
        project_scope: str,
        reference: Mapping[str, object],
        content_path: Path,
    ) -> None:
        try:
            evidence_reference = str(reference["evidenceReference"])
            digest = str(reference["sha256"])
            size_bytes = int(reference["sizeBytes"])
            content_type = str(reference["contentType"])
            created_at = datetime.fromisoformat(str(reference["createdAt"]))
            retain_until_value = reference["retainUntil"]
            retain_until = (
                datetime.fromisoformat(str(retain_until_value))
                if retain_until_value is not None
                else None
            )
            retention_class = str(reference["retentionClass"])
            source_reference = str(reference["sourceReference"])
            contract_version = str(reference["contractVersion"])
        except (KeyError, TypeError, ValueError) as error:
            raise EvidenceError("EVIDENCE_METADATA_INVALID") from error
        if (
            not _REFERENCE.fullmatch(evidence_reference)
            or not _SHA256.fullmatch(digest)
            or not 0 <= size_bytes <= self._max_bytes
            or content_type not in _ALLOWED_CONTENT_TYPES
            or self._content_reference(project_scope, digest) != evidence_reference
            or not created_at.tzinfo
            or created_at.utcoffset() is None
            or retain_until is not None
            and (not retain_until.tzinfo or retain_until.utcoffset() is None)
            or retention_class != "connector-default"
            or contract_version != "connector-evidence.v1"
            or not source_reference
            or len(source_reference) > 512
            or source_reference.startswith(("/", "\\"))
            or ".." in source_reference
            or any(ord(character) < 32 for character in source_reference)
            or content_path.is_symlink()
            or not content_path.is_file()
            or content_path.stat().st_size != size_bytes
        ):
            raise EvidenceError("EVIDENCE_METADATA_INVALID")
        target_dir = self._object_dir(project_scope, digest)
        object_path = target_dir / "content"
        metadata_path = target_dir / "metadata.json"
        reference_path = self._reference_path(project_scope, evidence_reference)
        if target_dir.exists() or reference_path.exists():
            raise EvidenceError("EVIDENCE_CONTENT_CONFLICT")
        temporary = target_dir.parent / f".{digest}.{uuid.uuid4().hex}.partial"
        observed = 0
        actual = hashlib.sha256()
        try:
            target_dir.parent.mkdir(parents=True, exist_ok=True)
            with content_path.open("rb") as source, temporary.open("xb") as destination:
                while chunk := source.read(_CHUNK_BYTES):
                    observed += len(chunk)
                    if observed > size_bytes or observed > self._max_bytes:
                        raise EvidenceError("EVIDENCE_SIZE_EXCEEDED")
                    actual.update(chunk)
                    destination.write(chunk)
                destination.flush()
                os.fsync(destination.fileno())
            if observed != size_bytes or actual.hexdigest() != digest:
                raise EvidenceError("EVIDENCE_DIGEST_MISMATCH")
            target_dir.mkdir(parents=True)
            os.replace(temporary, object_path)
            metadata = EvidenceMetadata(
                evidence_reference=evidence_reference,
                project_scope=project_scope,
                sha256=digest,
                size_bytes=size_bytes,
                content_type=content_type,
                created_at=created_at,
                retention_class=retention_class,
                retain_until=retain_until,
                source_reference=source_reference,
                contract_version=contract_version,
            )
            self._write_metadata(metadata_path, metadata)
            self._write_reference_index(metadata)
        except EvidenceError:
            raise
        except OSError as error:
            raise EvidenceError("EVIDENCE_WRITE_INTERRUPTED") from error
        finally:
            temporary.unlink(missing_ok=True)

    async def remove_project_for_import(self, project_scope: str) -> None:
        """Remove only this import's preflight-empty project evidence roots on rollback."""
        if not _safe_project(project_scope):
            raise EvidenceError("EVIDENCE_PROJECT_FORBIDDEN")
        async with self._write_lock:
            await asyncio.to_thread(self._remove_project_for_import_sync, project_scope)

    def _remove_project_for_import_sync(self, project_scope: str) -> None:
        is_junction = getattr(os.path, "isjunction", lambda _path: False)
        for directory in (
            self._root / "references" / project_scope,
            self._root / "objects" / project_scope,
        ):
            if is_junction(directory) or directory.is_symlink():
                raise EvidenceError("EVIDENCE_INTEGRITY_FAILED")
            if directory.exists():
                if not directory.is_dir():
                    raise EvidenceError("EVIDENCE_INTEGRITY_FAILED")
                shutil.rmtree(directory)

    def _list_project_sync(self, project_scope: str) -> tuple[EvidenceMetadata, ...]:
        directory = self._root / "references" / project_scope
        is_junction = getattr(os.path, "isjunction", lambda _path: False)
        if is_junction(directory) or directory.is_symlink():
            raise EvidenceError("EVIDENCE_INTEGRITY_FAILED")
        if not directory.exists():
            return ()
        if not directory.is_dir():
            raise EvidenceError("EVIDENCE_INTEGRITY_FAILED")
        metadata_items: list[EvidenceMetadata] = []
        references: set[str] = set()
        for path in sorted(directory.iterdir(), key=lambda item: item.name):
            if (
                is_junction(path)
                or path.is_symlink()
                or not path.is_file()
                or not path.name.endswith(".json")
            ):
                raise EvidenceError("EVIDENCE_INTEGRITY_FAILED")
            evidence_reference = path.name.removesuffix(".json")
            if not _REFERENCE.fullmatch(evidence_reference) or evidence_reference in references:
                raise EvidenceError("EVIDENCE_INTEGRITY_FAILED")
            references.add(evidence_reference)
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, TypeError, ValueError, json.JSONDecodeError) as error:
                raise EvidenceError("EVIDENCE_INTEGRITY_FAILED") from error
            if (
                not isinstance(value, dict)
                or set(value) != {"sha256"}
                or not isinstance(value["sha256"], str)
                or not _SHA256.fullmatch(value["sha256"])
            ):
                raise EvidenceError("EVIDENCE_INTEGRITY_FAILED")
            metadata = self._read_metadata(
                self._object_dir(project_scope, value["sha256"]) / "metadata.json",
                project_scope,
            )
            if metadata.evidence_reference != evidence_reference:
                raise EvidenceError("EVIDENCE_INTEGRITY_FAILED")
            metadata_items.append(metadata)
        return tuple(metadata_items)

    async def mark_for_retention_purge(
        self, request: EvidenceRetentionRequest, *, deadline: float | None = None
    ) -> str:
        self._check(deadline, None)
        async with self._write_lock:
            metadata = self._resolve(request.project_scope, request.evidence_reference)
            metadata_path = (
                self._object_dir(metadata.project_scope, metadata.sha256) / "metadata.json"
            )
            replacement = EvidenceMetadata(
                evidence_reference=metadata.evidence_reference,
                project_scope=metadata.project_scope,
                sha256=metadata.sha256,
                size_bytes=metadata.size_bytes,
                content_type=metadata.content_type,
                created_at=metadata.created_at,
                retention_class=metadata.retention_class,
                retain_until=request.retain_until,
                source_reference=metadata.source_reference,
            )
            self._write_metadata(metadata_path, replacement)
            self._write_reference_index(replacement)
        return "marked"

    def _resolve(self, project_scope: str, evidence_reference: str) -> EvidenceMetadata:
        if not _safe_project(project_scope) or not _REFERENCE.fullmatch(evidence_reference):
            raise EvidenceError("EVIDENCE_REFERENCE_INVALID")
        reference_path = self._reference_path(project_scope, evidence_reference)
        try:
            reference = json.loads(reference_path.read_text(encoding="utf-8"))
            digest = str(reference["sha256"])
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise EvidenceError("EVIDENCE_NOT_FOUND") from exc
        metadata = self._read_metadata(
            self._object_dir(project_scope, digest) / "metadata.json", project_scope
        )
        if metadata.evidence_reference != evidence_reference:
            raise EvidenceError("EVIDENCE_NOT_FOUND")
        return metadata

    def _object_dir(self, project_scope: str, digest: str) -> Path:
        if not _safe_project(project_scope) or not _SHA256.fullmatch(digest):
            raise EvidenceError("EVIDENCE_REFERENCE_INVALID")
        project_dir = self._root / "objects" / project_scope
        target = (project_dir / digest[:2] / digest).resolve()
        if self._root not in target.parents:
            raise EvidenceError("EVIDENCE_REFERENCE_INVALID")
        return target

    def _reference_path(self, project_scope: str, evidence_reference: str) -> Path:
        if not _safe_project(project_scope) or not _REFERENCE.fullmatch(evidence_reference):
            raise EvidenceError("EVIDENCE_REFERENCE_INVALID")
        target = (
            self._root / "references" / project_scope / f"{evidence_reference}.json"
        ).resolve()
        if self._root not in target.parents:
            raise EvidenceError("EVIDENCE_REFERENCE_INVALID")
        return target

    @staticmethod
    def _content_reference(project_scope: str, digest: str) -> str:
        value = hashlib.sha256(f"{project_scope}\0{digest}".encode()).digest()
        token = base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")[:22]
        return "ev_" + token

    def _write_reference_index(self, metadata: EvidenceMetadata) -> None:
        path = self._reference_path(metadata.project_scope, metadata.evidence_reference)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._write_json_atomic(path, {"sha256": metadata.sha256})

    def _write_metadata(self, path: Path, metadata: EvidenceMetadata) -> None:
        self._write_json_atomic(path, self._metadata_json(metadata))

    @staticmethod
    def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        try:
            temporary.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)

    def _read_metadata(self, path: Path, project_scope: str) -> EvidenceMetadata:
        try:
            raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
            if raw.get("project_scope") != project_scope:
                raise EvidenceError("EVIDENCE_NOT_FOUND")
            return EvidenceMetadata(
                evidence_reference=str(raw["evidence_reference"]),
                project_scope=str(raw["project_scope"]),
                sha256=str(raw["sha256"]),
                size_bytes=int(raw["size_bytes"]),
                content_type=str(raw["content_type"]),
                created_at=datetime.fromisoformat(str(raw["created_at"])),
                retention_class=str(raw["retention_class"]),
                retain_until=(
                    datetime.fromisoformat(str(raw["retain_until"]))
                    if raw.get("retain_until")
                    else None
                ),
                source_reference=str(raw["source_reference"]),
            )
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise EvidenceError("EVIDENCE_NOT_FOUND") from exc

    @staticmethod
    def _metadata_json(metadata: EvidenceMetadata) -> dict[str, Any]:
        return {
            "evidence_reference": metadata.evidence_reference,
            "project_scope": metadata.project_scope,
            "sha256": metadata.sha256,
            "size_bytes": metadata.size_bytes,
            "content_type": metadata.content_type,
            "created_at": metadata.created_at.isoformat(),
            "retention_class": metadata.retention_class,
            "retain_until": metadata.retain_until.isoformat() if metadata.retain_until else None,
            "source_reference": metadata.source_reference,
            "contract_version": metadata.contract_version,
        }

    def _validate_request(self, request: EvidencePutRequest) -> None:
        if not _safe_project(request.project_scope):
            raise EvidenceError("EVIDENCE_PROJECT_FORBIDDEN")
        if request.content_type not in _ALLOWED_CONTENT_TYPES:
            raise EvidenceError("EVIDENCE_CONTENT_TYPE_UNSUPPORTED")
        if request.declared_size < 0 or request.declared_size > self._max_bytes:
            raise EvidenceError("EVIDENCE_SIZE_EXCEEDED")
        if not _SHA256.fullmatch(request.declared_sha256):
            raise EvidenceError("EVIDENCE_DIGEST_MISMATCH")
        if (
            not request.source_reference
            or len(request.source_reference) > 512
            or request.source_reference.startswith(("/", "\\"))
            or ".." in request.source_reference
            or any(ord(char) < 32 for char in request.source_reference)
        ):
            raise EvidenceError("EVIDENCE_METADATA_INVALID")

    @staticmethod
    def _check(deadline: float | None, cancellation: object | None) -> None:
        if deadline is not None and asyncio.get_running_loop().time() >= deadline:
            raise EvidenceError("EVIDENCE_DEADLINE_EXCEEDED")
        if isinstance(cancellation, asyncio.Event) and cancellation.is_set():
            raise EvidenceError("EVIDENCE_CANCELLED")
