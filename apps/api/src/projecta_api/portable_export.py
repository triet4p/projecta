"""Bounded logical Projecta export for the owner-approved projecta-portable.v1 contract."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import platform
import re
import shutil
import sqlite3
import stat
import tempfile
import uuid
import zipfile
from collections import defaultdict
from collections.abc import AsyncIterator, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Protocol, cast, get_args

from sqlalchemy import Engine, inspect, select, text
from sqlalchemy.engine import Connection

from projecta_api.configuration.storage import OperationalDatabase
from projecta_api.context import TrustedRequestContext
from projecta_api.evidence.local import LocalEvidenceStore
from projecta_api.evidence.ports import EvidenceGetRequest, EvidenceMetadata
from projecta_api.extraction.correction_burden import (
    CORRECTION_BURDEN_CONTRACT_VERSION,
    CorrectionBurdenEventRecord,
    _event_from_row,
)
from projecta_api.extraction.review_receipts import (
    REVIEW_RECEIPT_CONTRACT_VERSION,
    ReviewDecisionReceiptRecord,
    _receipt_digest,
    _receipt_from_row,
)
from projecta_api.connectors.github_public_issues import GitHubCursorCodec
from projecta_api.connectors.teams import _cursor_watermark
from projecta_api.structured_candidate_store import StructuredCandidateEditRequest
from projecta_api.structured_note import NoteDraftStatus, StructuredNoteDraft
from projecta_api.structured_note_store import structured_note_draft_fingerprint
from projecta_api.semantic_core import SemanticCoreProblem
from projecta_api.extraction.local_suggestions import LocalSuggestionProposal

PORTABLE_CONTRACT = "projecta-portable.v1"
MAX_ARCHIVE_BYTES = 2 * 1024 * 1024 * 1024
MAX_EXPANDED_BYTES = 4 * 1024 * 1024 * 1024
MAX_MANIFEST_BYTES = 2 * 1024 * 1024
MAX_ENTRIES = 4096
MAX_EVIDENCE_OBJECTS = 2048
MAX_EVIDENCE_BYTES = 1024 * 1024
MAX_SEMANTIC_BYTES = 512 * 1024 * 1024
MAX_SEMANTIC_TRIPLES = 1_000_000
MAX_LOGICAL_RECORDS = 250_000
_PROJECT_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
_SOURCE_REVISION = re.compile(r"^catalog-r-[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_PORTABLE_DIGEST_MARKER = re.compile(
    r"^projecta-portable-(?:key|actor)\.v1\|(sha256:[0-9a-f]{64})\|[0-9a-f]{32}$"
)
_TEAMS_CURSOR = re.compile(r"^teams\.v1\|([^|]{1,64})\|([0-9a-f]{32})$")
_FIXED_MEMBERS: tuple[tuple[str, str, str], ...] = (
    ("payload/semantic/project.trig", "semantic-project", "application/trig"),
    ("payload/application/project-workflows.json", "application-workflows", "application/json"),
    ("payload/operations/connectors.json", "connector-state", "application/json"),
    ("payload/receipts/review-decision-receipts.jsonl", "review-receipts", "application/x-ndjson"),
    ("payload/receipts/correction-burden-events.jsonl", "correction-burden-events", "application/x-ndjson"),
)
_SQLITE_TABLE_COLUMNS: dict[str, frozenset[str]] = {
    "structured_note_drafts": frozenset(
        {"handle", "project_id", "actor_id", "revision", "payload", "fingerprint", "idempotency_key", "committed_note_id", "created_at", "updated_at"}
    ),
    "structured_candidate_edits": frozenset(
        {"edit_handle", "project_id", "candidate_handle", "actor_id", "request_id", "revision", "payload", "created_at"}
    ),
    "local_suggestion_workflows": frozenset(
        {"workflow_id", "project_id", "source_version_digest", "source_version_revision", "item_handle_digest", "item_revision", "evidence_digest", "state", "proposal_json", "proposal_revision", "current_attempt_digest", "attempt_started_at", "model_id", "error_code", "latest_receipt_digest", "created_at", "updated_at"}
    ),
    "local_suggestion_attempts": frozenset(
        {"attempt_id", "project_id", "actor_digest", "workflow_id", "idempotency_digest", "request_digest", "state", "error_code", "requested_at"}
    ),
    "authoring_cost_events": frozenset(
        {"event_id", "project_digest", "actor_digest", "workflow_digest", "workflow_kind", "event_type", "attempt_digest", "receipt_digest", "assertion_digest", "decision", "local_inference_units", "correction_category", "correction_dimensions", "semantic_edit_count", "review_latency_ms", "occurred_at"}
    ),
}


class SemanticSnapshotClient(Protocol):
    async def request(
        self,
        context: TrustedRequestContext,
        method: str,
        path: str,
        body: object | None = None,
        key: str | None = None,
    ) -> object: ...

    async def stream_project_trig(
        self, context: TrustedRequestContext, destination: Path, max_bytes: int
    ) -> int: ...


class PortableExportFailure(RuntimeError):
    """Finite, safe export failure; source paths and data are never included."""

    def __init__(self, code: str, *, status_code: int = 409) -> None:
        self.code = code
        self.status_code = status_code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ExportArtifact:
    work_directory: Path
    path: Path
    filename: str
    sha256: str
    size_bytes: int
    project_id: str


@dataclass(frozen=True, slots=True)
class _Payload:
    path: str
    role: str
    media_type: str
    file_path: Path
    size_bytes: int
    sha256: str

    def manifest_entry(self) -> dict[str, object]:
        return {
            "path": self.path,
            "role": self.role,
            "mediaType": self.media_type,
            "sizeBytes": self.size_bytes,
            "sha256": self.sha256,
        }


@dataclass(frozen=True, slots=True)
class _EvidenceReference:
    metadata: EvidenceMetadata

    def manifest_value(self) -> dict[str, object]:
        metadata = self.metadata
        return {
            "evidenceReference": metadata.evidence_reference,
            "sha256": metadata.sha256,
            "sizeBytes": metadata.size_bytes,
            "contentType": metadata.content_type,
            "createdAt": _format_timestamp(metadata.created_at),
            "retentionClass": metadata.retention_class,
            "retainUntil": _format_timestamp(metadata.retain_until) if metadata.retain_until else None,
            "sourceReference": metadata.source_reference,
            "contractVersion": metadata.contract_version,
        }


@dataclass(frozen=True, slots=True)
class _Collection:
    source_revision: str
    payloads: tuple[_Payload, ...]
    evidence_references: tuple[_EvidenceReference, ...]
    sqlite_schema_versions: tuple[int, ...]
    postgres_alembic_head: str
    postgres_version: str
    semantic_triples: int
    logical_record_counts: Mapping[str, int]

    def revision_vector(self) -> tuple[object, ...]:
        return (
            self.source_revision,
            tuple((item.path, item.size_bytes, item.sha256) for item in self.payloads),
            tuple(
                (
                    item.metadata.evidence_reference,
                    item.metadata.sha256,
                    item.metadata.size_bytes,
                    item.metadata.content_type,
                    _format_timestamp(item.metadata.created_at),
                    item.metadata.retention_class,
                    _format_timestamp(item.metadata.retain_until) if item.metadata.retain_until else None,
                    item.metadata.source_reference,
                    item.metadata.contract_version,
                )
                for item in self.evidence_references
            ),
            self.sqlite_schema_versions,
            self.postgres_alembic_head,
            self.postgres_version,
            self.semantic_triples,
            tuple(sorted(self.logical_record_counts.items())),
        )


class _BoundedArchiveFile:
    """File proxy that rejects an archive as soon as its physical limit is crossed."""

    def __init__(self, stream: object, limit: int) -> None:
        self._stream = cast(object, stream)
        self._limit = limit
        self._high_water = 0

    def write(self, value: bytes) -> int:
        stream = cast(object, self._stream)
        write = getattr(stream, "write")
        written = cast(int, write(value))
        tell = getattr(stream, "tell")
        position = cast(int, tell())
        self._high_water = max(self._high_water, position)
        if self._high_water > self._limit:
            raise PortableExportFailure("EXPORT_TOO_LARGE", status_code=413)
        return written

    def tell(self) -> int:
        return cast(int, getattr(self._stream, "tell")())

    def seek(self, offset: int, whence: int = 0) -> int:
        return cast(int, getattr(self._stream, "seek")(offset, whence))

    def flush(self) -> None:
        getattr(self._stream, "flush")()

    def seekable(self) -> bool:
        return True


class ProjectPortableExportService:
    """Collect and validate one frozen project epoch into a verified ZIP package."""

    def __init__(
        self,
        database: OperationalDatabase,
        postgres_engine: Engine | None,
        evidence_store: LocalEvidenceStore | None,
        semantic_client: SemanticSnapshotClient,
        *,
        native_runtime_lock_held: bool,
    ) -> None:
        self._database = database
        self._postgres_engine = postgres_engine
        self._evidence = evidence_store
        self._semantic = semantic_client
        self._native_runtime_lock_held = native_runtime_lock_held

    def enabled(self) -> bool:
        return (
            self._native_runtime_lock_held
            and self._postgres_engine is not None
            and self._evidence is not None
        )

    async def create(
        self,
        context: TrustedRequestContext,
        project_name: str,
        source_revision: str,
        output_root: Path,
    ) -> ExportArtifact:
        project_id = context.project_id
        if not self.enabled():
            raise PortableExportFailure("EXPORT_UNSUPPORTED_RUNTIME", status_code=503)
        if not _PROJECT_ID.fullmatch(project_id):
            raise PortableExportFailure("EXPORT_UNSUPPORTED_STATE")
        _validate_project_name(project_name)
        _validate_source_revision(source_revision)
        _ensure_private_directory(output_root)
        work_directory = Path(tempfile.mkdtemp(prefix=".projecta-export-", dir=output_root))
        if os.name != "nt":
            os.chmod(work_directory, 0o700)
        try:
            first = await self._collect(context, work_directory / "snapshot")
            second = await self._collect(context, work_directory / "recheck")
            if (
                first.source_revision != source_revision
                or second.source_revision != source_revision
                or first.revision_vector() != second.revision_vector()
            ):
                raise PortableExportFailure("EXPORT_INTEGRITY_FAILED")
            await asyncio.to_thread(shutil.rmtree, work_directory / "recheck")
            producer = _producer_inventory(first)
            manifest = _manifest(project_id, project_name, producer, first)
            manifest_bytes = _canonical_json(manifest)
            if len(manifest_bytes) > MAX_MANIFEST_BYTES:
                raise PortableExportFailure("EXPORT_TOO_LARGE", status_code=413)
            expanded = len(manifest_bytes) + sum(item.size_bytes for item in first.payloads)
            if expanded > MAX_EXPANDED_BYTES:
                raise PortableExportFailure("EXPORT_TOO_LARGE", status_code=413)
            export_id = cast(str, manifest["exportId"])
            filename = f"{project_id}-export-{export_id}.projecta"
            partial_path = work_directory / f"{export_id}.partial"
            final_path = work_directory / filename
            await asyncio.to_thread(_write_archive, partial_path, manifest_bytes, first.payloads)
            _verify_archive(partial_path, manifest_bytes, first.payloads, expanded, source_revision)
            archive_digest, archive_size = await asyncio.to_thread(_hash_file, partial_path)
            if archive_size > MAX_ARCHIVE_BYTES:
                raise PortableExportFailure("EXPORT_TOO_LARGE", status_code=413)
            os.replace(partial_path, final_path)
            _fsync_directory(work_directory)
            return ExportArtifact(
                work_directory=work_directory,
                path=final_path,
                filename=filename,
                sha256=archive_digest,
                size_bytes=archive_size,
                project_id=project_id,
            )
        except BaseException:
            shutil.rmtree(work_directory, ignore_errors=True)
            raise

    async def _collect(
        self, context: TrustedRequestContext, directory: Path
    ) -> _Collection:
        project_id = context.project_id
        source_revision = await _read_source_revision(self._semantic, context)
        directory.mkdir(mode=0o700, parents=True, exist_ok=False)
        payload_directory = directory / "payload"
        payload_directory.mkdir(mode=0o700)
        semantic_path = directory / "semantic.trig"
        try:
            triple_count = await self._semantic.stream_project_trig(
                context, semantic_path, MAX_SEMANTIC_BYTES
            )
        except SemanticCoreProblem as error:
            if error.code in {
                "EXPORT_BUSY",
                "EXPORT_INTEGRITY_FAILED",
                "EXPORT_SOURCE_UNAVAILABLE",
                "EXPORT_TOO_LARGE",
                "EXPORT_UNSUPPORTED_VERSION",
            }:
                status_code = error.status_code if error.status_code in {409, 413, 503} else 503
                raise PortableExportFailure(error.code, status_code=status_code) from error
            raise PortableExportFailure("EXPORT_SOURCE_UNAVAILABLE", status_code=503) from error
        if triple_count < 0 or triple_count > MAX_SEMANTIC_TRIPLES:
            raise PortableExportFailure("EXPORT_TOO_LARGE", status_code=413)
        semantic_size = semantic_path.stat().st_size
        if semantic_size > MAX_SEMANTIC_BYTES:
            raise PortableExportFailure("EXPORT_TOO_LARGE", status_code=413)
        assets = _ontology_assets()
        workflows_path = payload_directory / "project-workflows.json"
        connectors_path = payload_directory / "connectors.json"
        receipts_path = payload_directory / "review-decision-receipts.jsonl"
        corrections_path = payload_directory / "correction-burden-events.jsonl"
        candidate_handles = await asyncio.to_thread(
            _candidate_edit_handles, self._database, project_id
        )
        candidate_identities = await asyncio.to_thread(
            _candidate_identities_from_trig, semantic_path, candidate_handles
        )
        sqlite_result, postgres_result = await asyncio.to_thread(
            _write_operational_payloads,
            self._database,
            self._postgres_engine,
            project_id,
            workflows_path,
            connectors_path,
            receipts_path,
            corrections_path,
            candidate_identities,
        )
        inbox_references = cast(frozenset[str], postgres_result["inbox_references"])
        evidence_references = await self._write_evidence_payloads(
            project_id, payload_directory, inbox_references
        )
        payload_specs = (
            _payload_from_file("payload/semantic/project.trig", "semantic-project", "application/trig", semantic_path),
            _payload_from_file("payload/application/project-workflows.json", "application-workflows", "application/json", workflows_path),
            _payload_from_file("payload/operations/connectors.json", "connector-state", "application/json", connectors_path),
            _payload_from_file("payload/receipts/review-decision-receipts.jsonl", "review-receipts", "application/x-ndjson", receipts_path),
            _payload_from_file("payload/receipts/correction-burden-events.jsonl", "correction-burden-events", "application/x-ndjson", corrections_path),
        )
        evidence_payloads: list[_Payload] = []
        for reference in evidence_references:
            metadata = reference.metadata
            payload_path = payload_directory / "evidence" / "sha256" / f"{metadata.sha256}.bin"
            evidence_payloads.append(
                _payload_from_file(
                    f"payload/evidence/sha256/{metadata.sha256}.bin",
                    "evidence-object",
                    metadata.content_type,
                    payload_path,
                )
            )
        all_payloads = payload_specs + tuple(evidence_payloads)
        if len(all_payloads) + 1 > MAX_ENTRIES:
            raise PortableExportFailure("EXPORT_TOO_LARGE", status_code=413)
        expanded = sum(item.size_bytes for item in all_payloads)
        if expanded + MAX_MANIFEST_BYTES > MAX_EXPANDED_BYTES:
            raise PortableExportFailure("EXPORT_TOO_LARGE", status_code=413)
        total_records = sum(sqlite_result["record_counts"].values()) + sum(
            postgres_result["record_counts"].values()
        )
        if total_records > MAX_LOGICAL_RECORDS:
            raise PortableExportFailure("EXPORT_TOO_LARGE", status_code=413)
        evidence_values = tuple(
            sorted(evidence_references, key=lambda item: item.metadata.evidence_reference)
        )
        return _Collection(
            source_revision=source_revision,
            payloads=all_payloads,
            evidence_references=evidence_values,
            sqlite_schema_versions=sqlite_result["schema_versions"],
            postgres_alembic_head=postgres_result["alembic_head"],
            postgres_version=postgres_result["server_version"],
            semantic_triples=triple_count,
            logical_record_counts={
                **{f"workflow.{key}": value for key, value in sqlite_result["record_counts"].items()},
                **{f"postgres.{key}": value for key, value in postgres_result["record_counts"].items()},
            },
        )

    async def _write_evidence_payloads(
        self,
        project_id: str,
        payload_directory: Path,
        inbox_references: frozenset[str],
    ) -> tuple[_EvidenceReference, ...]:
        if self._evidence is None:
            raise PortableExportFailure("EXPORT_SOURCE_UNAVAILABLE", status_code=503)
        try:
            metadata_items = await self._evidence.list_project(project_id)
        except Exception as error:  # noqa: BLE001 - storage details never cross the API boundary.
            raise PortableExportFailure("EXPORT_SOURCE_UNAVAILABLE", status_code=503) from error
        if len(metadata_items) > MAX_EVIDENCE_OBJECTS:
            raise PortableExportFailure("EXPORT_TOO_LARGE", status_code=413)
        root = payload_directory / "evidence" / "sha256"
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        total_bytes = 0
        references: list[_EvidenceReference] = []
        digest_to_ref: dict[str, str] = {}
        reference_ids: set[str] = set()
        for metadata in sorted(metadata_items, key=lambda item: item.evidence_reference):
            _validate_evidence_metadata(project_id, metadata)
            if metadata.evidence_reference in reference_ids:
                raise PortableExportFailure("EXPORT_INTEGRITY_FAILED")
            reference_ids.add(metadata.evidence_reference)
            previous = digest_to_ref.get(metadata.sha256)
            if previous is not None and previous != metadata.evidence_reference:
                raise PortableExportFailure("EXPORT_INTEGRITY_FAILED")
            digest_to_ref[metadata.sha256] = metadata.evidence_reference
            target = root / f"{metadata.sha256}.bin"
            try:
                returned, content = await self._evidence.get(
                    EvidenceGetRequest(project_id, metadata.evidence_reference),
                    max_bytes=MAX_EVIDENCE_BYTES,
                )
                if returned != metadata:
                    raise PortableExportFailure("EXPORT_INTEGRITY_FAILED")
                observed = 0
                digest = hashlib.sha256()
                with target.open("xb") as output:
                    async for chunk in content:
                        observed += len(chunk)
                        total_bytes += len(chunk)
                        if observed > MAX_EVIDENCE_BYTES or total_bytes > MAX_EXPANDED_BYTES:
                            raise PortableExportFailure("EXPORT_TOO_LARGE", status_code=413)
                        digest.update(chunk)
                        await asyncio.to_thread(output.write, chunk)
                    await asyncio.to_thread(output.flush)
                    await asyncio.to_thread(os.fsync, output.fileno())
            except PortableExportFailure:
                raise
            except Exception as error:  # noqa: BLE001 - a missing/corrupt object aborts the package.
                raise PortableExportFailure("EXPORT_INTEGRITY_FAILED") from error
            if observed != metadata.size_bytes or digest.hexdigest() != metadata.sha256:
                raise PortableExportFailure("EXPORT_INTEGRITY_FAILED")
            references.append(_EvidenceReference(metadata))
        available_references = {item.metadata.evidence_reference for item in references}
        # Review digests may identify spans in Semantic Core, not LocalEvidenceStore objects.
        if not inbox_references <= available_references:
            raise PortableExportFailure("EXPORT_INTEGRITY_FAILED")
        return tuple(references)



def _candidate_edit_handles(
    database: OperationalDatabase, project_id: str
) -> frozenset[str]:
    handles: set[str] = set()
    with database.read_transaction() as connection:
        rows = connection.execute(
            "SELECT DISTINCT candidate_handle FROM structured_candidate_edits "
            "WHERE project_id = ? ORDER BY candidate_handle",
            (project_id,),
        )
        for row in rows:
            handle = _text(row["candidate_handle"])
            if not re.fullmatch(r"(?:candidate|node)-h-[0-9a-f]{24}", handle):
                raise PortableExportFailure("EXPORT_UNSUPPORTED_STATE")
            handles.add(handle)
            if len(handles) > MAX_LOGICAL_RECORDS:
                raise PortableExportFailure("EXPORT_TOO_LARGE", status_code=413)
    return frozenset(handles)


def _candidate_identities_from_trig(
    path: Path, source_handles: frozenset[str]
) -> dict[str, str]:
    if not source_handles:
        return {}
    expected = set(source_handles)
    identities: dict[str, str] = {}
    subject_pattern = re.compile(rb"^[ \t]*<([^<>\\\x00-\x20]+)>[ \t]+<")
    try:
        with path.open("rb") as source:
            while prefix := source.readline(4096):
                match = subject_pattern.match(prefix)
                if match is not None:
                    subject = match.group(1)
                    digest = hashlib.sha256(subject).hexdigest()[:24]
                    for kind in ("candidate", "node"):
                        handle = f"{kind}-h-{digest}"
                        if handle not in expected:
                            continue
                        try:
                            identity = subject.decode("utf-8", "strict")
                        except UnicodeError as error:
                            raise PortableExportFailure("EXPORT_INTEGRITY_FAILED") from error
                        previous = identities.get(handle)
                        if previous is not None and previous != identity:
                            raise PortableExportFailure("EXPORT_INTEGRITY_FAILED")
                        identities[handle] = identity
                if not prefix.endswith(b"\n"):
                    while remainder := source.readline(64 * 1024):
                        if remainder.endswith(b"\n"):
                            break
    except OSError as error:
        raise PortableExportFailure("EXPORT_SOURCE_UNAVAILABLE", status_code=503) from error
    if identities.keys() != expected:
        raise PortableExportFailure("EXPORT_INTEGRITY_FAILED")
    return identities
def _write_operational_payloads(
    database: OperationalDatabase,
    engine: Engine | None,
    project_id: str,
    workflows_path: Path,
    connectors_path: Path,
    receipts_path: Path,
    corrections_path: Path,
    candidate_identities: Mapping[str, str],
) -> tuple[dict[str, object], dict[str, object]]:
    if engine is None:
        raise PortableExportFailure("EXPORT_SOURCE_UNAVAILABLE", status_code=503)
    sqlite_result = _write_sqlite_workflows(
        database, project_id, workflows_path, candidate_identities
    )
    sqlite_count = sum(cast(Mapping[str, int], sqlite_result["record_counts"]).values())
    postgres_result = _write_postgres_payloads(
        engine,
        project_id,
        connectors_path,
        receipts_path,
        corrections_path,
        record_limit=MAX_LOGICAL_RECORDS - sqlite_count,
    )
    count = sqlite_count + sum(cast(Mapping[str, int], postgres_result["record_counts"]).values())
    if count > MAX_LOGICAL_RECORDS:
        raise PortableExportFailure("EXPORT_TOO_LARGE", status_code=413)
    return sqlite_result, postgres_result


def _write_sqlite_workflows(
    database: OperationalDatabase,
    project_id: str,
    destination: Path,
    candidate_identities: Mapping[str, str],
) -> dict[str, object]:
    counts: dict[str, int] = {}
    schema_versions: tuple[int, ...]
    with database.read_transaction() as connection:
        versions = tuple(
            int(row["version"])
            for row in connection.execute(
                "SELECT version FROM schema_migrations ORDER BY version"
            ).fetchall()
        )
        if versions != (1, 2, 3):
            raise PortableExportFailure("EXPORT_UNSUPPORTED_VERSION")
        schema_versions = versions
        for table, expected in _SQLITE_TABLE_COLUMNS.items():
            found = frozenset(
                str(row["name"])
                for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
            )
            if found != expected:
                raise PortableExportFailure("EXPORT_UNSUPPORTED_VERSION")
        _reject_active_suggestions(connection, project_id)
        with destination.open("xb") as output:
            _write_json_object_start(output, "schemaVersion", 1)
            workflow_arrays: tuple[tuple[str, Iterator[dict[str, object]]], ...] = (
                ("structuredNoteDrafts", _structured_note_drafts(connection, project_id)),
                ("candidateEdits", _candidate_edits(connection, project_id, candidate_identities)),
                ("suggestionWorkflows", _suggestion_workflows(connection, project_id)),
                ("suggestionAttempts", _suggestion_attempts(connection, project_id)),
                ("authoringCostEvents", _authoring_cost_events(connection, project_id)),
            )
            record_total = 0
            for field, records in workflow_arrays:
                output.write(b",")
                _write_json_key(output, field)
                output.write(b"[")
                count = _write_json_records(
                    output, records, limit=MAX_LOGICAL_RECORDS - record_total
                )
                counts[field] = count
                record_total += count
                output.write(b"]")
            output.write(b"}")
            output.flush()
            os.fsync(output.fileno())
    return {"record_counts": counts, "schema_versions": schema_versions}


def _write_postgres_payloads(
    engine: Engine,
    project_id: str,
    connectors_path: Path,
    receipts_path: Path,
    corrections_path: Path,
    *,
    record_limit: int = MAX_LOGICAL_RECORDS,
) -> dict[str, object]:
    try:
        from projecta_api.operational.schema import (
            ConnectorAuditRecord,
            ConnectorCursor,
            ConnectorDeadLetter,
            ConnectorEventInbox,
            ConnectorInstallation,
            ConnectorSyncAttempt,
            ConnectorSyncRun,
            CorrectionBurdenEvent,
            ReviewDecisionReceipt,
        )

        expected_models = (
            ConnectorInstallation,
            ConnectorEventInbox,
            ConnectorSyncRun,
            ConnectorSyncAttempt,
            ConnectorCursor,
            ConnectorDeadLetter,
            ConnectorAuditRecord,
            ReviewDecisionReceipt,
            CorrectionBurdenEvent,
        )
        with engine.connect() as connection:
            connection = connection.execution_options(isolation_level="REPEATABLE READ")
            with connection.begin():
                connection.exec_driver_sql("SET TRANSACTION READ ONLY")
                inspector = inspect(connection)
                for model in expected_models:
                    table_name = model.__tablename__
                    actual = frozenset(
                        column["name"] for column in inspector.get_columns(table_name)
                    )
                    expected = frozenset(column.name for column in model.__table__.columns)
                    if actual != expected:
                        raise PortableExportFailure("EXPORT_UNSUPPORTED_VERSION")
                server_version = str(connection.execute(text("SHOW server_version")).scalar_one())
                if server_version != "16.15":
                    raise PortableExportFailure("EXPORT_UNSUPPORTED_VERSION")
                head_rows = connection.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalars().all()
                if tuple(str(item) for item in head_rows) != (
                    "0012_project_purge_exception",
                ):
                    raise PortableExportFailure("EXPORT_UNSUPPORTED_VERSION")
                _reject_active_connectors(connection, project_id)
                counts, inbox_references = _write_connector_json(
                    connection, project_id, connectors_path, limit=record_limit
                )
                record_total = sum(counts.values())
                receipt_records, receipt_digests = _read_and_write_receipts(
                    connection,
                    project_id,
                    receipts_path,
                    limit=record_limit - record_total,
                )
                record_total += receipt_records
                correction_count = _write_correction_events(
                    connection,
                    project_id,
                    corrections_path,
                    receipt_digests,
                    limit=record_limit - record_total,
                )
                record_counts = {
                    **counts,
                    "reviewReceipts": receipt_records,
                    "correctionBurdenEvents": correction_count,
                }
    except PortableExportFailure:
        raise
    except Exception as error:  # noqa: BLE001 - a missing/unavailable store aborts, never returns empty rows.
        raise PortableExportFailure("EXPORT_SOURCE_UNAVAILABLE", status_code=503) from error
    return {
        "record_counts": record_counts,
        "alembic_head": "0012_project_purge_exception",
        "server_version": server_version,
        "receipt_digests": receipt_digests,
        "inbox_references": inbox_references,
    }

def _write_connector_json(
    connection: Connection,
    project_id: str,
    destination: Path,
    *,
    limit: int,
) -> tuple[dict[str, int], frozenset[str]]:
    table_fields: tuple[tuple[str, str, str, str], ...] = (
        (
            "installations",
            "connector_installations",
            "installation_id",
            "installation_id, project_id, connector_type, "
            "capability_snapshot -> 'capabilities' AS capabilities, enabled, revision, created_at, updated_at",
        ),
        (
            "inbox",
            "connector_event_inbox",
            "event_id, installation_id",
            "event_id, installation_id, project_id, body_hash, content_reference, accepted_outcome, "
            "accepted_at, conflict_count, conflict_last_seen_at, created_at, updated_at",
        ),
        (
            "runs",
            "connector_sync_runs",
            "run_id",
            "run_id, installation_id, project_id, status, started_at, terminal_at, terminal_outcome, "
            "revision, event_count, replay_count, dead_letter_id, idempotency_key, retry_of_run_id, "
            "failure_code, failure_detail, created_at, updated_at",
        ),
        ("attempts", "connector_sync_attempts", "run_id, attempt_number", ""),
        (
            "cursors",
            "connector_cursors",
            "installation_id",
            "installation_id, project_id, checkpoint, revision, updated_at",
        ),
        (
            "deadLetters",
            "connector_dead_letters",
            "dead_letter_id",
            "dead_letter_id, installation_id, project_id, run_id, event_id, failure_code, "
            "sanitized_detail, created_at, resolved_at",
        ),
        (
            "auditEvents",
            "connector_audit_records",
            "audit_id",
            "audit_id, project_id, installation_id, operation, outcome, actor_reference, "
            "correlation_id, revision, recorded_at",
        ),
    )
    counts: dict[str, int] = {}
    record_total = 0
    inbox_references: set[str] = set()
    installations = {
        cast(str, row[0]): cast(str, row[1])
        for row in connection.execute(
            text(
                "SELECT installation_id, connector_type FROM connector_installations "
                "WHERE project_id = :project_id"
            ),
            {"project_id": project_id},
        ).all()
    }
    with destination.open("xb") as output:
        _write_json_object_start(output, "schemaVersion", 1)
        for field, table, order, columns in table_fields:
            output.write(b",")
            _write_json_key(output, field)
            output.write(b"[")
            if field == "attempts":
                statement = text(
                    "SELECT a.run_id, a.attempt_number, a.status, a.started_at, a.terminal_at, "
                    "a.outcome, a.failure_code, a.failure_detail, r.project_id "
                    "FROM connector_sync_attempts AS a "
                    "JOIN connector_sync_runs AS r ON r.run_id = a.run_id "
                    "WHERE r.project_id = :project_id ORDER BY a.run_id, a.attempt_number"
                )
            else:
                statement = text(
                    f"SELECT {columns} FROM {table} "
                    f"WHERE project_id = :project_id ORDER BY {order}"
                )
            records = connection.execute(statement, {"project_id": project_id}).mappings()

            def mapped_records() -> Iterator[dict[str, object]]:
                for row in records:
                    record = _connector_record(
                        field, cast(Mapping[str, object], row), project_id, installations
                    )
                    if field == "inbox":
                        inbox_references.add(_text(record["contentReference"]))
                    yield record

            count = _write_json_records(
                output, mapped_records(), limit=limit - record_total
            )
            counts[field] = count
            record_total += count
            output.write(b"]")
        output.write(b"}")
        output.flush()
        os.fsync(output.fileno())
    _validate_connector_relationships(connection, project_id)
    return counts, frozenset(inbox_references)


def _connector_record(
    collection: str,
    row: Mapping[str, object],
    project_id: str,
    installations: Mapping[str, str],
) -> dict[str, object]:
    if row.get("project_id") != project_id:
        raise PortableExportFailure("EXPORT_INTEGRITY_FAILED")
    if collection == "installations":
        connector = _text(row.get("connector_type"))
        if connector not in {"json-mock", "teams", "github-public-issues"}:
            raise PortableExportFailure("EXPORT_UNSUPPORTED_STATE")
        capabilities = row.get("capabilities")
        allowed: dict[str, tuple[str, ...]] = {
            "json-mock": ("inbound-import", "resource-fetch", "cancellation"),
            "teams": ("inbound-import",),
            "github-public-issues": ("inbound-import",),
        }
        if not isinstance(capabilities, list) or not capabilities or any(
            not isinstance(value, str) or value not in allowed[connector] for value in capabilities
        ):
            raise PortableExportFailure("EXPORT_UNSUPPORTED_STATE")
        return {
            "installationId": _text(row.get("installation_id")),
            "projectId": project_id,
            "connectorType": connector,
            "capabilities": capabilities,
            "enabled": _bool(row.get("enabled")),
            "revision": _int(row.get("revision")),
            "createdAt": _db_timestamp(row.get("created_at")),
            "updatedAt": _db_timestamp(row.get("updated_at")),
        }
    if collection == "inbox":
        installation_id = _text(row.get("installation_id"))
        if installations.get(installation_id) is None:
            raise PortableExportFailure("EXPORT_INTEGRITY_FAILED")
        return {
            "eventId": _text(row.get("event_id")),
            "installationId": installation_id,
            "projectId": project_id,
            "bodyHash": _hex_digest(row.get("body_hash")),
            "contentReference": _text(row.get("content_reference")),
            "acceptedOutcome": _nullable_text(row.get("accepted_outcome")),
            "acceptedAt": _nullable_db_timestamp(row.get("accepted_at")),
            "conflictCount": _int(row.get("conflict_count")),
            "conflictLastSeenAt": _nullable_db_timestamp(row.get("conflict_last_seen_at")),
            "createdAt": _db_timestamp(row.get("created_at")),
            "updatedAt": _db_timestamp(row.get("updated_at")),
        }
    if collection == "runs":
        installation_id = _text(row.get("installation_id"))
        if installations.get(installation_id) is None:
            raise PortableExportFailure("EXPORT_INTEGRITY_FAILED")
        status_value = _text(row.get("status"))
        terminal = row.get("terminal_at")
        terminal_outcome = row.get("terminal_outcome")
        if (terminal is None) != (terminal_outcome is None):
            raise PortableExportFailure("EXPORT_INTEGRITY_FAILED")
        if terminal is None or status_value in {"running", "pending", "in_progress"}:
            raise PortableExportFailure("EXPORT_BUSY")
        return {
            "runId": _text(row.get("run_id")),
            "installationId": installation_id,
            "projectId": project_id,
            "status": status_value,
            "startedAt": _db_timestamp(row.get("started_at")),
            "terminalAt": _db_timestamp(terminal),
            "terminalOutcome": _text(terminal_outcome),
            "revision": _int(row.get("revision")),
            "eventCount": _int(row.get("event_count")),
            "replayCount": _int(row.get("replay_count")),
            "deadLetterId": _nullable_int(row.get("dead_letter_id")),
            "idempotencyDigest": _digest_text(_text(row.get("idempotency_key"))),
            "retryOfRunId": _nullable_text(row.get("retry_of_run_id")),
            "failureCode": _nullable_text(row.get("failure_code")),
            "failureDetail": _bounded_nullable_text(row.get("failure_detail"), 2048),
            "createdAt": _db_timestamp(row.get("created_at")),
            "updatedAt": _db_timestamp(row.get("updated_at")),
        }
    if collection == "attempts":
        if row.get("terminal_at") is None or _text(row.get("status")) in {"running", "pending", "in_progress"}:
            raise PortableExportFailure("EXPORT_BUSY")
        return {
            "runId": _text(row.get("run_id")),
            "attemptNumber": _int(row.get("attempt_number")),
            "status": _text(row.get("status")),
            "startedAt": _db_timestamp(row.get("started_at")),
            "terminalAt": _db_timestamp(row.get("terminal_at")),
            "outcome": _nullable_text(row.get("outcome")),
            "failureCode": _nullable_text(row.get("failure_code")),
            "failureDetail": _bounded_nullable_text(row.get("failure_detail"), 2048),
        }
    if collection == "cursors":
        installation_id = _text(row.get("installation_id"))
        connector_type = installations.get(installation_id)
        if connector_type is None:
            raise PortableExportFailure("EXPORT_INTEGRITY_FAILED")
        checkpoint = _nullable_text(row.get("checkpoint"))
        _validate_cursor(connector_type, checkpoint)
        return {
            "installationId": installation_id,
            "projectId": project_id,
            "checkpoint": checkpoint,
            "revision": _int(row.get("revision")),
            "updatedAt": _db_timestamp(row.get("updated_at")),
        }
    if collection == "deadLetters":
        installation_id = _text(row.get("installation_id"))
        if installations.get(installation_id) is None:
            raise PortableExportFailure("EXPORT_INTEGRITY_FAILED")
        return {
            "deadLetterId": _int(row.get("dead_letter_id")),
            "installationId": installation_id,
            "projectId": project_id,
            "runId": _nullable_text(row.get("run_id")),
            "eventId": _nullable_text(row.get("event_id")),
            "failureCode": _text(row.get("failure_code")),
            "sanitizedDetail": _bounded_text(row.get("sanitized_detail"), 2048),
            "createdAt": _db_timestamp(row.get("created_at")),
            "resolvedAt": _nullable_db_timestamp(row.get("resolved_at")),
        }
    if collection == "auditEvents":
        installation_id = _nullable_text(row.get("installation_id"))
        if installation_id is not None and installations.get(installation_id) is None:
            raise PortableExportFailure("EXPORT_INTEGRITY_FAILED")
        return {
            "auditId": _int(row.get("audit_id")),
            "projectId": project_id,
            "installationId": installation_id,
            "operation": _bounded_text(row.get("operation"), 64),
            "outcome": _bounded_text(row.get("outcome"), 32),
            "actorDigest": _digest_text(_bounded_text(row.get("actor_reference"), 256)),
            "correlationId": _bounded_text(row.get("correlation_id"), 128),
            "revision": _nullable_int(row.get("revision")),
            "recordedAt": _db_timestamp(row.get("recorded_at")),
        }
    raise PortableExportFailure("EXPORT_UNSUPPORTED_STATE")


def _validate_cursor(connector_type: str, checkpoint: str | None) -> None:
    """Validate only the recognized v1 connector cursors; unknown codecs fail as unsupported."""
    if checkpoint is None:
        return
    if connector_type == "teams":
        match = _TEAMS_CURSOR.fullmatch(checkpoint)
        if match is None:
            raise PortableExportFailure("EXPORT_UNSUPPORTED_STATE")
        try:
            datetime.fromisoformat(match.group(1)).astimezone(UTC)
        except ValueError as error:
            raise PortableExportFailure("EXPORT_UNSUPPORTED_STATE") from error
        return
    if connector_type == "github-public-issues":
        try:
            GitHubCursorCodec.decode(checkpoint)
        except Exception as error:
            raise PortableExportFailure("EXPORT_UNSUPPORTED_STATE") from error
        return
    if connector_type == "json-mock":
        try:
            index = int(checkpoint)
        except ValueError as error:
            raise PortableExportFailure("EXPORT_UNSUPPORTED_STATE") from error
        if index < 0 or index > 100:
            raise PortableExportFailure("EXPORT_UNSUPPORTED_STATE")
        return
    raise PortableExportFailure("EXPORT_UNSUPPORTED_STATE")


def _reject_active_connectors(connection: Connection, project_id: str) -> None:
    running_run = connection.execute(
        text(
            "SELECT 1 FROM connector_sync_runs WHERE project_id = :p "
            "AND (terminal_at IS NULL OR status IN ('running','pending','in_progress')) LIMIT 1"
        ),
        {"p": project_id},
    ).first()
    running_attempt = connection.execute(
        text(
            "SELECT 1 FROM connector_sync_attempts a JOIN connector_sync_runs r USING (run_id) "
            "WHERE r.project_id = :p AND (a.terminal_at IS NULL OR a.status IN ('running','pending','in_progress')) LIMIT 1"
        ),
        {"p": project_id},
    ).first()
    if running_run is not None or running_attempt is not None:
        raise PortableExportFailure("EXPORT_BUSY")


def _validate_connector_relationships(connection: Connection, project_id: str) -> None:
    checks = (
        "SELECT 1 FROM connector_sync_runs r LEFT JOIN connector_installations i "
        "ON i.installation_id = r.installation_id AND i.project_id = r.project_id "
        "WHERE r.project_id = :p AND i.installation_id IS NULL LIMIT 1",
        "SELECT 1 FROM connector_sync_runs r LEFT JOIN connector_sync_runs parent "
        "ON parent.run_id = r.retry_of_run_id AND parent.project_id = r.project_id "
        "WHERE r.project_id = :p AND r.retry_of_run_id IS NOT NULL AND parent.run_id IS NULL LIMIT 1",
        "SELECT 1 FROM connector_sync_runs r LEFT JOIN connector_dead_letters d "
        "ON d.dead_letter_id = r.dead_letter_id AND d.project_id = r.project_id AND d.run_id = r.run_id "
        "WHERE r.project_id = :p AND r.dead_letter_id IS NOT NULL AND d.dead_letter_id IS NULL LIMIT 1",
        "SELECT 1 FROM connector_dead_letters d LEFT JOIN connector_sync_runs r "
        "ON r.run_id = d.run_id AND r.project_id = d.project_id "
        "WHERE d.project_id = :p AND d.run_id IS NOT NULL AND r.run_id IS NULL LIMIT 1",
        "SELECT 1 FROM connector_dead_letters d LEFT JOIN connector_event_inbox e "
        "ON e.event_id = d.event_id AND e.installation_id = d.installation_id "
        "AND e.project_id = d.project_id WHERE d.project_id = :p AND d.event_id IS NOT NULL "
        "AND e.event_id IS NULL LIMIT 1",
        "SELECT 1 FROM connector_cursors c LEFT JOIN connector_installations i "
        "ON i.installation_id = c.installation_id AND i.project_id = c.project_id "
        "WHERE c.project_id = :p AND i.installation_id IS NULL LIMIT 1",
        "SELECT 1 FROM connector_audit_records a LEFT JOIN connector_installations i "
        "ON i.installation_id = a.installation_id AND i.project_id = a.project_id "
        "WHERE a.project_id = :p AND a.installation_id IS NOT NULL AND i.installation_id IS NULL LIMIT 1",
    )
    for statement in checks:
        if connection.execute(text(statement), {"p": project_id}).first() is not None:
            raise PortableExportFailure("EXPORT_INTEGRITY_FAILED")

def _read_and_write_receipts(
    connection: Connection,
    project_id: str,
    destination: Path,
    *,
    limit: int,
) -> tuple[int, frozenset[str]]:
    from projecta_api.operational.schema import ReviewDecisionReceipt

    statement = (
        select(ReviewDecisionReceipt)
        .where(ReviewDecisionReceipt.project_id == project_id)
        .order_by(
            ReviewDecisionReceipt.item_kind,
            ReviewDecisionReceipt.item_handle_digest,
            ReviewDecisionReceipt.sequence,
        )
    )
    groups: dict[tuple[str, str], tuple[int, str | None, str | None, int | None]] = {}
    receipt_digests: set[str] = set()
    count = 0
    with destination.open("xb") as output:
        for row in connection.execute(statement):
            try:
                record = _receipt_from_row(row, "accepted")
                request_digest = _validate_receipt(row, record)
            except PortableExportFailure:
                raise
            except Exception as error:  # noqa: BLE001 - malformed source history is not a valid export.
                raise PortableExportFailure("EXPORT_INTEGRITY_FAILED") from error
            key = (record.item_kind, record.item_handle_digest)
            previous = groups.get(key)
            expected_sequence = 1 if previous is None else previous[0] + 1
            expected_previous = None if previous is None else previous[1]
            if record.sequence != expected_sequence or record.previous_decision_digest != expected_previous:
                raise PortableExportFailure("EXPORT_INTEGRITY_FAILED")
            if previous is not None and (
                previous[2] != record.source_version_digest
                or previous[3] != record.source_version_revision
            ):
                raise PortableExportFailure("EXPORT_INTEGRITY_FAILED")
            groups[key] = (
                record.sequence,
                record.receipt_digest,
                record.source_version_digest,
                record.source_version_revision,
            )
            _write_json_line(
                output, _receipt_export_value(record, project_id, request_digest)
            )
            receipt_digests.add(record.receipt_digest)
            count += 1
            if count > limit:
                raise PortableExportFailure("EXPORT_TOO_LARGE", status_code=413)
        output.flush()
        os.fsync(output.fileno())
    return count, frozenset(receipt_digests)


def _validate_receipt(row: object, record: ReviewDecisionReceiptRecord) -> str:
    source = cast(object, row)
    project_id = _text(getattr(source, "project_id", None))
    request_digest = _digest_format(_text(getattr(source, "request_digest", None)))
    receipt_id = _text(getattr(source, "receipt_id", None))
    occurred_at = getattr(source, "occurred_at", None)
    if (
        receipt_id != "rr1_" + request_digest.removeprefix("sha256:")
        or not isinstance(occurred_at, datetime)
        or occurred_at.tzinfo is None
        or occurred_at.utcoffset() is None
        or occurred_at != record.occurred_at
    ):
        raise PortableExportFailure("EXPORT_INTEGRITY_FAILED")
    expected_digest = _receipt_digest(request_digest, occurred_at)
    if record.project_digest != _digest_text(project_id) or record.receipt_digest != expected_digest:
        raise PortableExportFailure("EXPORT_INTEGRITY_FAILED")
    return request_digest


def _receipt_export_value(
    record: ReviewDecisionReceiptRecord, project_id: str, request_digest: str
) -> dict[str, object]:
    return {
        "receiptId": record.receipt_id,
        "projectId": project_id,
        "actorDigest": record.actor_digest,
        "authorizationDigest": record.authorization_digest,
        "itemKind": record.item_kind,
        "itemHandleDigest": record.item_handle_digest,
        "decision": record.decision,
        "candidateRevision": record.candidate_revision,
        "sourceVersionDigest": record.source_version_digest,
        "sourceVersionRevision": record.source_version_revision,
        "constrainedContractVersion": record.constrained_contract_version,
        "evidenceDigest": record.evidence_digest,
        "previousDecisionDigest": record.previous_decision_digest,
        "idempotencyDigest": record.idempotency_digest,
        "requestDigest": request_digest,
        "sequence": record.sequence,
        "occurredAt": _format_timestamp(record.occurred_at),
        "receiptDigest": record.receipt_digest,
    }

def _write_correction_events(
    connection: Connection,
    project_id: str,
    destination: Path,
    receipt_digests: frozenset[str],
    *,
    limit: int,
) -> int:
    from projecta_api.extraction.correction_burden import TelemetryIntegrityError
    from projecta_api.operational.schema import CorrectionBurdenEvent

    statement = (
        select(CorrectionBurdenEvent)
        .where(CorrectionBurdenEvent.project_id == project_id)
        .order_by(CorrectionBurdenEvent.occurred_at, CorrectionBurdenEvent.event_id)
    )
    count = 0
    with destination.open("xb") as output:
        for row in connection.execute(statement):
            try:
                record = _event_from_row(row, "accepted")
            except (TelemetryIntegrityError, ValueError, TypeError) as error:
                raise PortableExportFailure("EXPORT_INTEGRITY_FAILED") from error
            if (
                record.project_digest != _digest_text(project_id)
                or record.review_receipt_digest not in receipt_digests
            ):
                raise PortableExportFailure("EXPORT_INTEGRITY_FAILED")
            _write_json_line(output, _correction_export_value(record, project_id))
            count += 1
            if count > limit:
                raise PortableExportFailure("EXPORT_TOO_LARGE", status_code=413)
        output.flush()
        os.fsync(output.fileno())
    return count


def _correction_export_value(record: CorrectionBurdenEventRecord, project_id: str) -> dict[str, object]:
    return {
        "eventId": record.event_id,
        "projectId": project_id,
        "itemKind": record.item_kind,
        "itemDigest": record.item_digest,
        "assertionDigest": record.assertion_digest,
        "sourceVersionDigest": record.source_version_digest,
        "sourceVersionRevision": record.source_version_revision,
        "reviewReceiptDigest": record.review_receipt_digest,
        "materializationRevision": record.materialization_revision,
        "inferenceRevision": record.inference_revision,
        "correctionCategory": record.correction_category,
        "correctionDimensions": list(record.correction_dimensions),
        "reviewOutcome": record.review_outcome,
        "semanticEditCount": record.semantic_edit_count,
        "reviewLatencyMs": record.review_latency_ms,
        "materializationState": record.materialization_state,
        "inferenceState": record.inference_state,
        "idempotencyDigest": record.idempotency_digest,
        "requestDigest": _correction_request_digest(record, project_id),
        "occurredAt": _format_timestamp(record.occurred_at),
        "eventDigest": record.event_digest,
    }


def _correction_request_digest(record: CorrectionBurdenEventRecord, project_id: str) -> str:
    from projecta_api.extraction.correction_burden import _request_digest_from_event

    return _request_digest_from_event(project_id, record)


def _reject_active_suggestions(connection: sqlite3.Connection, project_id: str) -> None:
    pending_workflow = connection.execute(
        "SELECT 1 FROM local_suggestion_workflows WHERE project_id = ? AND state = 'pending' LIMIT 1",
        (project_id,),
    ).fetchone()
    pending_attempt = connection.execute(
        "SELECT 1 FROM local_suggestion_attempts WHERE project_id = ? AND state = 'pending' LIMIT 1",
        (project_id,),
    ).fetchone()
    if pending_workflow is not None or pending_attempt is not None:
        raise PortableExportFailure("EXPORT_BUSY")


def _structured_note_drafts(
    connection: sqlite3.Connection, project_id: str
) -> Iterator[dict[str, object]]:
    rows = connection.execute(
        "SELECT handle, project_id, actor_id, revision, payload, fingerprint, idempotency_key, "
        "committed_note_id, created_at, updated_at FROM structured_note_drafts "
        "WHERE project_id = ? ORDER BY handle",
        (project_id,),
    )
    for raw in rows:
        row = cast(Mapping[str, object], raw)
        _check_project(row["project_id"], project_id)
        payload_text = _text(row["payload"])
        payload_value = _load_json(payload_text)
        draft = StructuredNoteDraft.model_validate(payload_value)
        if draft.model_dump(mode="json", by_alias=True) != payload_value:
            raise PortableExportFailure("EXPORT_UNSUPPORTED_STATE")
        payload_digest = sha256(payload_text.encode("utf-8", "strict")).hexdigest()
        stored_fingerprint = _text(row["fingerprint"])
        committed_note_id = _nullable_text(row["committed_note_id"])
        if committed_note_id is None:
            fingerprint_matches = stored_fingerprint == payload_digest
        else:
            fingerprint_matches = (
                draft.draft_status == "committed"
                and stored_fingerprint
                in {
                    structured_note_draft_fingerprint(
                        draft.model_copy(update={"draft_status": status})
                    )
                    for status in get_args(NoteDraftStatus)
                }
            )
        if not fingerprint_matches:
            raise PortableExportFailure("EXPORT_INTEGRITY_FAILED")
        yield {
            "sourceHandle": _text(row["handle"]),
            "projectId": project_id,
            "actorId": _bounded_text(row["actor_id"], 128),
            "revision": _positive_int(row["revision"]),
            "draft": payload_value,
            "payloadDigest": payload_digest,
            "idempotencyDigest": _digest_text(_text(row["idempotency_key"])),
            "committedNoteId": committed_note_id,
            "createdAt": _sqlite_timestamp(row["created_at"]),
            "updatedAt": _sqlite_timestamp(row["updated_at"]),
        }


def _candidate_edits(
    connection: sqlite3.Connection,
    project_id: str,
    candidate_identities: Mapping[str, str],
) -> Iterator[dict[str, object]]:
    rows = connection.execute(
        "SELECT edit_handle, project_id, candidate_handle, actor_id, request_id, revision, payload, created_at "
        "FROM structured_candidate_edits WHERE project_id = ? ORDER BY candidate_handle, revision",
        (project_id,),
    )
    for raw in rows:
        row = cast(Mapping[str, object], raw)
        _check_project(row["project_id"], project_id)
        source_candidate_handle = _text(row["candidate_handle"])
        candidate_id = candidate_identities.get(source_candidate_handle)
        if candidate_id is None:
            raise PortableExportFailure("EXPORT_INTEGRITY_FAILED")
        payload = _load_json(_text(row["payload"]))
        edit = StructuredCandidateEditRequest.model_validate(payload)
        if edit.model_dump(mode="json", by_alias=True) != payload:
            raise PortableExportFailure("EXPORT_UNSUPPORTED_STATE")
        yield {
            "sourceEditHandle": _text(row["edit_handle"]),
            "projectId": project_id,
            "sourceCandidateHandle": source_candidate_handle,
            "candidateId": candidate_id,
            "actorId": _bounded_text(row["actor_id"], 128),
            "requestId": _bounded_text(row["request_id"], 128),
            "revision": _positive_int(row["revision"]),
            "corrections": payload,
            "createdAt": _sqlite_timestamp(row["created_at"]),
        }


def _suggestion_workflows(connection: sqlite3.Connection, project_id: str) -> Iterator[dict[str, object]]:
    rows = connection.execute(
        "SELECT workflow_id, project_id, source_version_digest, source_version_revision, item_handle_digest, "
        "item_revision, evidence_digest, state, proposal_json, proposal_revision, model_id, error_code, "
        "latest_receipt_digest, created_at, updated_at FROM local_suggestion_workflows "
        "WHERE project_id = ? ORDER BY workflow_id",
        (project_id,),
    )
    for raw in rows:
        row = cast(Mapping[str, object], raw)
        _check_project(row["project_id"], project_id)
        state = _text(row["state"])
        if state == "pending":
            raise PortableExportFailure("EXPORT_BUSY")
        if state not in {"failed", "proposed", "edited", "confirmed", "rejected", "abstained"}:
            raise PortableExportFailure("EXPORT_UNSUPPORTED_STATE")
        proposal: object = None
        raw_proposal = row["proposal_json"]
        if raw_proposal is not None:
            proposal = LocalSuggestionProposal.model_validate(_load_json(_text(raw_proposal))).model_dump(
                mode="json", by_alias=True, exclude_none=True
            )
        yield {
            "workflowId": _digest_format(_text(row["workflow_id"])),
            "projectId": project_id,
            "sourceVersionDigest": _digest_format(_text(row["source_version_digest"])),
            "sourceVersionRevision": _positive_int(row["source_version_revision"]),
            "itemHandleDigest": _digest_format(_text(row["item_handle_digest"])),
            "itemRevision": _positive_int(row["item_revision"]),
            "evidenceDigest": _digest_format(_text(row["evidence_digest"])),
            "state": state,
            "proposal": proposal,
            "proposalRevision": _int(row["proposal_revision"]),
            "modelId": _nullable_bounded_text(row["model_id"], 128),
            "errorCode": _nullable_bounded_text(row["error_code"], 64),
            "latestReceiptDigest": _nullable_digest(row["latest_receipt_digest"]),
            "createdAt": _sqlite_timestamp(row["created_at"]),
            "updatedAt": _sqlite_timestamp(row["updated_at"]),
        }


def _suggestion_attempts(connection: sqlite3.Connection, project_id: str) -> Iterator[dict[str, object]]:
    rows = connection.execute(
        "SELECT attempt_id, project_id, actor_digest, workflow_id, idempotency_digest, request_digest, "
        "state, error_code, requested_at FROM local_suggestion_attempts "
        "WHERE project_id = ? ORDER BY requested_at, attempt_id",
        (project_id,),
    )
    for raw in rows:
        row = cast(Mapping[str, object], raw)
        _check_project(row["project_id"], project_id)
        state = _text(row["state"])
        if state == "pending":
            raise PortableExportFailure("EXPORT_BUSY")
        if state not in {"completed", "failed"}:
            raise PortableExportFailure("EXPORT_UNSUPPORTED_STATE")
        yield {
            "attemptId": _digest_format(_text(row["attempt_id"])),
            "projectId": project_id,
            "actorDigest": _digest_format(_text(row["actor_digest"])),
            "workflowId": _digest_format(_text(row["workflow_id"])),
            "idempotencyDigest": _digest_format(_text(row["idempotency_digest"])),
            "requestDigest": _digest_format(_text(row["request_digest"])),
            "state": state,
            "errorCode": _nullable_bounded_text(row["error_code"], 64),
            "requestedAt": _sqlite_timestamp(row["requested_at"]),
        }


def _authoring_cost_events(connection: sqlite3.Connection, project_id: str) -> Iterator[dict[str, object]]:
    expected = _digest_text(project_id)
    rows = connection.execute(
        "SELECT event_id, project_digest, actor_digest, workflow_digest, workflow_kind, event_type, "
        "attempt_digest, receipt_digest, assertion_digest, decision, local_inference_units, correction_category, "
        "correction_dimensions, semantic_edit_count, review_latency_ms, occurred_at FROM authoring_cost_events "
        "WHERE project_digest = ? ORDER BY occurred_at, event_id",
        (expected,),
    )
    for raw in rows:
        row = cast(Mapping[str, object], raw)
        if row["project_digest"] != expected:
            raise PortableExportFailure("EXPORT_INTEGRITY_FAILED")
        dimensions = _load_json(_text(row["correction_dimensions"]))
        if not isinstance(dimensions, list) or any(not isinstance(item, str) for item in dimensions):
            raise PortableExportFailure("EXPORT_UNSUPPORTED_STATE")
        yield {
            "eventId": _bounded_text(row["event_id"], 128),
            "projectId": project_id,
            "actorDigest": _digest_format(_text(row["actor_digest"])),
            "workflowDigest": _nullable_digest(row["workflow_digest"]),
            "workflowKind": _bounded_text(row["workflow_kind"], 16),
            "eventType": _bounded_text(row["event_type"], 32),
            "attemptDigest": _nullable_digest(row["attempt_digest"]),
            "receiptDigest": _nullable_digest(row["receipt_digest"]),
            "assertionDigest": _nullable_digest(row["assertion_digest"]),
            "decision": _nullable_text(row["decision"]),
            "localInferenceUnits": _int(row["local_inference_units"]),
            "correctionCategory": _nullable_text(row["correction_category"]),
            "correctionDimensions": dimensions,
            "semanticEditCount": _int(row["semantic_edit_count"]),
            "reviewLatencyMs": _nullable_int(row["review_latency_ms"]),
            "occurredAt": _sqlite_timestamp(row["occurred_at"]),
        }


def _manifest(
    project_id: str,
    project_name: str,
    producer: dict[str, object],
    collection: _Collection,
) -> dict[str, object]:
    evidence = [item.manifest_value() for item in collection.evidence_references]
    counts = collection.logical_record_counts
    return {
        "portableContract": PORTABLE_CONTRACT,
        "exportId": str(uuid.uuid4()),
        "exportedAt": _format_timestamp(datetime.now(UTC)),
        "project": {"projectId": project_id, "projectName": project_name, "tenantId": None},
        "sourceRevision": collection.source_revision,
        "producer": producer,
        "evidenceReferences": evidence,
        "counts": {
            "namedGraphs": 5,
            "evidenceObjects": len(evidence),
            "workflowRecords": sum(value for key, value in counts.items() if key.startswith("workflow.")),
            "connectorRecords": sum(
                value for key, value in counts.items() if key.startswith("postgres.") and key not in {"postgres.reviewReceipts", "postgres.correctionBurdenEvents"}
            ),
            "reviewReceipts": counts.get("postgres.reviewReceipts", 0),
            "correctionBurdenEvents": counts.get("postgres.correctionBurdenEvents", 0),
        },
        "entries": [item.manifest_entry() for item in collection.payloads],
    }


def _producer_inventory(collection: _Collection) -> dict[str, object]:
    if collection.postgres_alembic_head != "0012_project_purge_exception":
        raise PortableExportFailure("EXPORT_UNSUPPORTED_VERSION")
    if collection.sqlite_schema_versions != (1, 2, 3) or collection.postgres_version != "16.15":
        raise PortableExportFailure("EXPORT_UNSUPPORTED_VERSION")
    if platform.python_version() != "3.12.10":
        raise PortableExportFailure("EXPORT_UNSUPPORTED_VERSION")
    return {
        "projectaVersion": "0.7.0",
        "apiVersion": "0.7.0",
        "webVersion": "0.7.0",
        "nativeRuntime": {
            "python": "3.12.10",
            "java": "21.0.12.1+1",
            "fuseki": "6.2.0",
            "postgresql": collection.postgres_version,
            "semanticCore": {"javalin": "7.2.2", "jena": "6.2.0"},
        },
        "postgresAlembicHead": collection.postgres_alembic_head,
        "sqliteSchemaVersions": list(collection.sqlite_schema_versions),
        "connectorContract": "connector-contract.v1",
        "reviewReceiptContract": REVIEW_RECEIPT_CONTRACT_VERSION,
        "correctionBurdenContract": CORRECTION_BURDEN_CONTRACT_VERSION,
        "ontologyAssets": _ontology_assets(),
    }


def _ontology_assets() -> list[dict[str, object]]:
    package_root = _package_root()
    ontology = package_root / "ontology"
    modules = (
        "core.ttl",
        "communication.ttl",
        "provenance.ttl",
        "temporal.ttl",
        "evidence.ttl",
        "llm-extraction-v04.ttl",
        "m4-retrieval.ttl",
        "rules/m4-rules.ttl",
    )
    paths = [ontology / name for name in modules]
    shapes = ontology / "shapes"
    if not shapes.is_dir():
        raise PortableExportFailure("EXPORT_UNSUPPORTED_VERSION")
    paths.extend(sorted(shapes.rglob("*.ttl"), key=lambda item: item.relative_to(package_root).as_posix()))
    if any(not path.is_file() or path.is_symlink() for path in paths):
        raise PortableExportFailure("EXPORT_UNSUPPORTED_VERSION")
    expected = {path.resolve() for path in paths}
    packaged_ttls = {
        path.resolve()
        for directory in (ontology, ontology / "shapes", ontology / "rules")
        if directory.is_dir()
        for path in directory.glob("*.ttl")
        if path.is_file()
    }
    if not expected <= packaged_ttls:
        raise PortableExportFailure("EXPORT_UNSUPPORTED_VERSION")
    assets: list[dict[str, object]] = []
    for path in sorted(paths, key=lambda item: item.relative_to(package_root).as_posix()):
        relative = path.relative_to(package_root).as_posix()
        if relative.startswith("ontology/shapes/"):
            asset_type = "shape"
        elif "/rules/" in relative or relative.startswith("ontology/rules/"):
            asset_type = "inference-rule"
        else:
            asset_type = "ontology"
        try:
            source = path.read_bytes()
            text_value = source.decode("utf-8", "strict")
        except (OSError, UnicodeError) as error:
            raise PortableExportFailure("EXPORT_SOURCE_UNAVAILABLE", status_code=503) from error
        versions = re.findall(r"owl:versionIRI\s+<([^>]+)>", text_value)
        if len(versions) > 1:
            raise PortableExportFailure("EXPORT_UNSUPPORTED_VERSION")
        assets.append(
            {
                "assetType": asset_type,
                "path": relative,
                "versionIri": versions[0] if versions else None,
                "sha256": hashlib.sha256(source).hexdigest(),
            }
        )
    if not assets:
        raise PortableExportFailure("EXPORT_UNSUPPORTED_VERSION")
    return assets


def _package_root() -> Path:
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "ontology" / "core.ttl").is_file():
            return candidate
    raise PortableExportFailure("EXPORT_UNSUPPORTED_VERSION")


def _write_archive(path: Path, manifest_bytes: bytes, payloads: Sequence[_Payload]) -> None:
    try:
        with path.open("w+b") as raw:
            bounded = _BoundedArchiveFile(raw, MAX_ARCHIVE_BYTES)
            with zipfile.ZipFile(bounded, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as archive:
                _write_zip_member(archive, "manifest.json", manifest_bytes)
                for payload in sorted(payloads, key=lambda item: item.path):
                    info = _zip_info(payload.path)
                    with archive.open(info, mode="w", force_zip64=True) as target:
                        with payload.file_path.open("rb") as source:
                            shutil.copyfileobj(source, target, length=1024 * 1024)
            raw.flush()
            os.fsync(raw.fileno())
    except PortableExportFailure:
        path.unlink(missing_ok=True)
        raise
    except (OSError, ValueError, zipfile.BadZipFile, RuntimeError) as error:
        path.unlink(missing_ok=True)
        raise PortableExportFailure("EXPORT_FAILED", status_code=503) from error


def _verify_archive(
    path: Path,
    manifest_bytes: bytes,
    payloads: Sequence[_Payload],
    expanded_limit: int,
    source_revision: str,
) -> None:
    if path.stat().st_size > MAX_ARCHIVE_BYTES:
        raise PortableExportFailure("EXPORT_TOO_LARGE", status_code=413)
    expected = {item.path: item for item in payloads}
    try:
        with zipfile.ZipFile(path, "r") as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            if len(infos) != len(expected) + 1 or len(infos) > MAX_ENTRIES:
                raise PortableExportFailure("EXPORT_INTEGRITY_FAILED")
            if names[0] != "manifest.json" or len({name.casefold() for name in names}) != len(names):
                raise PortableExportFailure("EXPORT_INTEGRITY_FAILED")
            if set(names) != set(expected) | {"manifest.json"}:
                raise PortableExportFailure("EXPORT_INTEGRITY_FAILED")
            archived_manifest = archive.read("manifest.json")
            if archived_manifest != manifest_bytes:
                raise PortableExportFailure("EXPORT_INTEGRITY_FAILED")
            try:
                manifest_value = _load_json(archived_manifest.decode("utf-8", "strict"))
            except (UnicodeError, PortableExportFailure) as error:
                raise PortableExportFailure("EXPORT_INTEGRITY_FAILED") from error
            if not isinstance(manifest_value, dict) or set(manifest_value) != {
                "portableContract",
                "exportId",
                "exportedAt",
                "project",
                "sourceRevision",
                "producer",
                "evidenceReferences",
                "counts",
                "entries",
            }:
                raise PortableExportFailure("EXPORT_INTEGRITY_FAILED")
            manifest_revision = manifest_value.get("sourceRevision")
            if (
                manifest_value.get("portableContract") != PORTABLE_CONTRACT
                or not isinstance(manifest_revision, str)
                or manifest_revision != source_revision
                or not _SOURCE_REVISION.fullmatch(manifest_revision)
            ):
                raise PortableExportFailure("EXPORT_INTEGRITY_FAILED")
            actual_expanded = 0
            for info in infos:
                if info.flag_bits & 1 or info.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}:
                    raise PortableExportFailure("EXPORT_INTEGRITY_FAILED")
                if info.external_attr >> 16 & 0o170000 not in {0, stat.S_IFREG}:
                    raise PortableExportFailure("EXPORT_INTEGRITY_FAILED")
                actual_expanded += info.file_size
                if actual_expanded > MAX_EXPANDED_BYTES:
                    raise PortableExportFailure("EXPORT_TOO_LARGE", status_code=413)
                if info.filename == "manifest.json":
                    if info.file_size > MAX_MANIFEST_BYTES:
                        raise PortableExportFailure("EXPORT_TOO_LARGE", status_code=413)
                    continue
                payload = expected[info.filename]
                if info.file_size != payload.size_bytes:
                    raise PortableExportFailure("EXPORT_INTEGRITY_FAILED")
                digest = hashlib.sha256()
                size = 0
                with archive.open(info, "r") as source:
                    while chunk := source.read(1024 * 1024):
                        size += len(chunk)
                        digest.update(chunk)
                        if size > payload.size_bytes:
                            raise PortableExportFailure("EXPORT_INTEGRITY_FAILED")
                if size != payload.size_bytes or digest.hexdigest() != payload.sha256:
                    raise PortableExportFailure("EXPORT_INTEGRITY_FAILED")
            if actual_expanded > expanded_limit:
                raise PortableExportFailure("EXPORT_INTEGRITY_FAILED")
            if archive.testzip() is not None:
                raise PortableExportFailure("EXPORT_INTEGRITY_FAILED")
    except PortableExportFailure:
        raise
    except (OSError, zipfile.BadZipFile, RuntimeError) as error:
        raise PortableExportFailure("EXPORT_INTEGRITY_FAILED") from error


def _zip_info(name: str) -> zipfile.ZipInfo:
    if not _safe_member_path(name):
        raise PortableExportFailure("EXPORT_INTEGRITY_FAILED")
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = (stat.S_IFREG | 0o600) << 16
    info.flag_bits |= 0x800
    return info


def _write_zip_member(archive: zipfile.ZipFile, name: str, data: bytes) -> None:
    info = _zip_info(name)
    archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=6)


def _safe_member_path(value: str) -> bool:
    if not value or value.startswith(("/", "\\")) or "\\" in value or re.match(r"^[A-Za-z]:", value):
        return False
    parts = value.split("/")
    return all(part not in {"", ".", ".."} for part in parts)


def _payload_from_file(path: str, role: str, media_type: str, file_path: Path) -> _Payload:
    if not _safe_member_path(path) or not file_path.is_file() or file_path.is_symlink():
        raise PortableExportFailure("EXPORT_INTEGRITY_FAILED")
    digest, size = _hash_file(file_path)
    return _Payload(path, role, media_type, file_path, size, digest)


def _hash_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    try:
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
                size += len(chunk)
    except OSError as error:
        raise PortableExportFailure("EXPORT_SOURCE_UNAVAILABLE", status_code=503) from error
    return digest.hexdigest(), size


def _write_json_object_start(output: object, first_key: str, value: int) -> None:
    stream = cast(object, output)
    write = getattr(stream, "write")
    write(b"{")
    _write_json_key(output, first_key)
    write(str(value).encode("ascii"))


def _write_json_key(output: object, value: str) -> None:
    getattr(output, "write")(_canonical_json(value))
    getattr(output, "write")(b":")


def _write_json_records(
    output: object, records: Iterable[dict[str, object]], *, limit: int = MAX_LOGICAL_RECORDS
) -> int:
    count = 0
    first = True
    for record in records:
        count += 1
        _require_record_limit(count)
        if count > limit:
            raise PortableExportFailure("EXPORT_TOO_LARGE", status_code=413)
        if not first:
            getattr(output, "write")(b",")
        first = False
        getattr(output, "write")(_canonical_json(record))
    return count


def _write_json_line(output: object, value: dict[str, object]) -> None:
    getattr(output, "write")(_canonical_json(value))
    getattr(output, "write")(b"\n")


def _canonical_json(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=False,
        ).encode("utf-8", "strict")
    except (TypeError, ValueError, UnicodeError) as error:
        raise PortableExportFailure("EXPORT_UNSUPPORTED_STATE") from error


def _load_json(value: str) -> object:
    def unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, item in pairs:
            if key in result:
                raise ValueError("duplicate JSON field")
            result[key] = item
        return result

    try:
        result = json.loads(value, object_pairs_hook=unique_pairs, parse_constant=_reject_json_constant)
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise PortableExportFailure("EXPORT_UNSUPPORTED_STATE") from error
    if isinstance(result, dict) and any(not isinstance(key, str) for key in result):
        raise PortableExportFailure("EXPORT_UNSUPPORTED_STATE")
    return result


def _reject_json_constant(value: str) -> object:
    raise ValueError(f"unsupported JSON constant: {value}")


def _write_timestamp(value: object) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise PortableExportFailure("EXPORT_UNSUPPORTED_STATE")
    return _format_timestamp(value)


def _format_timestamp(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise PortableExportFailure("EXPORT_UNSUPPORTED_STATE")
    normalized = value.astimezone(UTC).isoformat(timespec="microseconds")
    return normalized[:-6].rstrip("0").rstrip(".") + "Z"


def _db_timestamp(value: object) -> str:
    if not isinstance(value, datetime):
        raise PortableExportFailure("EXPORT_UNSUPPORTED_STATE")
    if value.tzinfo is None:
        raise PortableExportFailure("EXPORT_UNSUPPORTED_STATE")
    return _format_timestamp(value)


def _nullable_db_timestamp(value: object) -> str | None:
    return None if value is None else _db_timestamp(value)


def _sqlite_timestamp(value: object) -> str:
    if not isinstance(value, str):
        raise PortableExportFailure("EXPORT_UNSUPPORTED_STATE")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise PortableExportFailure("EXPORT_UNSUPPORTED_STATE") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise PortableExportFailure("EXPORT_UNSUPPORTED_STATE")
    return _format_timestamp(parsed)


def _validate_source_revision(value: str) -> None:
    if not isinstance(value, str) or not _SOURCE_REVISION.fullmatch(value):
        raise PortableExportFailure("EXPORT_INTEGRITY_FAILED")


def project_source_revision(project_overview: object, project_id: str) -> str:
    """Read the canonical project freshness revision from Semantic Core's response."""
    try:
        project = _mapping(_mapping(project_overview).get("project"))
    except PortableExportFailure as error:
        raise PortableExportFailure("EXPORT_INTEGRITY_FAILED") from error
    if project.get("projectId") != project_id:
        raise PortableExportFailure("EXPORT_INTEGRITY_FAILED")
    revision = project.get("freshnessRevision")
    if not isinstance(revision, str):
        raise PortableExportFailure("EXPORT_INTEGRITY_FAILED")
    _validate_source_revision(revision)
    return revision


