"""Fail-closed staged importer for the owner-approved projecta-portable.v1 format."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import shutil
import stat
import uuid
import zipfile
import zlib
from collections.abc import AsyncIterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Protocol, cast

from sqlalchemy import Engine, inspect, text

from projecta_api.configuration.storage import OperationalDatabase
from projecta_api.context import TrustedActorContext
from projecta_api.evidence.local import LocalEvidenceStore
from projecta_api.extraction.correction_burden import (
    CORRECTION_BURDEN_CONTRACT_VERSION,
    _event_digest,
)
from projecta_api.extraction.review_receipts import (
    REVIEW_RECEIPT_CONTRACT_VERSION,
    _receipt_digest,
)
from projecta_api.portable_export import (
    MAX_ARCHIVE_BYTES,
    MAX_ENTRIES,
    MAX_EVIDENCE_BYTES,
    MAX_EVIDENCE_OBJECTS,
    MAX_EXPANDED_BYTES,
    MAX_LOGICAL_RECORDS,
    MAX_MANIFEST_BYTES,
    MAX_SEMANTIC_BYTES,
    MAX_SEMANTIC_TRIPLES,
    PORTABLE_CONTRACT,
    PortableExportFailure,
    _FIXED_MEMBERS,
    _PROJECT_ID,
    _SHA256,
    _canonical_json,
    _load_json,
    _ontology_assets,
    _validate_cursor,
)

_MAX_UPLOAD_CHUNK = 1024 * 1024
_MAX_EXPORT_TIME_LENGTH = 40
_SHA_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_PROJECT_NAME_CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f]")
_MANIFEST_KEYS = frozenset(
    {"portableContract", "exportId", "exportedAt", "project", "sourceRevision", "producer", "evidenceReferences", "counts", "entries"}
)
_EVIDENCE_KEYS = frozenset(
    {"evidenceReference", "sha256", "sizeBytes", "contentType", "createdAt", "retentionClass", "retainUntil", "sourceReference", "contractVersion"}
)
_ENTRY_KEYS = frozenset({"path", "role", "mediaType", "sizeBytes", "sha256"})
_COUNT_KEYS = frozenset(
    {"namedGraphs", "evidenceObjects", "workflowRecords", "connectorRecords", "reviewReceipts", "correctionBurdenEvents"}
)
_WORKFLOW_ARRAYS = (
    "structuredNoteDrafts",
    "candidateEdits",
    "suggestionWorkflows",
    "suggestionAttempts",
    "authoringCostEvents",
)
_CONNECTOR_ARRAYS = (
    "installations",
    "inbox",
    "runs",
    "attempts",
    "cursors",
    "deadLetters",
    "auditEvents",
)
_WORKFLOW_FIELDS: dict[str, frozenset[str]] = {
    "structuredNoteDrafts": frozenset({"sourceHandle", "projectId", "actorId", "revision", "draft", "payloadDigest", "idempotencyDigest", "committedNoteId", "createdAt", "updatedAt"}),
    "candidateEdits": frozenset({"sourceEditHandle", "projectId", "sourceCandidateHandle", "candidateId", "actorId", "requestId", "revision", "corrections", "createdAt"}),
    "suggestionWorkflows": frozenset({"workflowId", "projectId", "sourceVersionDigest", "sourceVersionRevision", "itemHandleDigest", "itemRevision", "evidenceDigest", "state", "proposal", "proposalRevision", "modelId", "errorCode", "latestReceiptDigest", "createdAt", "updatedAt"}),
    "suggestionAttempts": frozenset({"attemptId", "projectId", "actorDigest", "workflowId", "idempotencyDigest", "requestDigest", "state", "errorCode", "requestedAt"}),
    "authoringCostEvents": frozenset({"eventId", "projectId", "actorDigest", "workflowDigest", "workflowKind", "eventType", "attemptDigest", "receiptDigest", "assertionDigest", "decision", "localInferenceUnits", "correctionCategory", "correctionDimensions", "semanticEditCount", "reviewLatencyMs", "occurredAt"}),
}
_CONNECTOR_FIELDS: dict[str, frozenset[str]] = {
    "installations": frozenset({"installationId", "projectId", "connectorType", "capabilities", "enabled", "revision", "createdAt", "updatedAt"}),
    "inbox": frozenset({"eventId", "installationId", "projectId", "bodyHash", "contentReference", "acceptedOutcome", "acceptedAt", "conflictCount", "conflictLastSeenAt", "createdAt", "updatedAt"}),
    "runs": frozenset({"runId", "installationId", "projectId", "status", "startedAt", "terminalAt", "terminalOutcome", "revision", "eventCount", "replayCount", "deadLetterId", "idempotencyDigest", "retryOfRunId", "failureCode", "failureDetail", "createdAt", "updatedAt"}),
    "attempts": frozenset({"runId", "attemptNumber", "status", "startedAt", "terminalAt", "outcome", "failureCode", "failureDetail"}),
    "cursors": frozenset({"installationId", "projectId", "checkpoint", "revision", "updatedAt"}),
    "deadLetters": frozenset({"deadLetterId", "installationId", "projectId", "runId", "eventId", "failureCode", "sanitizedDetail", "createdAt", "resolvedAt"}),
    "auditEvents": frozenset({"auditId", "projectId", "installationId", "operation", "outcome", "actorDigest", "correlationId", "revision", "recordedAt"}),
}
_RECEIPT_FIELDS = frozenset({"receiptId", "projectId", "actorDigest", "authorizationDigest", "itemKind", "itemHandleDigest", "decision", "candidateRevision", "sourceVersionDigest", "sourceVersionRevision", "constrainedContractVersion", "evidenceDigest", "previousDecisionDigest", "idempotencyDigest", "requestDigest", "sequence", "occurredAt", "receiptDigest"})
_CORRECTION_FIELDS = frozenset({"eventId", "projectId", "itemKind", "itemDigest", "assertionDigest", "sourceVersionDigest", "sourceVersionRevision", "reviewReceiptDigest", "materializationRevision", "inferenceRevision", "correctionCategory", "correctionDimensions", "reviewOutcome", "semanticEditCount", "reviewLatencyMs", "materializationState", "inferenceState", "idempotencyDigest", "requestDigest", "occurredAt", "eventDigest"})


class PortableImportFailure(RuntimeError):
    """Finite import failure that contains no local path or source payload."""

    def __init__(self, code: str, *, status_code: int = 409) -> None:
        self.code = code
        self.status_code = status_code
        super().__init__(code)


class SemanticImportClient(Protocol):
    async def validate_portable_import(
        self,
        actor: TrustedActorContext,
        project_id: str,
        placeholder_name: str,
        project_name: str,
        trig_path: Path,
    ) -> Mapping[str, object]: ...

    async def apply_portable_import(
        self,
        actor: TrustedActorContext,
        project_id: str,
        placeholder_name: str,
        project_name: str,
        adopt_placeholder: bool,
        trig_path: Path,
    ) -> Mapping[str, object]: ...

    async def rollback_portable_import(
        self,
        actor: TrustedActorContext,
        project_id: str,
        placeholder_name: str,
        project_name: str,
        restore_placeholder: bool,
        trig_path: Path,
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class ImportPreview:
    token: str
    project_id: str
    project_name: str
    export_id: str
    exported_at: str
    archive_sha256: str
    size_bytes: int
    destination_action: str
    counts: Mapping[str, int]
    plaintext_warning: str

    def response(self) -> dict[str, object]:
        return {
            "importId": self.token,
            "projectId": self.project_id,
            "projectName": self.project_name,
            "exportId": self.export_id,
            "exportedAt": self.exported_at,
            "archiveSha256": self.archive_sha256,
            "sizeBytes": self.size_bytes,
            "destinationAction": self.destination_action,
            "counts": dict(self.counts),
            "plaintextWarning": self.plaintext_warning,
        }


@dataclass(frozen=True, slots=True)
class _ValidatedPackage:
    token: str
    directory: Path
    archive_path: Path
    archive_sha256: str
    archive_size: int
    manifest: Mapping[str, object]
    project_id: str
    project_name: str
    export_id: str
    exported_at: str
    payload_paths: Mapping[str, Path]
    workflows: Mapping[str, object]
    connectors: Mapping[str, object]
    receipts: tuple[Mapping[str, object], ...]
    corrections: tuple[Mapping[str, object], ...]
    evidence: tuple[Mapping[str, object], ...]


class ProjectPortableImportService:
    """Validate, stage, and recover one confirmed project import at a time."""

    def __init__(
        self,
        database: OperationalDatabase,
        postgres_engine: Engine | None,
        evidence_store: LocalEvidenceStore,
        semantic_core: SemanticImportClient,
        *,
        import_root: Path | None,
        registry_path: Path | None,
        restart_file: Path | None,
        runtime_id: str,
        native_runtime_lock_held: bool,
        context_secret: str,
        staging_copy: bool = False,
    ) -> None:
        self._database = database
        self._postgres_engine = postgres_engine
        self._evidence = evidence_store
        self._semantic = semantic_core
        self._root = import_root
        self._registry_path = registry_path
        self._restart_file = restart_file
        self._runtime_id = runtime_id
        self._native_runtime_lock_held = native_runtime_lock_held
        self._context_secret = context_secret
        self._staging_copy = staging_copy

    def enabled(self) -> bool:
        return bool(
            self._native_runtime_lock_held
            and self._postgres_engine is not None
            and self._root is not None
            and self._registry_path is not None
            and self._restart_file is not None
            and self._runtime_id
            and self._context_secret
        )

    async def create_preview(
        self,
        actor: TrustedActorContext,
        chunks: AsyncIterable[bytes],
    ) -> ImportPreview:
        if not self.enabled():
            raise PortableImportFailure("IMPORT_UNSUPPORTED_RUNTIME", status_code=503)
        assert self._root is not None
        _ensure_private_directory(self._root)
        token = str(uuid.uuid4())
        directory = self._root / "previews" / token
        _ensure_private_directory(directory.parent)
        directory.mkdir(mode=0o700)
        archive_path = directory / "package.projecta"
        digest = hashlib.sha256()
        observed = 0
        try:
            with archive_path.open("xb") as destination:
                async for chunk in chunks:
                    if not chunk:
                        continue
                    observed += len(chunk)
                    if observed > MAX_ARCHIVE_BYTES:
                        raise PortableImportFailure("IMPORT_TOO_LARGE", status_code=413)
                    digest.update(chunk)
                    await asyncio.to_thread(destination.write, chunk)
                await asyncio.to_thread(destination.flush)
                await asyncio.to_thread(os.fsync, destination.fileno())
            if observed == 0:
                raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
            package = await asyncio.to_thread(
                _validate_archive, token, directory, archive_path, digest.hexdigest(), observed
            )
            registry = _read_registry(self._registry_path)
            action, placeholder_name, semantic_validation = await self._destination_action(actor, package, registry)
            if semantic_validation is not None:
                _bounded_int(semantic_validation.get("tripleCount"), MAX_SEMANTIC_TRIPLES)
                candidate_ids = semantic_validation.get("candidateIds")
                if not isinstance(candidate_ids, list) or any(not isinstance(item, str) for item in candidate_ids):
                    raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
                workflow_map = cast(dict[str, object], package.workflows)
                for edit in _objects(workflow_map["candidateEdits"]):
                    if edit["candidateId"] not in candidate_ids:
                        raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
            _write_private_json(
                directory / "preview.json",
                {
                    "actorId": actor.actor_id,
                    "createdAt": datetime.now(UTC).isoformat(),
                    "projectId": package.project_id,
                    "exportId": package.export_id,
                    "archiveSha256": package.archive_sha256,
                    "archiveSize": package.archive_size,
                },
            )
            manifest_counts = _mapping(package.manifest["counts"])
            return ImportPreview(
                token=token,
                project_id=package.project_id,
                project_name=package.project_name,
                export_id=package.export_id,
                exported_at=package.exported_at,
                archive_sha256=package.archive_sha256,
                size_bytes=package.archive_size,
                destination_action=action,
                counts={key: cast(int, value) for key, value in manifest_counts.items()},
                plaintext_warning=(
                    "This unsigned, unencrypted package may contain sensitive source content. "
                    "SHA-256 detects accidental changes but does not authenticate its sender. "
                    "Only import a file you are authorized to move. Credentials and sessions are not transferred."
                ),
            )
        except BaseException:
            if directory.exists():
                await asyncio.to_thread(shutil.rmtree, directory, True)
            raise

    async def cancel_preview(self, actor: TrustedActorContext, token: str) -> None:
        package = self._preview_directory(token)
        owner = _read_private_json(package / "preview.json", "IMPORT_NOT_FOUND", status_code=404)
        if owner.get("actorId") != actor.actor_id:
            raise PortableImportFailure("IMPORT_NOT_FOUND", status_code=404)
        await asyncio.to_thread(shutil.rmtree, package, True)

    async def result(self, actor: TrustedActorContext, token: str) -> dict[str, object]:
        if not self.enabled():
            raise PortableImportFailure("IMPORT_UNSUPPORTED_RUNTIME", status_code=503)
        _valid_token(token)
        assert self._root is not None
        result_path = self._root / "results" / f"{token}.json"
        if result_path.exists():
            result = _read_private_json(result_path)
            if (
                type(result.get("formatVersion")) is not int
                or result.get("formatVersion") != 1
                or result.get("importId") != token
                or result.get("actorId") != actor.actor_id
                or not isinstance(result.get("status"), str)
                or result["status"] not in {"staging", "complete", "failed"}
            ):
                raise PortableImportFailure("IMPORT_NOT_FOUND", status_code=404)
            response: dict[str, object] = {
                "importId": token,
                "status": result["status"],
                "projectId": _bounded_string(result.get("projectId"), 63),
                "projectName": _bounded_string(result.get("projectName"), 128),
            }
            failure_code = result.get("failureCode")
            if failure_code is not None:
                response["failureCode"] = _bounded_string(failure_code, 64)
            return response
        journal_path = self._root / "journal.json"
        if journal_path.exists():
            journal = _read_private_json(journal_path)
            if (
                journal.get("phase") == "queued"
                and journal.get("token") == token
                and journal.get("actorId") == actor.actor_id
            ):
                return {
                    "importId": token,
                    "status": "staging",
                    "projectId": _bounded_string(journal.get("projectId"), 63),
                    "projectName": _bounded_string(journal.get("projectName"), 128),
                }
        raise PortableImportFailure("IMPORT_NOT_FOUND", status_code=404)

    async def apply(
        self,
        actor: TrustedActorContext,
        token: str,
        confirmed: bool,
    ) -> dict[str, object]:
        if not self.enabled():
            raise PortableImportFailure("IMPORT_UNSUPPORTED_RUNTIME", status_code=503)
        if confirmed is not True:
            raise PortableImportFailure("IMPORT_CONFIRMATION_REQUIRED", status_code=400)
        assert self._root is not None and self._registry_path is not None
        directory = self._preview_directory(token)
        metadata = _read_private_json(directory / "preview.json", "IMPORT_NOT_FOUND", status_code=404)
        if metadata.get("actorId") != actor.actor_id:
            raise PortableImportFailure("IMPORT_NOT_FOUND", status_code=404)
        archive_path = directory / "package.projecta"
        try:
            archive_size = archive_path.stat().st_size
        except OSError as error:
            raise PortableImportFailure("IMPORT_PACKAGE_INVALID") from error
        if archive_path.is_symlink():
            raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
        archive_sha, verified_size = await asyncio.to_thread(_hash_file, archive_path)
        if archive_sha != metadata.get("archiveSha256") or verified_size != archive_size:
            raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
        package = await asyncio.to_thread(
            _validate_archive, token, directory, archive_path, archive_sha, archive_size
        )
        registry = _read_registry(self._registry_path)
        action, placeholder_name, _ = await self._destination_action(actor, package, registry)
        if action == "already-imported":
            await asyncio.to_thread(shutil.rmtree, directory, True)
            return {
                "projectId": package.project_id,
                "projectName": package.project_name,
                "alreadyImported": True,
                "restartRequired": False,
            }
        if action == "conflict":
            raise PortableImportFailure("IMPORT_CONFLICT")
        self._check_relational_destination(package)
        self._validate_sqlite_destination(package)
        journal_path = self._root / "journal.json"
        if journal_path.exists():
            raise PortableImportFailure("IMPORT_BUSY")
        adopt_placeholder = action == "adopt-placeholder"
        journal = {
            "formatVersion": 1,
            "phase": "prepared",
            "token": token,
            "projectId": package.project_id,
            "projectName": package.project_name,
            "exportId": package.export_id,
            "archiveSha256": package.archive_sha256,
            "archiveSize": package.archive_size,
            "adoptPlaceholder": adopt_placeholder,
            "placeholderName": placeholder_name,
            "actorId": actor.actor_id,
            "expectedPostgresRows": _postgres_record_count(package),
        }
        if not self._staging_copy:
            try:
                registry_bytes = self._registry_path.read_bytes()
            except OSError as error:
                raise PortableImportFailure("IMPORT_DESTINATION_INVALID", status_code=503) from error
            journal["phase"] = "queued"
            journal["oldCatalogRevision"] = (
                "sha256:" + hashlib.sha256(registry_bytes).hexdigest()
            )
            _write_private_json(journal_path, journal)
            self._request_runtime_restart()
            return {
                "importId": token,
                "projectId": package.project_id,
                "projectName": package.project_name,
                "alreadyImported": False,
                "restartRequired": True,
                "status": "staging",
                "nextAction": (
                    "Projecta Local is preparing the import in a private destination copy. "
                    "The project will appear only after the complete staged state is published."
                ),
            }
        _write_private_json(journal_path, journal)
        try:
            semantic_result = await self._semantic.apply_portable_import(
                actor,
                package.project_id,
                placeholder_name,
                package.project_name,
                adopt_placeholder,
                package.payload_paths["payload/semantic/project.trig"],
            )
            candidate_handles = semantic_result.get("candidateHandles")
            if not isinstance(candidate_handles, dict) or any(
                not isinstance(key, str) or not isinstance(value, str)
                for key, value in candidate_handles.items()
            ):
                raise PortableImportFailure("IMPORT_FAILED", status_code=503)
            journal["phase"] = "semantic-applied"
            _write_private_json(journal_path, journal)
            await self._restore_evidence(package)
            journal["phase"] = "evidence-applied"
            _write_private_json(journal_path, journal)
            await asyncio.to_thread(
                self._restore_sqlite, package, cast(Mapping[str, str], candidate_handles)
            )
            journal["phase"] = "sqlite-applied"
            _write_private_json(journal_path, journal)
            await asyncio.to_thread(self._restore_postgres, package)
            journal["phase"] = "postgres-committed"
            _write_private_json(journal_path, journal)
            await asyncio.to_thread(self._write_ledger, package)
            journal["phase"] = "ledger-written"
            _write_private_json(journal_path, journal)
            updated_registry = _append_project(
                registry, package.project_id, package.project_name, adopt_placeholder
            )
            journal["phase"] = "publishing"
            _write_private_json(journal_path, journal)
            await asyncio.to_thread(_write_private_json, self._registry_path, updated_registry)
            journal["phase"] = "catalog-published"
            _write_private_json(journal_path, journal)
            self._request_runtime_restart()
            journal_path.unlink(missing_ok=True)
            await asyncio.to_thread(shutil.rmtree, directory, True)
            return {
                "projectId": package.project_id,
                "projectName": package.project_name,
                "alreadyImported": False,
                "restartRequired": True,
                "nextAction": "Projecta Local is restarting. Select the imported project from Projects when it is ready.",
            }
        except BaseException as error:
            try:
                committed = _import_is_committed(
                    self._postgres_engine,
                    package.project_id,
                    journal["expectedPostgresRows"],
                    cast(str, journal["phase"]),
                )
            except PortableImportFailure as recovery_error:
                self._request_recovery_restart()
                raise PortableImportFailure("IMPORT_RECOVERY_REQUIRED", status_code=503) from recovery_error
            if committed:
                # The PostgreSQL transaction is the commit boundary; retain the journal until catalog and ledger publication finish.
                self._request_recovery_restart()
                raise PortableImportFailure("IMPORT_RECOVERY_PENDING", status_code=503) from error
            try:
                await self._rollback_import(actor, package, adopt_placeholder, placeholder_name)
                journal_path.unlink(missing_ok=True)
                await asyncio.to_thread(shutil.rmtree, directory, True)
            except BaseException as recovery_error:
                self._request_recovery_restart()
                raise PortableImportFailure(
                    "IMPORT_RECOVERY_REQUIRED", status_code=503
                ) from recovery_error
            if isinstance(error, PortableImportFailure):
                raise
            raise PortableImportFailure("IMPORT_FAILED", status_code=503) from error

    async def recover_before_serving(self, actor_id: str) -> None:
        """Resolve an interrupted import before the native API begins serving requests."""
        if not self.enabled():
            return
        assert self._root is not None and self._registry_path is not None
        journal_path = self._root / "journal.json"
        if not journal_path.exists():
            return
        journal = _read_private_json(journal_path)
        phase = _bounded_string(journal.get("phase"), 32)
        journal_fields = {
            "formatVersion", "phase", "token", "projectId", "projectName", "exportId",
            "archiveSha256", "archiveSize", "adoptPlaceholder", "placeholderName", "actorId",
            "expectedPostgresRows",
        }
        if phase == "queued":
            journal_fields.add("oldCatalogRevision")
        if (
            set(journal) != journal_fields
            or journal.get("formatVersion") != 1
            or journal.get("actorId") != actor_id
        ):
            raise PortableImportFailure("IMPORT_RECOVERY_REQUIRED", status_code=503)
        token = _valid_token(journal.get("token"))
        project_id = _bounded_string(journal.get("projectId"), 63)
        project_name = _bounded_string(journal.get("projectName"), 128)
        export_id = _bounded_string(journal.get("exportId"), 64)
        archive_digest = _bounded_string(journal.get("archiveSha256"), 64)
        archive_size_expected = _bounded_int(
            journal.get("archiveSize"), MAX_ARCHIVE_BYTES, minimum=1
        )
        placeholder_name = _bounded_string(journal.get("placeholderName"), 128)
        adopt_placeholder = journal.get("adoptPlaceholder")
        if (
            not _SHA256.fullmatch(archive_digest)
            or type(adopt_placeholder) is not bool
        ):
            raise PortableImportFailure("IMPORT_RECOVERY_REQUIRED", status_code=503)
        if phase not in {
            "queued", "prepared", "semantic-applied", "evidence-applied", "sqlite-applied",
            "postgres-committed", "ledger-written", "publishing", "catalog-published",
        }:
            raise PortableImportFailure("IMPORT_RECOVERY_REQUIRED", status_code=503)
        if phase == "queued":
            if not self._staging_copy:
                raise PortableImportFailure("IMPORT_RECOVERY_REQUIRED", status_code=503)
            old_catalog_revision = _bounded_string(journal.get("oldCatalogRevision"), 71)
            try:
                current_catalog_revision = (
                    "sha256:" + hashlib.sha256(self._registry_path.read_bytes()).hexdigest()
                )
            except OSError as error:
                raise PortableImportFailure("IMPORT_RECOVERY_REQUIRED", status_code=503) from error
            if (
                not _SHA_DIGEST.fullmatch(old_catalog_revision)
                or old_catalog_revision != current_catalog_revision
            ):
                raise PortableImportFailure("IMPORT_RECOVERY_REQUIRED", status_code=503)
        elif not self._staging_copy:
            raise PortableImportFailure("IMPORT_RECOVERY_REQUIRED", status_code=503)
        registry = _read_registry(self._registry_path)
        if registry.get("actorId") != actor_id:
            raise PortableImportFailure("IMPORT_RECOVERY_REQUIRED", status_code=503)
        token_directory = self._preview_directory(token)
        archive_path = token_directory / "package.projecta"
        if archive_path.is_symlink() or not archive_path.is_file():
            raise PortableImportFailure("IMPORT_RECOVERY_REQUIRED", status_code=503)
        archive_sha, archive_size = await asyncio.to_thread(_hash_file, archive_path)
        if archive_sha != archive_digest or archive_size != archive_size_expected:
            raise PortableImportFailure("IMPORT_RECOVERY_REQUIRED", status_code=503)
        package = await asyncio.to_thread(
            _validate_archive, token, token_directory, archive_path, archive_sha, archive_size
        )
        if (
            package.project_id != project_id
            or package.project_name != project_name
            or package.export_id != export_id
        ):
            raise PortableImportFailure("IMPORT_RECOVERY_REQUIRED", status_code=503)
        actor = TrustedActorContext(actor_id=actor_id, request_id=f"import-recovery-{token[:12]}")
        if phase == "queued":
            journal_path.unlink(missing_ok=True)
            await self.apply(actor, token, True)
            return
        expected_rows = _bounded_int(journal.get("expectedPostgresRows"), MAX_LOGICAL_RECORDS)
        committed = _import_is_committed(
            self._postgres_engine, package.project_id, expected_rows, phase
        )
        if committed:
            await asyncio.to_thread(self._write_ledger, package)
            updated_registry = _append_project(registry, package.project_id, package.project_name, adopt_placeholder)
            await asyncio.to_thread(_write_private_json, self._registry_path, updated_registry)
            self._request_runtime_restart()
            journal_path.unlink(missing_ok=True)
            await asyncio.to_thread(shutil.rmtree, token_directory, True)
            return
        await self._rollback_import(
            actor, package, adopt_placeholder, placeholder_name
        )
        journal_path.unlink(missing_ok=True)
        await asyncio.to_thread(shutil.rmtree, token_directory, True)

    async def _destination_action(
        self,
        actor: TrustedActorContext,
        package: _ValidatedPackage,
        registry: Mapping[str, object],
    ) -> tuple[str, str, Mapping[str, object] | None]:
        if actor.actor_id != registry.get("actorId"):
            raise PortableImportFailure("IMPORT_UNAUTHORIZED", status_code=403)
        project_id = package.project_id
        projects = _registry_projects(registry)
        if project_id not in projects and len(projects) >= 100:
            raise PortableImportFailure("IMPORT_CATALOG_FULL", status_code=409)
        local_name = _registry_name(registry, "my-projecta-workspace")
        ledger = self._read_ledger()
        prior = ledger.get(package.export_id)
        if prior is not None:
            if prior == package.archive_sha256 and project_id in projects:
                return "already-imported", local_name, None
            return "conflict", local_name, None
        if project_id in projects:
            if project_id != "my-projecta-workspace" or not _is_placeholder_registry(
                registry, project_id, local_name
            ):
                return "conflict", local_name, None
            await self._check_local_empty(project_id)
            checked = await self._semantic.validate_portable_import(
                actor,
                project_id,
                local_name,
                package.project_name,
                package.payload_paths["payload/semantic/project.trig"],
            )
            if checked.get("destinationState") == "pristine-placeholder":
                return "adopt-placeholder", local_name, checked
            return "conflict", local_name, checked
        await self._check_local_empty(project_id)
        checked = await self._semantic.validate_portable_import(
            actor,
            project_id,
            local_name or package.project_name,
            package.project_name,
            package.payload_paths["payload/semantic/project.trig"],
        )
        if checked.get("destinationState") != "absent":
            return "conflict", local_name or package.project_name, checked
        return "add-project", local_name or package.project_name, checked

    async def _check_local_empty(self, project_id: str) -> None:
        if self._postgres_engine is None:
            raise PortableImportFailure("IMPORT_UNSUPPORTED_RUNTIME", status_code=503)
        with self._database.read_transaction() as database:
            for table in (
                "structured_note_drafts", "structured_candidate_edits", "local_suggestion_workflows",
                "local_suggestion_attempts", "local_suggestion_budget_counters",
            ):
                if database.execute(
                    f"SELECT 1 FROM {table} WHERE project_id = ? LIMIT 1", (project_id,)
                ).fetchone():
                    raise PortableImportFailure("IMPORT_CONFLICT")
            project_digest = _digest_text(project_id)
            if database.execute(
                "SELECT 1 FROM authoring_cost_events WHERE project_digest = ? LIMIT 1", (project_digest,)
            ).fetchone():
                raise PortableImportFailure("IMPORT_CONFLICT")
        if await self._evidence.list_project(project_id):
            raise PortableImportFailure("IMPORT_CONFLICT")
        with self._postgres_engine.connect() as pg:
            for table in (
                "connector_installations", "connector_event_inbox", "connector_sync_runs",
                "connector_cursors", "connector_dead_letters", "connector_audit_records",
                "review_decision_receipts", "correction_burden_events",
            ):
                if pg.execute(
                    text(f"SELECT 1 FROM {table} WHERE project_id = :project_id LIMIT 1"),
                    {"project_id": project_id},
                ).first():
                    raise PortableImportFailure("IMPORT_CONFLICT")

    def _validate_sqlite_destination(self, package: _ValidatedPackage) -> None:
        project_digest = _digest_text(package.project_id)
        workflows = _mapping(package.workflows)
        sqlite_ids = (
            ("local_suggestion_workflows", "workflow_id",
             ("ls1_" + _raw_digest(row["workflowId"]) for row in _objects(workflows["suggestionWorkflows"]))),
            ("local_suggestion_attempts", "attempt_id",
             (_raw_digest(row["attemptId"]) for row in _objects(workflows["suggestionAttempts"]))),
            ("authoring_cost_events", "event_id",
             (_bounded_string(row["eventId"], 128) for row in _objects(workflows["authoringCostEvents"]))),
        )
        with self._database.read_transaction() as connection:
            for table, project_column in (
                ("structured_note_drafts", "project_id"),
                ("structured_candidate_edits", "project_id"),
                ("local_suggestion_workflows", "project_id"),
                ("local_suggestion_attempts", "project_id"),
                ("local_suggestion_budget_counters", "project_id"),
            ):
                if connection.execute(
                    f"SELECT 1 FROM {table} WHERE {project_column} = ? LIMIT 1",
                    (package.project_id,),
                ).fetchone():
                    raise PortableImportFailure("IMPORT_CONFLICT")
            if connection.execute(
                "SELECT 1 FROM authoring_cost_events WHERE project_digest = ? LIMIT 1",
                (project_digest,),
            ).fetchone():
                raise PortableImportFailure("IMPORT_CONFLICT")
            for table, column, values in sqlite_ids:
                identifiers = tuple(values)
                if len(identifiers) != len(set(identifiers)):
                    raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
                for identifier in identifiers:
                    if connection.execute(
                        f"SELECT 1 FROM {table} WHERE {column} = ? LIMIT 1", (identifier,)
                    ).fetchone():
                        raise PortableImportFailure("IMPORT_CONFLICT")

    def _check_relational_destination(self, package: _ValidatedPackage) -> None:
        assert self._postgres_engine is not None
        if _postgres_record_count(package) == 0:
            return
        connector_data = _mapping(package.connectors)
        rows_by_table: tuple[tuple[str, str, str], ...] = (
            ("connector_installations", "installationId", "installation_id"),
            ("connector_event_inbox", "eventId", "event_id"),
            ("connector_sync_runs", "runId", "run_id"),
            ("review_decision_receipts", "receiptId", "receipt_id"),
            ("correction_burden_events", "eventId", "event_id"),
        )
        table_payload: dict[str, Sequence[Mapping[str, object]]] = {
            "connector_installations": _objects(connector_data["installations"]),
            "connector_event_inbox": _objects(connector_data["inbox"]),
            "connector_sync_runs": _objects(connector_data["runs"]),
            "review_decision_receipts": package.receipts,
            "correction_burden_events": package.corrections,
        }
        with self._postgres_engine.connect() as connection:
            inspector = inspect(connection)
            required = {
                "connector_installations", "connector_event_inbox", "connector_sync_runs", "connector_sync_attempts",
                "connector_cursors", "connector_dead_letters", "connector_audit_records", "review_decision_receipts",
                "correction_burden_events",
            }
            if not required <= set(inspector.get_table_names()):
                raise PortableImportFailure("IMPORT_UNSUPPORTED_VERSION", status_code=409)
            for table, field, column in rows_by_table:
                for row in table_payload[table]:
                    value = row[field]
                    if connection.execute(text(f"SELECT 1 FROM {table} WHERE {column} = :value LIMIT 1"), {"value": value}).first():
                        raise PortableImportFailure("IMPORT_CONFLICT")
            for row in _objects(connector_data["cursors"]):
                if connection.execute(
                    text("SELECT 1 FROM connector_cursors WHERE installation_id = :id LIMIT 1"),
                    {"id": row["installationId"]},
                ).first():
                    raise PortableImportFailure("IMPORT_CONFLICT")

    async def _restore_evidence(self, package: _ValidatedPackage) -> None:
        for reference in package.evidence:
            evidence_path = package.payload_paths[f"payload/evidence/sha256/{reference['sha256']}.bin"]
            await self._evidence.restore_portable(package.project_id, reference, evidence_path)

    def _restore_sqlite(
        self,
        package: _ValidatedPackage,
        candidate_handles: Mapping[str, str],
    ) -> None:
        data = _mapping(package.workflows)
        project_id = package.project_id
        with self._database.transaction() as db:
            for row in _objects(data["structuredNoteDrafts"]):
                from projecta_api.structured_note import StructuredNoteDraft
                from projecta_api.structured_note_store import (
                    _serialize,
                    structured_note_draft_fingerprint,
                )

                local_handle = "draft-h-" + uuid.uuid4().hex[:24]
                draft = StructuredNoteDraft.model_validate(row["draft"])
                payload_text = _serialize(draft)
                payload_sha = hashlib.sha256(payload_text.encode("utf-8")).hexdigest()
                if payload_sha != row["payloadDigest"]:
                    raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
                fingerprint = (
                    structured_note_draft_fingerprint(draft)
                    if row["committedNoteId"] is not None
                    else payload_sha
                )
                db.execute(
                    "INSERT INTO structured_note_drafts(handle,project_id,actor_id,revision,payload,fingerprint,idempotency_key,committed_note_id,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (
                        local_handle, project_id, _bounded_string(row["actorId"], 128),
                        _bounded_int(row["revision"], 2**31 - 1, minimum=1), payload_text, fingerprint,
                        _portable_marker("key", _digest(row["idempotencyDigest"])),
                        row["committedNoteId"], row["createdAt"], row["updatedAt"],
                    ),
                )
            for row in _objects(data["candidateEdits"]):
                candidate_id = _bounded_string(row["candidateId"], 512)
                candidate_handle = candidate_handles.get(candidate_id)
                if candidate_handle is None:
                    raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
                from projecta_api.structured_note import StructuredCandidateEditRequest

                edit = StructuredCandidateEditRequest.model_validate(row["corrections"])
                db.execute(
                    "INSERT INTO structured_candidate_edits(edit_handle,project_id,candidate_handle,actor_id,request_id,revision,payload,created_at) VALUES(?,?,?,?,?,?,?,?)",
                    (
                        "edit-h-" + uuid.uuid4().hex[:24], project_id, candidate_handle,
                        _bounded_string(row["actorId"], 128), _bounded_string(row["requestId"], 128),
                        _bounded_int(row["revision"], 2**31 - 1, minimum=1),
                        json.dumps(edit.model_dump(mode="json", by_alias=True), sort_keys=True),
                        row["createdAt"],
                    ),
                )
            for row in _objects(data["suggestionWorkflows"]):
                db.execute(
                    "INSERT INTO local_suggestion_workflows(workflow_id,project_id,source_version_digest,source_version_revision,item_handle_digest,item_revision,evidence_digest,state,proposal_json,proposal_revision,current_attempt_digest,attempt_started_at,model_id,error_code,latest_receipt_digest,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,? ,NULL,NULL,?,?,?,?,?)",
                    (
                        "ls1_" + _raw_digest(row["workflowId"]), project_id,
                        _raw_digest(row["sourceVersionDigest"]), row["sourceVersionRevision"],
                        _raw_digest(row["itemHandleDigest"]), row["itemRevision"],
                        _raw_digest(row["evidenceDigest"]), row["state"],
                        None if row["proposal"] is None else _canonical_json(row["proposal"]).decode("utf-8"),
                        row["proposalRevision"], row["modelId"], row["errorCode"], row["latestReceiptDigest"],
                        row["createdAt"], row["updatedAt"],
                    ),
                )
            for row in _objects(data["suggestionAttempts"]):
                db.execute(
                    "INSERT INTO local_suggestion_attempts(attempt_id,project_id,actor_digest,workflow_id,idempotency_digest,request_digest,state,error_code,requested_at) VALUES(?,?,?,?,?,?,?,?,?)",
                    (
                        _raw_digest(row["attemptId"]), project_id, _raw_digest(row["actorDigest"]),
                        "ls1_" + _raw_digest(row["workflowId"]), _raw_digest(row["idempotencyDigest"]),
                        _raw_digest(row["requestDigest"]), row["state"], row["errorCode"], row["requestedAt"],
                    ),
                )
            for row in _objects(data["authoringCostEvents"]):
                dimensions = json.dumps(row["correctionDimensions"], ensure_ascii=False, separators=(",", ":"))
                db.execute(
                    "INSERT INTO authoring_cost_events(event_id,project_digest,actor_digest,workflow_digest,workflow_kind,event_type,attempt_digest,receipt_digest,assertion_digest,decision,local_inference_units,correction_category,correction_dimensions,semantic_edit_count,review_latency_ms,occurred_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        row["eventId"], _digest_text(project_id), row["actorDigest"], row["workflowDigest"],
                        row["workflowKind"], row["eventType"], row["attemptDigest"], row["receiptDigest"],
                        row["assertionDigest"], row["decision"], row["localInferenceUnits"],
                        row["correctionCategory"], dimensions, row["semanticEditCount"],
                        row["reviewLatencyMs"], row["occurredAt"],
                    ),
                )

    def _restore_postgres(self, package: _ValidatedPackage) -> None:
        assert self._postgres_engine is not None
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

        data = _mapping(package.connectors)
        project_id = package.project_id
        parse_time = _datetime
        with self._postgres_engine.begin() as connection:
            installation_ids: set[str] = set()
            for row in _objects(data["installations"]):
                installation_id = _bounded_string(row["installationId"], 128)
                installation_ids.add(installation_id)
                connection.execute(
                    ConnectorInstallation.__table__.insert().values(
                        installation_id=installation_id,
                        project_id=project_id,
                        connector_type=row["connectorType"],
                        capability_snapshot=row["capabilities"],
                        secret_reference=None,
                        enabled=False,
                        revision=row["revision"],
                        created_at=parse_time(row["createdAt"]),
                        updated_at=parse_time(row["updatedAt"]),
                    )
                )
            for row in _objects(data["inbox"]):
                connection.execute(
                    ConnectorEventInbox.__table__.insert().values(
                        event_id=row["eventId"], installation_id=row["installationId"], project_id=project_id,
                        body_hash=row["bodyHash"], content_reference=row["contentReference"],
                        accepted_outcome=row["acceptedOutcome"], accepted_at=_nullable_datetime(row["acceptedAt"]),
                        conflict_count=row["conflictCount"], conflict_last_seen_at=_nullable_datetime(row["conflictLastSeenAt"]),
                        created_at=parse_time(row["createdAt"]), updated_at=parse_time(row["updatedAt"]),
                    )
                )
            runs = _objects(data["runs"])
            for row in runs:
                connection.execute(
                    ConnectorSyncRun.__table__.insert().values(
                        run_id=row["runId"], installation_id=row["installationId"], project_id=project_id,
                        status=row["status"], started_at=parse_time(row["startedAt"]), terminal_at=parse_time(row["terminalAt"]),
                        terminal_outcome=row["terminalOutcome"], revision=row["revision"], event_count=row["eventCount"],
                        replay_count=row["replayCount"], dead_letter_id=None,
                        idempotency_key=_portable_marker("key", _digest(row["idempotencyDigest"])),
                        retry_of_run_id=None, failure_code=row["failureCode"], failure_detail=row["failureDetail"],
                        created_at=parse_time(row["createdAt"]), updated_at=parse_time(row["updatedAt"]),
                    )
                )
            for row in _objects(data["attempts"]):
                connection.execute(
                    ConnectorSyncAttempt.__table__.insert().values(
                        run_id=row["runId"], attempt_number=row["attemptNumber"], status=row["status"],
                        started_at=parse_time(row["startedAt"]), terminal_at=parse_time(row["terminalAt"]),
                        outcome=row["outcome"], failure_code=row["failureCode"], failure_detail=row["failureDetail"],
                    )
                )
            for row in _objects(data["cursors"]):
                connection.execute(
                    ConnectorCursor.__table__.insert().values(
                        installation_id=row["installationId"], project_id=project_id,
                        checkpoint=row["checkpoint"], revision=row["revision"], updated_at=parse_time(row["updatedAt"]),
                    )
                )
            dead_letter_map: dict[int, int] = {}
            for row in _objects(data["deadLetters"]):
                source_id = cast(int, row["deadLetterId"])
                inserted_id = connection.execute(
                    ConnectorDeadLetter.__table__.insert().values(
                        installation_id=row["installationId"], project_id=project_id, run_id=row["runId"],
                        event_id=row["eventId"], failure_code=row["failureCode"],
                        sanitized_detail=row["sanitizedDetail"], created_at=parse_time(row["createdAt"]),
                        resolved_at=_nullable_datetime(row["resolvedAt"]),
                    ).returning(ConnectorDeadLetter.dead_letter_id)
                ).scalar_one()
                dead_letter_map[source_id] = cast(int, inserted_id)
            for row in runs:
                changes: dict[str, object] = {}
                if row["deadLetterId"] is not None:
                    changes["dead_letter_id"] = dead_letter_map[cast(int, row["deadLetterId"])]
                if row["retryOfRunId"] is not None:
                    changes["retry_of_run_id"] = row["retryOfRunId"]
                if changes:
                    connection.execute(
                        ConnectorSyncRun.__table__.update()
                        .where(ConnectorSyncRun.run_id == row["runId"])
                        .values(**changes)
                    )
            for row in _objects(data["auditEvents"]):
                connection.execute(
                    ConnectorAuditRecord.__table__.insert().values(
                        project_id=project_id, installation_id=row["installationId"], operation=row["operation"],
                        outcome=row["outcome"],
                        actor_reference=_portable_marker("actor", _digest(row["actorDigest"])),
                        correlation_id=row["correlationId"], revision=row["revision"],
                        recorded_at=parse_time(row["recordedAt"]),
                    )
                )
            for row in package.receipts:
                connection.execute(
                    ReviewDecisionReceipt.__table__.insert().values(
                        receipt_id=row["receiptId"], project_id=project_id, actor_digest=row["actorDigest"],
                        authorization_digest=row["authorizationDigest"], item_kind=row["itemKind"],
                        item_handle_digest=row["itemHandleDigest"], decision=row["decision"],
                        candidate_revision=row["candidateRevision"], source_version_digest=row["sourceVersionDigest"],
                        source_version_revision=row["sourceVersionRevision"],
                        constrained_contract_version=row["constrainedContractVersion"], evidence_digest=row["evidenceDigest"],
                        previous_decision_digest=row["previousDecisionDigest"], idempotency_digest=row["idempotencyDigest"],
                        request_digest=row["requestDigest"], sequence=row["sequence"], occurred_at=parse_time(row["occurredAt"]),
                        receipt_digest=row["receiptDigest"],
                    )
                )
            for row in package.corrections:
                connection.execute(
                    CorrectionBurdenEvent.__table__.insert().values(
                        event_id=row["eventId"], project_id=project_id, item_kind=row["itemKind"],
                        item_digest=row["itemDigest"], assertion_digest=row["assertionDigest"],
                        source_version_digest=row["sourceVersionDigest"], source_version_revision=row["sourceVersionRevision"],
                        review_receipt_digest=row["reviewReceiptDigest"], materialization_revision=row["materializationRevision"],
                        inference_revision=row["inferenceRevision"], correction_category=row["correctionCategory"],
                        correction_dimensions=row["correctionDimensions"], review_outcome=row["reviewOutcome"],
                        semantic_edit_count=row["semanticEditCount"], review_latency_ms=row["reviewLatencyMs"],
                        materialization_state=row["materializationState"], inference_state=row["inferenceState"],
                        idempotency_digest=row["idempotencyDigest"], request_digest=row["requestDigest"],
                        occurred_at=parse_time(row["occurredAt"]), event_digest=row["eventDigest"],
                    )
                )

    async def _rollback_import(
        self,
        actor: TrustedActorContext,
        package: _ValidatedPackage,
        adopt_placeholder: bool,
        placeholder_name: str,
    ) -> None:
        await self._semantic.rollback_portable_import(
            actor,
            package.project_id,
            placeholder_name,
            package.project_name,
            adopt_placeholder,
            package.payload_paths["payload/semantic/project.trig"],
        )
        await self._evidence.remove_project_for_import(package.project_id)
        await asyncio.to_thread(self._delete_sqlite_project, package.project_id)
        if self._postgres_engine is not None:
            count = await asyncio.to_thread(
                _postgres_project_count, self._postgres_engine, package.project_id
            )
            if count:
                raise PortableImportFailure("IMPORT_RECOVERY_REQUIRED", status_code=503)

    def _delete_sqlite_project(self, project_id: str) -> None:
        digest = "sha256:" + hashlib.sha256(project_id.encode("utf-8")).hexdigest()
        with self._database.transaction() as connection:
            connection.execute("DELETE FROM structured_candidate_edits WHERE project_id=?", (project_id,))
            connection.execute("DELETE FROM structured_note_drafts WHERE project_id=?", (project_id,))
            connection.execute("DELETE FROM local_suggestion_attempts WHERE project_id=?", (project_id,))
            connection.execute("DELETE FROM local_suggestion_workflows WHERE project_id=?", (project_id,))
            connection.execute("DELETE FROM authoring_cost_events WHERE project_digest=?", (digest,))

    def _write_ledger(self, package: _ValidatedPackage) -> None:
        assert self._root is not None
        ledger_path = self._root / "ledger.json"
        ledger = _read_private_json(ledger_path) if ledger_path.exists() else {"formatVersion": 1, "imports": {}}
        if set(ledger) != {"formatVersion", "imports"} or ledger.get("formatVersion") != 1:
            raise PortableImportFailure("IMPORT_RECOVERY_REQUIRED", status_code=503)
        imports = _mapping(ledger["imports"])
        existing = imports.get(package.export_id)
        if existing is not None and existing != package.archive_sha256:
            raise PortableImportFailure("IMPORT_CONFLICT")
        updated = dict(imports)
        updated[package.export_id] = package.archive_sha256
        _write_private_json(ledger_path, {"formatVersion": 1, "imports": updated})

    def _read_ledger(self) -> Mapping[str, str]:
        assert self._root is not None
        path = self._root / "ledger.json"
        if not path.exists():
            return {}
        value = _read_private_json(path)
        if set(value) != {"formatVersion", "imports"} or value.get("formatVersion") != 1:
            raise PortableImportFailure("IMPORT_RECOVERY_REQUIRED", status_code=503)
        imports = _mapping(value["imports"])
        if any(not isinstance(key, str) or not _SHA256.fullmatch(digest) for key, digest in imports.items()):
            raise PortableImportFailure("IMPORT_RECOVERY_REQUIRED", status_code=503)
        return cast(Mapping[str, str], imports)

    def _preview_directory(self, token: str) -> Path:
        valid = _valid_token(token)
        assert self._root is not None
        directory = self._root / "previews" / valid
        if not directory.is_dir() or directory.is_symlink():
            raise PortableImportFailure("IMPORT_NOT_FOUND", status_code=404)
        return directory

    def _request_runtime_restart(self) -> None:
        if self._staging_copy:
            return
        assert self._restart_file is not None
        _write_private_json(
            self._restart_file,
            {"runtimeId": self._runtime_id, "requestedAt": datetime.now(UTC).isoformat(), "restart": True},
        )

    def _request_recovery_restart(self) -> None:
        try:
            self._request_runtime_restart()
        except BaseException as error:
            raise PortableImportFailure("IMPORT_RECOVERY_REQUIRED", status_code=503) from error


def _validate_archive(
    token: str,
    directory: Path,
    archive_path: Path,
    archive_sha256: str,
    archive_size: int,
) -> _ValidatedPackage:
    if archive_size < 1 or archive_size > MAX_ARCHIVE_BYTES or not _SHA256.fullmatch(archive_sha256):
        raise PortableImportFailure("IMPORT_TOO_LARGE", status_code=413)
    expected_payloads = directory / "payload"
    if expected_payloads.is_dir() and not expected_payloads.is_symlink():
        return _revalidate_staged_archive(token, directory, archive_path, archive_sha256, archive_size)
    try:
        with zipfile.ZipFile(archive_path, "r") as archive:
            infos = archive.infolist()
            if not infos or len(infos) > MAX_ENTRIES:
                raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
            names = [info.filename for info in infos]
            if (
                len(names) != len(set(names))
                or len({name.casefold() for name in names}) != len(names)
                or any(not _safe_member(name) for name in names)
                or names[0] != "manifest.json"
            ):
                raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
            manifest_info = infos[0]
            if manifest_info.file_size > MAX_MANIFEST_BYTES or manifest_info.flag_bits & 1:
                raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
            manifest_bytes = archive.read(manifest_info)
            try:
                manifest_text = manifest_bytes.decode("utf-8", "strict")
                manifest_value = _load_json(manifest_text)
            except (UnicodeError, PortableExportFailure) as error:
                raise PortableImportFailure("IMPORT_PACKAGE_INVALID") from error
            manifest = _manifest(manifest_value)
            payload_entries = _manifest_entries(manifest)
            expected_names = {"manifest.json", *payload_entries}
            if set(names) != expected_names:
                raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
            expanded = 0
            payload_paths: dict[str, Path] = {}
            for info in infos:
                if (
                    info.flag_bits & 1
                    or info.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}
                    or info.is_dir()
                    or info.external_attr >> 16 & 0o170000 not in {0, stat.S_IFREG}
                ):
                    raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
                expanded += info.file_size
                if expanded > MAX_EXPANDED_BYTES:
                    raise PortableImportFailure("IMPORT_TOO_LARGE", status_code=413)
                if info.filename == "manifest.json":
                    continue
                entry = payload_entries[info.filename]
                if info.file_size != entry["sizeBytes"]:
                    raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
                target = directory / "payload" / Path(*PurePosixPath(info.filename).parts[1:])
                target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                digest = hashlib.sha256()
                observed = 0
                with archive.open(info, "r") as source, target.open("xb") as destination:
                    while True:
                        chunk = source.read(_MAX_UPLOAD_CHUNK)
                        if not chunk:
                            break
                        observed += len(chunk)
                        if observed > entry["sizeBytes"] or observed > MAX_EXPANDED_BYTES:
                            raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
                        digest.update(chunk)
                        destination.write(chunk)
                    destination.flush()
                if observed != entry["sizeBytes"] or digest.hexdigest() != entry["sha256"]:
                    raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
                payload_paths[info.filename] = target
    except PortableImportFailure:
        raise
    except (OSError, ValueError, zipfile.BadZipFile, RuntimeError, zlib.error) as error:
        raise PortableImportFailure("IMPORT_PACKAGE_INVALID") from error
    return _finish_archive_validation(
        token, directory, archive_path, archive_sha256, archive_size,
        manifest, payload_entries, payload_paths,
    )


def _revalidate_staged_archive(
    token: str,
    directory: Path,
    archive_path: Path,
    archive_sha256: str,
    archive_size: int,
) -> _ValidatedPackage:
    """Re-check an already-extracted preview without reopening its payload files for write."""
    try:
        with zipfile.ZipFile(archive_path, "r") as archive:
            infos = archive.infolist()
            if not infos or len(infos) > MAX_ENTRIES:
                raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
            manifest_bytes = archive.read("manifest.json")
            try:
                manifest = _manifest(_load_json(manifest_bytes.decode("utf-8", "strict")))
            except (UnicodeError, PortableExportFailure) as error:
                raise PortableImportFailure("IMPORT_PACKAGE_INVALID") from error
            payload_entries = _manifest_entries(manifest)
            if {info.filename for info in infos} != {"manifest.json", *payload_entries}:
                raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
            payload_paths: dict[str, Path] = {}
            for path, entry in payload_entries.items():
                target = directory / "payload" / Path(*PurePosixPath(path).parts[1:])
                if target.is_symlink() or not target.is_file():
                    raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
                digest, observed = _hash_file(target)
                if observed != entry["sizeBytes"] or digest != entry["sha256"]:
                    raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
                payload_paths[path] = target
    except PortableImportFailure:
        raise
    except (OSError, ValueError, zipfile.BadZipFile, RuntimeError, zlib.error) as error:
        raise PortableImportFailure("IMPORT_PACKAGE_INVALID") from error
    return _finish_archive_validation(
        token, directory, archive_path, archive_sha256, archive_size,
        manifest, payload_entries, payload_paths,
    )


def _finish_archive_validation(
    token: str,
    directory: Path,
    archive_path: Path,
    archive_sha256: str,
    archive_size: int,
    manifest: Mapping[str, object],
    payload_entries: Mapping[str, Mapping[str, object]],
    payload_paths: Mapping[str, Path],
) -> _ValidatedPackage:
    _ = payload_entries
    project = _mapping(manifest["project"])
    project_id = cast(str, project["projectId"])
    project_name = cast(str, project["projectName"])
    export_id = cast(str, manifest["exportId"])
    exported_at = cast(str, manifest["exportedAt"])
    _validate_producer(manifest["producer"])
    evidence = _validate_evidence(manifest["evidenceReferences"], project_id, payload_entries)
    workflows = _read_payload_json(payload_paths["payload/application/project-workflows.json"])
    connectors = _read_payload_json(payload_paths["payload/operations/connectors.json"])
    _validate_workflows(workflows, project_id)
    _validate_connectors(connectors, project_id, evidence)
    receipts = _read_json_lines(payload_paths["payload/receipts/review-decision-receipts.jsonl"], _RECEIPT_FIELDS)
    corrections = _read_json_lines(payload_paths["payload/receipts/correction-burden-events.jsonl"], _CORRECTION_FIELDS)
    _validate_receipts(receipts, project_id)
    _validate_corrections(corrections, project_id, receipts)
    _validate_archive_references(workflows, receipts)
    _check_no_secret_fields(workflows, connectors, receipts, corrections)
    counts = _mapping(manifest["counts"])
    workflow_count = sum(len(_objects(_mapping(workflows)[name])) for name in _WORKFLOW_ARRAYS)
    connector_count = sum(len(_objects(_mapping(connectors)[name])) for name in _CONNECTOR_ARRAYS)
    if (
        counts["evidenceObjects"] != len(evidence)
        or counts["workflowRecords"] != workflow_count
        or counts["connectorRecords"] != connector_count
        or counts["reviewReceipts"] != len(receipts)
        or counts["correctionBurdenEvents"] != len(corrections)
    ):
        raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
    if workflow_count + connector_count + len(receipts) + len(corrections) > MAX_LOGICAL_RECORDS:
        raise PortableImportFailure("IMPORT_TOO_LARGE", status_code=413)
    return _ValidatedPackage(
        token=token,
        directory=directory,
        archive_path=archive_path,
        archive_sha256=archive_sha256,
        archive_size=archive_size,
        manifest=manifest,
        project_id=project_id,
        project_name=project_name,
        export_id=export_id,
        exported_at=exported_at,
        payload_paths=dict(payload_paths),
        workflows=cast(Mapping[str, object], workflows),
        connectors=cast(Mapping[str, object], connectors),
        receipts=tuple(receipts),
        corrections=tuple(corrections),
        evidence=tuple(evidence),
    )


def _manifest(value: object) -> Mapping[str, object]:
    manifest = _mapping(value)
    if set(manifest) != _MANIFEST_KEYS or manifest.get("portableContract") != PORTABLE_CONTRACT:
        if manifest.get("portableContract") != PORTABLE_CONTRACT:
            raise PortableImportFailure("IMPORT_UNSUPPORTED_VERSION")
        raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
    export_id = _bounded_string(manifest["exportId"], 64)
    try:
        parsed_id = uuid.UUID(export_id)
    except ValueError as error:
        raise PortableImportFailure("IMPORT_PACKAGE_INVALID") from error
    if str(parsed_id) != export_id or parsed_id.version != 4:
        raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
    exported_at = _bounded_string(manifest["exportedAt"], _MAX_EXPORT_TIME_LENGTH)
    _datetime(exported_at)
    project = _mapping(manifest["project"])
    if set(project) != {"projectId", "projectName", "tenantId"}:
        raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
    project_id = _bounded_string(project["projectId"], 63)
    project_name = _bounded_string(project["projectName"], 128)
    if not _PROJECT_ID.fullmatch(project_id) or project["tenantId"] is not None:
        raise PortableImportFailure("IMPORT_DESTINATION_FORBIDDEN")
    if not project_name or project_name != project_name.strip() or _PROJECT_NAME_CONTROL.search(project_name):
        raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
    source_revision = _bounded_string(manifest["sourceRevision"], 64)
    if not re.fullmatch(r"catalog-r-[0-9a-f]{40}", source_revision):
        raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
    counts = _mapping(manifest["counts"])
    if set(counts) != _COUNT_KEYS or any(type(number) is not int or number < 0 for number in counts.values()):
        raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
    if counts["namedGraphs"] != 5 or counts["evidenceObjects"] > MAX_EVIDENCE_OBJECTS:
        raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
    if sum(counts[key] for key in ("workflowRecords", "connectorRecords", "reviewReceipts", "correctionBurdenEvents")) > MAX_LOGICAL_RECORDS:
        raise PortableImportFailure("IMPORT_TOO_LARGE", status_code=413)
    return manifest


def _manifest_entries(manifest: Mapping[str, object]) -> dict[str, Mapping[str, object]]:
    values = manifest.get("entries")
    if not isinstance(values, list) or len(values) + 1 > MAX_ENTRIES:
        raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
    expected_fixed = {member[0]: (member[1], member[2]) for member in _FIXED_MEMBERS}
    entries: dict[str, Mapping[str, object]] = {}
    seen_casefold: set[str] = set()
    for value in values:
        entry = _mapping(value)
        if set(entry) != _ENTRY_KEYS:
            raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
        path = _bounded_string(entry["path"], 1024)
        if not _safe_member(path) or path in entries or path.casefold() in seen_casefold:
            raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
        seen_casefold.add(path.casefold())
        if type(entry["sizeBytes"]) is not int or entry["sizeBytes"] < 0 or not _SHA256.fullmatch(_bounded_string(entry["sha256"], 64)):
            raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
        if path in expected_fixed:
            role, media = expected_fixed[path]
            if entry["role"] != role or entry["mediaType"] != media:
                raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
        elif path.startswith("payload/evidence/sha256/"):
            if entry["role"] != "evidence-object" or entry["mediaType"] not in {"application/json", "text/plain"}:
                raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
            filename = path.removeprefix("payload/evidence/sha256/")
            if not re.fullmatch(r"[0-9a-f]{64}\.bin", filename) or filename[:-4] != entry["sha256"]:
                raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
            if entry["sizeBytes"] > MAX_EVIDENCE_BYTES:
                raise PortableImportFailure("IMPORT_TOO_LARGE", status_code=413)
        else:
            raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
        entries[path] = entry
    if not set(expected_fixed) <= set(entries):
        raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
    if entries["payload/semantic/project.trig"]["sizeBytes"] > MAX_SEMANTIC_BYTES:
        raise PortableImportFailure("IMPORT_TOO_LARGE", status_code=413)
    return entries


def _validate_producer(value: object) -> None:
    producer = _mapping(value)
    try:
        expected_assets = _ontology_assets()
    except PortableExportFailure as error:
        raise PortableImportFailure("IMPORT_UNSUPPORTED_VERSION") from error
    expected = {
        "projectaVersion": "0.7.0",
        "apiVersion": "0.7.0",
        "webVersion": "0.7.0",
        "nativeRuntime": {
            "python": "3.12.10",
            "java": "21.0.12.1+1",
            "fuseki": "6.2.0",
            "postgresql": "16.15",
            "semanticCore": {"javalin": "7.2.2", "jena": "6.2.0"},
        },
        "postgresAlembicHead": "0011_review_receipts_append_only",
        "sqliteSchemaVersions": [1, 2, 3],
        "connectorContract": "connector-contract.v1",
        "reviewReceiptContract": REVIEW_RECEIPT_CONTRACT_VERSION,
        "correctionBurdenContract": CORRECTION_BURDEN_CONTRACT_VERSION,
        "ontologyAssets": expected_assets,
    }
    if producer != expected:
        raise PortableImportFailure("IMPORT_UNSUPPORTED_VERSION")


def _validate_evidence(
    value: object,
    project_id: str,
    entries: Mapping[str, Mapping[str, object]],
) -> list[Mapping[str, object]]:
    if not isinstance(value, list) or len(value) > MAX_EVIDENCE_OBJECTS:
        raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
    references: list[Mapping[str, object]] = []
    seen_ref: set[str] = set()
    seen_digest: set[str] = set()
    for raw in value:
        item = _mapping(raw)
        if set(item) != _EVIDENCE_KEYS:
            raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
        reference = _bounded_string(item["evidenceReference"], 32)
        digest = _bounded_string(item["sha256"], 64)
        size = _bounded_int(item["sizeBytes"], MAX_EVIDENCE_BYTES)
        content_type = _bounded_string(item["contentType"], 64)
        if (
            reference in seen_ref
            or digest in seen_digest
            or not re.fullmatch(r"ev_[A-Za-z0-9_-]{22}", reference)
            or not _SHA256.fullmatch(digest)
            or content_type not in {"application/json", "text/plain"}
        ):
            raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
        if item["retentionClass"] != "connector-default" or item["contractVersion"] != "connector-evidence.v1":
            raise PortableImportFailure("IMPORT_UNSUPPORTED_VERSION")
        if item["retainUntil"] is not None:
            _datetime(_bounded_string(item["retainUntil"], _MAX_EXPORT_TIME_LENGTH))
        _datetime(_bounded_string(item["createdAt"], _MAX_EXPORT_TIME_LENGTH))
        source = _bounded_string(item["sourceReference"], 512)
        if (
            source.startswith(("/", "\\"))
            or ".." in source
            or "\\" in source
            or re.match(r"^[A-Za-z]:", source)
            or _PROJECT_NAME_CONTROL.search(source)
        ):
            raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
        archive_path = f"payload/evidence/sha256/{digest}.bin"
        entry = entries.get(archive_path)
        if entry is None or entry["sizeBytes"] != size or entry["mediaType"] != content_type:
            raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
        seen_ref.add(reference)
        seen_digest.add(digest)
        references.append(item)
    evidence_entries = {path for path, value in entries.items() if value["role"] == "evidence-object"}
    if evidence_entries != {f"payload/evidence/sha256/{item['sha256']}.bin" for item in references}:
        raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
    return references


def _read_payload_json(path: Path) -> object:
    try:
        value = _load_json(path.read_text(encoding="utf-8", errors="strict"))
    except (OSError, UnicodeError, PortableExportFailure) as error:
        raise PortableImportFailure("IMPORT_PACKAGE_INVALID") from error
    return value


def _read_json_lines(path: Path, fields: frozenset[str]) -> list[Mapping[str, object]]:
    records: list[Mapping[str, object]] = []
    try:
        with path.open("r", encoding="utf-8", errors="strict", newline="") as stream:
            for line in stream:
                if not line.endswith("\n") or not line.strip():
                    raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
                raw = _load_json(line[:-1])
                record = _mapping(raw)
                if set(record) != fields or len(records) >= MAX_LOGICAL_RECORDS:
                    raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
                records.append(record)
    except PortableImportFailure:
        raise
    except (OSError, UnicodeError, PortableExportFailure) as error:
        raise PortableImportFailure("IMPORT_PACKAGE_INVALID") from error
    return records


def _validate_workflows(value: object, project_id: str) -> None:
    payload = _mapping(value)
    if set(payload) != {"schemaVersion", *_WORKFLOW_ARRAYS} or payload["schemaVersion"] != 1:
        raise PortableImportFailure("IMPORT_UNSUPPORTED_VERSION")
    by_workflow: dict[str, Mapping[str, object]] = {}
    records = 0
    for collection in _WORKFLOW_ARRAYS:
        for row in _objects(payload[collection]):
            if set(row) != _WORKFLOW_FIELDS[collection] or row.get("projectId") != project_id:
                raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
            records += 1
            if records > MAX_LOGICAL_RECORDS:
                raise PortableImportFailure("IMPORT_TOO_LARGE", status_code=413)
            if collection == "structuredNoteDrafts":
                _validate_note_draft(row)
            elif collection == "candidateEdits":
                _validate_candidate_edit(row)
            elif collection == "suggestionWorkflows":
                workflow_id = _digest(row["workflowId"])
                for field in ("sourceVersionDigest", "itemHandleDigest", "evidenceDigest"):
                    _digest(row[field])
                for field in ("sourceVersionRevision", "itemRevision"):
                    _bounded_int(row[field], 2**31 - 1, minimum=1)
                _bounded_int(row["proposalRevision"], 2**31 - 1)
                if (
                    workflow_id in by_workflow
                    or row["state"] not in {"failed", "proposed", "edited", "confirmed", "rejected", "abstained"}
                ):
                    raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
                by_workflow[workflow_id] = row
                if row["proposal"] is not None:
                    try:
                        from projecta_api.extraction.local_suggestions import LocalSuggestionProposal

                        proposal = LocalSuggestionProposal.model_validate(row["proposal"])
                    except Exception as error:
                        raise PortableImportFailure("IMPORT_PACKAGE_INVALID") from error
                    if proposal.model_dump(mode="json", by_alias=True, exclude_none=True) != row["proposal"]:
                        raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
                for field, maximum in (("modelId", 128), ("errorCode", 64)):
                    if row[field] is not None:
                        _bounded_string(row[field], maximum)
                if row["latestReceiptDigest"] is not None:
                    _digest(row["latestReceiptDigest"])
                _datetime(_bounded_string(row["createdAt"], _MAX_EXPORT_TIME_LENGTH))
                _datetime(_bounded_string(row["updatedAt"], _MAX_EXPORT_TIME_LENGTH))
            elif collection == "suggestionAttempts":
                for field in ("attemptId", "actorDigest", "workflowId", "idempotencyDigest", "requestDigest"):
                    _digest(row[field])
                if _digest(row["workflowId"]) not in by_workflow or row["state"] not in {"completed", "failed"}:
                    raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
                if row["errorCode"] is not None:
                    _bounded_string(row["errorCode"], 64)
                _datetime(_bounded_string(row["requestedAt"], _MAX_EXPORT_TIME_LENGTH))
            else:
                _validate_cost_event(row)


def _validate_note_draft(row: Mapping[str, object]) -> None:
    try:
        from projecta_api.structured_note import StructuredNoteDraft
        from projecta_api.structured_note_store import _serialize

        draft = StructuredNoteDraft.model_validate(row["draft"])
        serialized = _serialize(draft)
    except Exception as error:
        raise PortableImportFailure("IMPORT_PACKAGE_INVALID") from error
    if draft.model_dump(mode="json", by_alias=True) != row["draft"]:
        raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
    payload_digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    if (
        not _SHA256.fullmatch(_bounded_string(row["payloadDigest"], 64))
        or payload_digest != row["payloadDigest"]
        or not _SHA_DIGEST.fullmatch(_bounded_string(row["idempotencyDigest"], 71))
    ):
        raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
    committed_id = row["committedNoteId"]
    if committed_id is not None:
        _bounded_string(committed_id, 128)
    if (committed_id is not None) != (draft.draft_status == "committed"):
        raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
    _datetime(_bounded_string(row["createdAt"], _MAX_EXPORT_TIME_LENGTH))
    _datetime(_bounded_string(row["updatedAt"], _MAX_EXPORT_TIME_LENGTH))
    _bounded_string(row["sourceHandle"], 128)
    _bounded_string(row["actorId"], 128)
    _bounded_int(row["revision"], 2**31 - 1, minimum=1)


def _validate_candidate_edit(row: Mapping[str, object]) -> None:
    if not re.fullmatch(r"(?:candidate|node)-h-[0-9a-f]{24}", _bounded_string(row["sourceCandidateHandle"], 128)):
        raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
    candidate_id = _bounded_string(row["candidateId"], 512)
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{2,511}", candidate_id):
        if not _is_stable_candidate_identity(candidate_id):
            raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
    try:
        from projecta_api.structured_note import StructuredCandidateEditRequest

        edit = StructuredCandidateEditRequest.model_validate(row["corrections"])
    except Exception as error:
        raise PortableImportFailure("IMPORT_PACKAGE_INVALID") from error
    if edit.model_dump(mode="json", by_alias=True) != row["corrections"]:
        raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
    for key in ("sourceEditHandle", "actorId", "requestId"):
        _bounded_string(row[key], 128)
    _bounded_int(row["revision"], 2**31 - 1, minimum=1)
    _datetime(_bounded_string(row["createdAt"], _MAX_EXPORT_TIME_LENGTH))


def _validate_cost_event(row: Mapping[str, object]) -> None:
    _digest(row["actorDigest"])
    _bounded_string(row["eventId"], 128)
    for key in ("workflowDigest", "attemptDigest", "receiptDigest", "assertionDigest"):
        if row[key] is not None:
            _digest(row[key])
    if row["workflowKind"] not in {"entity", "relation"} or row["eventType"] not in {
        "manual_workflow", "local_request", "local_attempt", "manual_edit", "review", "accepted_assertion"
    }:
        raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
    if row["decision"] not in {None, "confirm", "edit", "reject", "abstain"}:
        raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
    if row["correctionCategory"] not in {None, "unchanged", "minor", "major"}:
        raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
    dimensions = row["correctionDimensions"]
    allowed_dimensions = {"span", "type", "label", "predicate", "endpoint", "evidence"}
    if (
        not isinstance(dimensions, list)
        or any(not isinstance(item, str) or item not in allowed_dimensions for item in dimensions)
        or len(dimensions) != len(set(dimensions))
    ):
        raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
    for key in ("localInferenceUnits", "semanticEditCount"):
        _bounded_int(row[key], 2**63 - 1)
    if row["reviewLatencyMs"] is not None:
        _bounded_int(row["reviewLatencyMs"], 31_536_000_000)
    _datetime(_bounded_string(row["occurredAt"], _MAX_EXPORT_TIME_LENGTH))


def _validate_connectors(value: object, project_id: str, evidence: Sequence[Mapping[str, object]]) -> None:
    payload = _mapping(value)
    if set(payload) != {"schemaVersion", *_CONNECTOR_ARRAYS} or payload["schemaVersion"] != 1:
        raise PortableImportFailure("IMPORT_UNSUPPORTED_VERSION")
    arrays = {field: _objects(payload[field]) for field in _CONNECTOR_ARRAYS}
    allowed_connectors = {
        "json-mock": {"inbound-import", "resource-fetch", "cancellation"},
        "teams": {"inbound-import"},
        "github-public-issues": {"inbound-import"},
    }
    terminal_outcomes = {"accepted", "replayed", "failed", "cancelled", "truncated", "conflict"}
    installations: dict[str, str] = {}
    for row in arrays["installations"]:
        if set(row) != _CONNECTOR_FIELDS["installations"] or row["projectId"] != project_id:
            raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
        connector = _bounded_string(row["connectorType"], 64)
        if connector not in allowed_connectors:
            raise PortableImportFailure("IMPORT_UNSUPPORTED_VERSION")
        capabilities = row["capabilities"]
        if (
            type(row["enabled"]) is not bool
            or not isinstance(capabilities, list)
            or not capabilities
            or any(not isinstance(item, str) or item not in allowed_connectors[connector] for item in capabilities)
            or len(capabilities) != len(set(capabilities))
        ):
            raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
        installation_id = _bounded_string(row["installationId"], 128)
        if installation_id in installations:
            raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
        installations[installation_id] = connector
        _bounded_int(row["revision"], 2**31 - 1, minimum=1)
        _datetime(_bounded_string(row["createdAt"], _MAX_EXPORT_TIME_LENGTH))
        _datetime(_bounded_string(row["updatedAt"], _MAX_EXPORT_TIME_LENGTH))
    evidence_refs = {cast(str, item["evidenceReference"]) for item in evidence}
    event_ids: set[tuple[str, str]] = set()
    for row in arrays["inbox"]:
        if set(row) != _CONNECTOR_FIELDS["inbox"] or row["projectId"] != project_id:
            raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
        installation_id = _bounded_string(row["installationId"], 128)
        if installation_id not in installations:
            raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
        event_id = _bounded_string(row["eventId"], 256)
        event_key = (installation_id, event_id)
        if event_key in event_ids:
            raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
        event_ids.add(event_key)
        if row["contentReference"] not in evidence_refs or not _SHA256.fullmatch(_bounded_string(row["bodyHash"], 64)):
            raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
        _bounded_int(row["conflictCount"], 2**31 - 1)
        if row["acceptedOutcome"] is not None:
            if _bounded_string(row["acceptedOutcome"], 32) not in terminal_outcomes:
                raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
        for key in ("createdAt", "updatedAt"):
            _datetime(_bounded_string(row[key], _MAX_EXPORT_TIME_LENGTH))
        for key in ("acceptedAt", "conflictLastSeenAt"):
            if row[key] is not None:
                _datetime(_bounded_string(row[key], _MAX_EXPORT_TIME_LENGTH))

    runs: dict[str, Mapping[str, object]] = {}
    run_start_times: dict[str, datetime] = {}
    for row in arrays["runs"]:
        if set(row) != _CONNECTOR_FIELDS["runs"] or row["projectId"] != project_id:
            raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
        installation_id = _bounded_string(row["installationId"], 128)
        status = _bounded_string(row["status"], 32)
        terminal_outcome = _bounded_string(row["terminalOutcome"], 32)
        if installation_id not in installations or status not in terminal_outcomes or terminal_outcome != status:
            raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
        run_id = _bounded_string(row["runId"], 128)
        if run_id in runs:
            raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
        if not _SHA_DIGEST.fullmatch(_bounded_string(row["idempotencyDigest"], 71)):
            raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
        for key in ("revision", "eventCount", "replayCount"):
            _bounded_int(row[key], 2**31 - 1)
        started = _datetime(_bounded_string(row["startedAt"], _MAX_EXPORT_TIME_LENGTH))
        terminal = _datetime(_bounded_string(row["terminalAt"], _MAX_EXPORT_TIME_LENGTH))
        if terminal < started:
            raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
        for key in ("createdAt", "updatedAt"):
            _datetime(_bounded_string(row[key], _MAX_EXPORT_TIME_LENGTH))
        for key, maximum in (("failureCode", 128), ("failureDetail", 2048)):
            if row[key] is not None:
                _bounded_string(row[key], maximum)
        if row["retryOfRunId"] is not None:
            _bounded_string(row["retryOfRunId"], 128)
        if row["deadLetterId"] is not None:
            _bounded_int(row["deadLetterId"], 2**63 - 1, minimum=1)
        runs[run_id] = row
        run_start_times[run_id] = started
    for run_id, row in runs.items():
        previous_id = row["retryOfRunId"]
        if previous_id is not None:
            previous = _bounded_string(previous_id, 128)
            if previous not in runs or previous == run_id or run_start_times[previous] >= run_start_times[run_id]:
                raise PortableImportFailure("IMPORT_PACKAGE_INVALID")

    attempts: set[tuple[str, int]] = set()
    for row in arrays["attempts"]:
        if set(row) != _CONNECTOR_FIELDS["attempts"]:
            raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
        run_id = _bounded_string(row["runId"], 128)
        status = _bounded_string(row["status"], 32)
        if run_id not in runs or status not in terminal_outcomes:
            raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
        if row["outcome"] is not None and _bounded_string(row["outcome"], 32) != status:
            raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
        key = (run_id, _bounded_int(row["attemptNumber"], 2**31 - 1, minimum=1))
        if key in attempts:
            raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
        attempts.add(key)
        started = _datetime(_bounded_string(row["startedAt"], _MAX_EXPORT_TIME_LENGTH))
        terminal = _datetime(_bounded_string(row["terminalAt"], _MAX_EXPORT_TIME_LENGTH))
        if terminal < started:
            raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
        for field, maximum in (("failureCode", 128), ("failureDetail", 2048)):
            if row[field] is not None:
                _bounded_string(row[field], maximum)
    cursor_installations: set[str] = set()
    for row in arrays["cursors"]:
        if set(row) != _CONNECTOR_FIELDS["cursors"] or row["projectId"] != project_id:
            raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
        installation_id = _bounded_string(row["installationId"], 128)
        connector = installations.get(installation_id)
        if connector is None or installation_id in cursor_installations:
            raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
        cursor_installations.add(installation_id)
        checkpoint = row["checkpoint"]
        if checkpoint is not None:
            checkpoint = _bounded_string(checkpoint, 2048)
        try:
            _validate_cursor(connector, cast(str | None, checkpoint))
        except PortableExportFailure as error:
            raise PortableImportFailure("IMPORT_UNSUPPORTED_VERSION") from error
        _bounded_int(row["revision"], 2**31 - 1)
        _datetime(_bounded_string(row["updatedAt"], _MAX_EXPORT_TIME_LENGTH))
    dead_ids: set[int] = set()
    for row in arrays["deadLetters"]:
        if set(row) != _CONNECTOR_FIELDS["deadLetters"] or row["projectId"] != project_id:
            raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
        installation_id = _bounded_string(row["installationId"], 128)
        if installation_id not in installations:
            raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
        dead_id = _bounded_int(row["deadLetterId"], 2**63 - 1, minimum=1)
        run_id = row["runId"]
        event_id = row["eventId"]
        if run_id is not None and _bounded_string(run_id, 128) not in runs:
            raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
        if event_id is not None and (installation_id, _bounded_string(event_id, 256)) not in event_ids:
            raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
        if dead_id in dead_ids:
            raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
        dead_ids.add(dead_id)
        _bounded_string(row["failureCode"], 128)
        _bounded_string(row["sanitizedDetail"], 2048)
        _datetime(_bounded_string(row["createdAt"], _MAX_EXPORT_TIME_LENGTH))
        if row["resolvedAt"] is not None:
            _datetime(_bounded_string(row["resolvedAt"], _MAX_EXPORT_TIME_LENGTH))
    for run in runs.values():
        dead_id = run["deadLetterId"]
        if dead_id is not None and _bounded_int(dead_id, 2**63 - 1, minimum=1) not in dead_ids:
            raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
    audit_ids: set[int] = set()
    for row in arrays["auditEvents"]:
        if set(row) != _CONNECTOR_FIELDS["auditEvents"] or row["projectId"] != project_id:
            raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
        installation_id = row["installationId"]
        if installation_id is not None and _bounded_string(installation_id, 128) not in installations:
            raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
        audit_id = _bounded_int(row["auditId"], 2**63 - 1, minimum=1)
        if audit_id in audit_ids:
            raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
        audit_ids.add(audit_id)
        _bounded_string(row["operation"], 64)
        _bounded_string(row["outcome"], 32)
        _digest(row["actorDigest"])
        _datetime(_bounded_string(row["recordedAt"], _MAX_EXPORT_TIME_LENGTH))
        _bounded_string(row["correlationId"], 128)

def _validate_optional_run_reference(value: object, runs: Mapping[str, object], run_id: str) -> None:
    if value is None:
        return
    previous = _bounded_string(value, 128)
    if previous == run_id or previous not in runs:
        raise PortableImportFailure("IMPORT_PACKAGE_INVALID")


def _validate_receipts(receipts: Sequence[Mapping[str, object]], project_id: str) -> None:
    project_digest = _digest_text(project_id)
    histories: dict[tuple[str, str], list[Mapping[str, object]]] = {}
    receipt_ids: set[str] = set()
    receipt_digests: set[str] = set()
    for row in receipts:
        if set(row) != _RECEIPT_FIELDS or row["projectId"] != project_id:
            raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
        try:
            from projecta_api.extraction.review_receipts import ReviewDecisionReceiptRecord

            receipt = ReviewDecisionReceiptRecord.model_validate_json(_canonical_json({
                "contractVersion": REVIEW_RECEIPT_CONTRACT_VERSION,
                "outcome": "accepted",
                "projectDigest": project_digest,
                **{key: value for key, value in row.items() if key not in {"projectId", "requestDigest"}},
            }).decode("utf-8"))
        except Exception as error:
            raise PortableImportFailure("IMPORT_PACKAGE_INVALID") from error
        safe_record = receipt.safe_dict()
        expected_record = {
            "contractVersion": REVIEW_RECEIPT_CONTRACT_VERSION,
            "outcome": "accepted",
            "projectDigest": project_digest,
            **{key: value for key, value in row.items() if key not in {"projectId", "requestDigest", "occurredAt"}},
        }
        safe_record.pop("occurredAt", None)
        expected_record.pop("occurredAt", None)
        if safe_record != expected_record:
            raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
        for key in ("candidateRevision", "sourceVersionRevision", "sequence"):
            _bounded_int(row[key], 2**31 - 1, minimum=1)
        request_digest = _digest(row["requestDigest"])
        occurred = _datetime(_bounded_string(row["occurredAt"], _MAX_EXPORT_TIME_LENGTH))
        receipt_digest = _digest(row["receiptDigest"])
        receipt_id = _bounded_string(row["receiptId"], 128)
        if (
            receipt_id != "rr1_" + request_digest.removeprefix("sha256:")
            or _receipt_digest(request_digest, occurred) != receipt_digest
        ):
            raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
        key = (cast(str, row["itemKind"]), cast(str, row["itemHandleDigest"]))
        histories.setdefault(key, []).append(row)
        if receipt_id in receipt_ids or receipt_digest in receipt_digests:
            raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
        receipt_ids.add(receipt_id)
        receipt_digests.add(receipt_digest)
    for history in histories.values():
        history.sort(key=lambda item: cast(int, item["sequence"]))
        previous: str | None = None
        for index, row in enumerate(history, start=1):
            if row["sequence"] != index or row["previousDecisionDigest"] != previous:
                raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
            previous = cast(str, row["receiptDigest"])


def _validate_corrections(
    corrections: Sequence[Mapping[str, object]],
    project_id: str,
    receipts: Sequence[Mapping[str, object]],
) -> None:
    project_digest = _digest_text(project_id)
    receipt_digests = {row["receiptDigest"] for row in receipts}
    ids: set[str] = set()
    for row in corrections:
        if set(row) != _CORRECTION_FIELDS or row["projectId"] != project_id:
            raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
        try:
            from projecta_api.extraction.correction_burden import CorrectionBurdenEventRecord

            correction = CorrectionBurdenEventRecord.model_validate_json(_canonical_json({
                "contractVersion": CORRECTION_BURDEN_CONTRACT_VERSION,
                "outcome": "accepted",
                "projectDigest": project_digest,
                **{key: value for key, value in row.items() if key not in {"projectId", "requestDigest"}},
            }).decode("utf-8"))
        except Exception as error:
            raise PortableImportFailure("IMPORT_PACKAGE_INVALID") from error
        safe_record = correction.safe_dict()
        expected_record = {
            "contractVersion": CORRECTION_BURDEN_CONTRACT_VERSION,
            "outcome": "accepted",
            "projectDigest": project_digest,
            **{key: value for key, value in row.items() if key not in {"projectId", "requestDigest", "occurredAt"}},
        }
        safe_record.pop("occurredAt", None)
        expected_record.pop("occurredAt", None)
        if safe_record != expected_record:
            raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
        request_digest = _digest(row["requestDigest"])
        occurred = _datetime(_bounded_string(row["occurredAt"], _MAX_EXPORT_TIME_LENGTH))
        event_digest = _digest(row["eventDigest"])
        event_id = _bounded_string(row["eventId"], 128)
        if (
            row["reviewReceiptDigest"] not in receipt_digests
            or event_id != "cbe1_" + request_digest.removeprefix("sha256:")
            or _event_digest(request_digest, occurred) != event_digest
            or event_id in ids
        ):
            raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
        ids.add(event_id)


def _validate_archive_references(
    workflows: object, receipts: Sequence[Mapping[str, object]]
) -> None:
    receipt_digests = {row["receiptDigest"] for row in receipts}
    payload = _mapping(workflows)
    for workflow in _objects(payload["suggestionWorkflows"]):
        latest_receipt = workflow["latestReceiptDigest"]
        if latest_receipt is not None and latest_receipt not in receipt_digests:
            raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
    for event in _objects(payload["authoringCostEvents"]):
        receipt_digest = event["receiptDigest"]
        if receipt_digest is not None and receipt_digest not in receipt_digests:
            raise PortableImportFailure("IMPORT_PACKAGE_INVALID")

def _check_no_secret_fields(*values: object) -> None:
    forbidden = frozenset(
        {
            "secretreference", "secretreferencedigest", "secret", "token", "password",
            "ciphertext", "credential", "credentials", "session", "sessiontoken", "masterkey",
            "oauthtoken", "providertoken", "setuphandle", "accesstoken", "refreshtoken",
            "clientsecret", "apikey", "privatekey", "secretkey", "authtoken", "bearertoken",
            "authorization",
        }
    )

    def walk(value: object) -> None:
        if isinstance(value, Mapping):
            if any(
                isinstance(key, str)
                and key.replace("_", "").replace("-", "").casefold() in forbidden
                for key in value
            ):
                raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    for value in values:
        walk(value)


def _append_project(
    registry: Mapping[str, object], project_id: str, project_name: str, adopt_placeholder: bool
) -> dict[str, object]:
    current = _registry_projects(registry)
    if project_id in current:
        if not adopt_placeholder or project_id != "my-projecta-workspace":
            return dict(registry)
        values = [
            {"projectId": item["projectId"], "projectName": project_name if item["projectId"] == project_id else item["projectName"]}
            for item in _registry_entries(registry)
        ]
        result = dict(registry)
        result["projectName"] = project_name
        result["projects"] = values
        return result
    result = dict(registry)
    projects = _registry_entries(registry)
    projects.append({"projectId": project_id, "projectName": project_name})
    result["projects"] = projects
    return result


def _registry_entries(registry: Mapping[str, object]) -> list[dict[str, str]]:
    raw = registry.get("projects")
    if raw is None:
        return [{"projectId": cast(str, registry["projectId"]), "projectName": cast(str, registry["projectName"])}]
    if not isinstance(raw, list):
        raise PortableImportFailure("IMPORT_DESTINATION_INVALID", status_code=503)
    result: list[dict[str, str]] = []
    for value in raw:
        item = _mapping(value)
        if set(item) != {"projectId", "projectName"}:
            raise PortableImportFailure("IMPORT_DESTINATION_INVALID", status_code=503)
        result.append({"projectId": _bounded_string(item["projectId"], 63), "projectName": _bounded_string(item["projectName"], 128)})
    if len(result) > 100:
        raise PortableImportFailure("IMPORT_DESTINATION_INVALID", status_code=503)
    return result


def _registry_projects(registry: Mapping[str, object]) -> set[str]:
    return {item["projectId"] for item in _registry_entries(registry)}


def _registry_name(registry: Mapping[str, object], project_id: str) -> str:
    return next((item["projectName"] for item in _registry_entries(registry) if item["projectId"] == project_id), "")


def _is_placeholder_registry(registry: Mapping[str, object], project_id: str, local_name: str) -> bool:
    return project_id == "my-projecta-workspace" and local_name == registry.get("projectName") and bool(local_name)


def _read_registry(path: Path | None) -> Mapping[str, object]:
    if path is None:
        raise PortableImportFailure("IMPORT_UNSUPPORTED_RUNTIME", status_code=503)
    value = _read_private_json(path, "IMPORT_DESTINATION_INVALID")
    if (
        value.get("formatVersion") != 1
        or not isinstance(value.get("projectId"), str)
        or not isinstance(value.get("projectName"), str)
        or not isinstance(value.get("actorId"), str)
    ):
        raise PortableImportFailure("IMPORT_DESTINATION_INVALID", status_code=503)
    entries = _registry_entries(value)
    if not entries or entries[0]["projectId"] != value["projectId"]:
        raise PortableImportFailure("IMPORT_DESTINATION_INVALID", status_code=503)
    if len({item["projectId"] for item in entries}) != len(entries):
        raise PortableImportFailure("IMPORT_DESTINATION_INVALID", status_code=503)
    return value


def _read_private_json(path: Path, code: str = "IMPORT_RECOVERY_REQUIRED", *, status_code: int = 503) -> dict[str, object]:
    try:
        if path.is_symlink() or not path.is_file():
            raise OSError("not a regular file")
        value = _load_json(path.read_text(encoding="utf-8", errors="strict"))
        return dict(_mapping(value))
    except PortableImportFailure:
        raise
    except (OSError, UnicodeError, PortableExportFailure) as error:
        raise PortableImportFailure(code, status_code=status_code) from error


def _write_private_json(path: Path, value: object) -> None:
    _ensure_private_directory(path.parent)
    if path.is_symlink():
        raise PortableImportFailure("IMPORT_DESTINATION_INVALID", status_code=503)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.partial")
    try:
        with temporary.open("xb") as output:
            output.write(_canonical_json(value) + b"\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    except OSError as error:
        temporary.unlink(missing_ok=True)
        raise PortableImportFailure("IMPORT_FAILED", status_code=503) from error


def _ensure_private_directory(path: Path) -> None:
    try:
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
        if path.is_symlink() or not path.is_dir():
            raise OSError("unsafe directory")
        if os.name != "nt":
            os.chmod(path, 0o700)
    except OSError as error:
        raise PortableImportFailure("IMPORT_DESTINATION_INVALID", status_code=503) from error


def _safe_member(path: str) -> bool:
    if not path or "\\" in path or path.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", path):
        return False
    parts = path.split("/")
    return all(part not in {"", ".", ".."} for part in parts)


def _mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
    return cast(Mapping[str, object], value)


def _objects(value: object) -> list[Mapping[str, object]]:
    if not isinstance(value, list):
        raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
    return [_mapping(item) for item in value]


def _digest(value: object) -> str:
    text_value = _bounded_string(value, 71)
    if not _SHA_DIGEST.fullmatch(text_value):
        raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
    return text_value

def _is_stable_candidate_identity(value: str) -> bool:
    """Accept the exporter stable candidate IRIs that preserve semantic continuity."""
    if len(value) > 512 or "\\" in value or "\x00" in value:
        return False
    pattern = r"https://w3id\.org/projecta/data/project/[a-z0-9][a-z0-9-]{0,62}/(?:candidate|note|entity|relation|item|source)/[A-Za-z0-9][A-Za-z0-9._~:/?#@!$&'()*+,;=\-\[\]]{0,400}"
    return re.fullmatch(pattern, value) is not None


def _raw_digest(value: object) -> str:
    return _digest(value).removeprefix("sha256:")


def _portable_marker(kind: str, digest: str) -> str:
    if kind not in {"key", "actor"} or not _SHA_DIGEST.fullmatch(digest):
        raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
    return f"projecta-portable-{kind}.v1|{digest}|{uuid.uuid4().hex}"




def _bounded_string(value: object, maximum: int) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum or "\x00" in value:
        raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
    return value


def _bounded_int(value: object, maximum: int, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum or value > maximum:
        raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
    return value


def _datetime(value: str) -> datetime:
    if not value.endswith("Z"):
        raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
    try:
        result = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise PortableImportFailure("IMPORT_PACKAGE_INVALID") from error
    if result.tzinfo is None or result.utcoffset() is None:
        raise PortableImportFailure("IMPORT_PACKAGE_INVALID")
    return result.astimezone(UTC)


def _nullable_datetime(value: object) -> datetime | None:
    return None if value is None else _datetime(_bounded_string(value, _MAX_EXPORT_TIME_LENGTH))


def _digest_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _hash_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    observed = 0
    try:
        with path.open("rb") as source:
            while True:
                chunk = source.read(_MAX_UPLOAD_CHUNK)
                if not chunk:
                    break
                observed += len(chunk)
                digest.update(chunk)
    except OSError as error:
        raise PortableImportFailure("IMPORT_PACKAGE_INVALID") from error
    return digest.hexdigest(), observed


def _valid_token(value: object) -> str:
    token = _bounded_string(value, 36)
    try:
        parsed = uuid.UUID(token)
    except ValueError as error:
        raise PortableImportFailure("IMPORT_NOT_FOUND", status_code=404) from error
    if str(parsed) != token or parsed.version != 4:
        raise PortableImportFailure("IMPORT_NOT_FOUND", status_code=404)
    return token


def _postgres_record_count(package: _ValidatedPackage) -> int:
    return sum(len(_objects(_mapping(package.connectors)[field])) for field in _CONNECTOR_ARRAYS) + len(package.receipts) + len(package.corrections)


def _postgres_project_count(engine: Engine, project_id: str) -> int:
    tables = (
        "connector_installations", "connector_event_inbox", "connector_sync_runs", "connector_cursors",
        "connector_dead_letters", "connector_audit_records", "review_decision_receipts", "correction_burden_events",
    )
    with engine.connect() as connection:
        count = sum(
            int(connection.execute(text(f"SELECT count(*) FROM {table} WHERE project_id=:id"), {"id": project_id}).scalar_one())
            for table in tables
        )
        count += int(
            connection.execute(
                text(
                    "SELECT count(*) FROM connector_sync_attempts a "
                    "JOIN connector_sync_runs r ON r.run_id=a.run_id WHERE r.project_id=:id"
                ),
                {"id": project_id},
            ).scalar_one()
        )
        return count


def _has_committed_postgres_rows(engine: Engine | None, project_id: str, expected: object) -> bool:
    if engine is None:
        return False
    count = _bounded_int(expected, MAX_LOGICAL_RECORDS)
    actual = _postgres_project_count(engine, project_id)
    if actual == 0:
        return False
    if actual != count:
        raise PortableImportFailure("IMPORT_RECOVERY_REQUIRED", status_code=503)
    return True

def _import_is_committed(
    engine: Engine | None,
    project_id: str,
    expected: object,
    phase: str,
) -> bool:
    count = _bounded_int(expected, MAX_LOGICAL_RECORDS)
    if _has_committed_postgres_rows(engine, project_id, count):
        return True
    if phase in {"postgres-committed", "ledger-written", "publishing", "catalog-published"}:
        if count == 0:
            return True
        raise PortableImportFailure("IMPORT_RECOVERY_REQUIRED", status_code=503)
    return False