async def _read_source_revision(
    semantic: SemanticSnapshotClient,
    context: TrustedRequestContext,
) -> str:
    try:
        overview = await semantic.request(
            context, "GET", f"/v1/projects/{context.project_id}/overview"
        )
    except SemanticCoreProblem as error:
        if error.code in {
            "EXPORT_BUSY",
            "EXPORT_INTEGRITY_FAILED",
            "EXPORT_SOURCE_UNAVAILABLE",
            "EXPORT_UNSUPPORTED_VERSION",
        }:
            status_code = error.status_code if error.status_code in {409, 503} else 503
            raise PortableExportFailure(error.code, status_code=status_code) from error
        raise PortableExportFailure("EXPORT_SOURCE_UNAVAILABLE", status_code=503) from error
    return project_source_revision(overview, context.project_id)


def _validate_evidence_metadata(project_id: str, metadata: EvidenceMetadata) -> None:
    if (
        metadata.project_scope != project_id
        or not _SHA256.fullmatch(metadata.sha256)
        or metadata.size_bytes < 0
        or metadata.size_bytes > MAX_EVIDENCE_BYTES
        or metadata.content_type not in {"application/json", "text/plain"}
        or metadata.retention_class != "connector-default"
        or metadata.contract_version != "connector-evidence.v1"
        or not metadata.evidence_reference.startswith("ev_")
    ):
        raise PortableExportFailure("EXPORT_UNSUPPORTED_STATE")
    source = metadata.source_reference
    if (
        not source
        or len(source) > 512
        or "\\" in source
        or ".." in source
        or re.match(r"^[A-Za-z]:", source)
        or any(ord(char) < 32 for char in source)
    ):
        raise PortableExportFailure("EXPORT_UNSUPPORTED_STATE")
    _format_timestamp(metadata.created_at)
    if metadata.retain_until is not None:
        _format_timestamp(metadata.retain_until)


def _ensure_private_directory(path: Path) -> None:
    try:
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
        if path.is_symlink() or not path.is_dir():
            raise PortableExportFailure("EXPORT_SOURCE_UNAVAILABLE", status_code=503)
        if os.name != "nt":
            os.chmod(path, 0o700)
    except OSError as error:
        raise PortableExportFailure("EXPORT_SOURCE_UNAVAILABLE", status_code=503) from error


def _fsync_directory(path: Path) -> None:
    if os.name == "nt":
        return
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _validate_project_name(value: str) -> None:
    if (
        not value
        or value != value.strip()
        or len(value) > 128
        or any(ord(char) < 32 or 0x7F <= ord(char) <= 0x9F for char in value)
    ):
        raise PortableExportFailure("EXPORT_UNSUPPORTED_STATE")


def _mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise PortableExportFailure("EXPORT_UNSUPPORTED_STATE")
    return cast(Mapping[str, object], value)


def _text(value: object) -> str:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise PortableExportFailure("EXPORT_UNSUPPORTED_STATE")
    return value


def _bounded_text(value: object, maximum: int) -> str:
    result = _text(value)
    if len(result) > maximum:
        raise PortableExportFailure("EXPORT_UNSUPPORTED_STATE")
    return result


def _nullable_text(value: object) -> str | None:
    return None if value is None else _text(value)


def _bounded_nullable_text(value: object, maximum: int) -> str | None:
    return None if value is None else _bounded_text(value, maximum)


def _nullable_bounded_text(value: object, maximum: int) -> str | None:
    return _bounded_nullable_text(value, maximum)


def _int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise PortableExportFailure("EXPORT_UNSUPPORTED_STATE")
    return value


def _positive_int(value: object) -> int:
    result = _int(value)
    if result < 1:
        raise PortableExportFailure("EXPORT_UNSUPPORTED_STATE")
    return result


def _nullable_int(value: object) -> int | None:
    return None if value is None else _int(value)


def _bool(value: object) -> bool:
    if not isinstance(value, bool):
        raise PortableExportFailure("EXPORT_UNSUPPORTED_STATE")
    return value


def _hex_digest(value: object) -> str:
    result = _text(value)
    if not _SHA256.fullmatch(result):
        raise PortableExportFailure("EXPORT_UNSUPPORTED_STATE")
    return result


def _digest_format(value: str) -> str:
    if _DIGEST.fullmatch(value):
        return value
    if _SHA256.fullmatch(value):
        return "sha256:" + value
    if value.startswith("ls1_") and _SHA256.fullmatch(value[4:]):
        return "sha256:" + value[4:]
    raise PortableExportFailure("EXPORT_UNSUPPORTED_STATE")


def _nullable_digest(value: object) -> str | None:
    return None if value is None else _digest_format(_text(value))


def _digest_text(value: str) -> str:
    marker = _PORTABLE_DIGEST_MARKER.fullmatch(value)
    if marker:
        return marker.group(1)
    return "sha256:" + hashlib.sha256(value.encode("utf-8", "strict")).hexdigest()


def _prefixed_digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _stable_json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8", "strict")


def _check_project(value: object, project_id: str) -> None:
    if value != project_id:
        raise PortableExportFailure("EXPORT_INTEGRITY_FAILED")


def _require_record_limit(value: int) -> None:
    if value > MAX_LOGICAL_RECORDS:
        raise PortableExportFailure("EXPORT_TOO_LARGE", status_code=413)


