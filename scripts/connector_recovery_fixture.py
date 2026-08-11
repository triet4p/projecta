"""Seed and verify a disposable PostgreSQL/evidence recovery fixture."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from collections.abc import AsyncIterator
from pathlib import Path

from projecta_api.config import Settings
from projecta_api.evidence.local import LocalEvidenceStore
from projecta_api.evidence.ports import (
    EvidenceGetRequest,
    EvidenceHeadRequest,
    EvidencePutRequest,
)
from projecta_api.operational.database import ConnectorDatabase
from projecta_api.operational.repository import PostgresConnectorRepository

PROJECT = "recovery-project"
INSTALLATION = "install-recovery"
RUN = "run-recovery"
EVENT = "event-recovery"
CONTENT = b'{"event":"recovery","value":42}\n'
BODY_HASH = hashlib.sha256(CONTENT).hexdigest()


async def _content() -> AsyncIterator[bytes]:
    yield CONTENT


async def seed() -> dict[str, object]:
    repository = PostgresConnectorRepository(ConnectorDatabase(Settings()))
    store = LocalEvidenceStore(Path(os.environ["PROJECTA_EVIDENCE_ROOT"]))
    receipt = await store.put(
        EvidencePutRequest(
            project_scope=PROJECT,
            content_type="application/json",
            declared_size=len(CONTENT),
            declared_sha256=hashlib.sha256(CONTENT).hexdigest(),
            source_reference="connector://recovery/event-recovery",
        ),
        _content(),
    )
    installation = repository.upsert_installation(
        project_id=PROJECT,
        installation_id=INSTALLATION,
        connector_type="json-mock",
        capability_snapshot={
            "capabilities": ["inbound-import"],
            "fixtureReference": "fixture://recovery",
        },
        secret_reference=None,
        enabled=True,
        expected_revision=None,
    )
    repository.start_run(
        project_id=PROJECT,
        installation_id=INSTALLATION,
        run_id=RUN,
        idempotency_key="recovery-operation-001",
    )
    run = repository.finish_run(
        project_id=PROJECT,
        installation_id=INSTALLATION,
        run_id=RUN,
        outcome="accepted",
        event_count=1,
    )
    claim = repository.claim_event(
        project_id=PROJECT,
        installation_id=INSTALLATION,
        event_id=EVENT,
        body_hash=BODY_HASH,
        content_reference=receipt.evidence_reference,
    )
    cursor = repository.complete_event(
        project_id=PROJECT,
        installation_id=INSTALLATION,
        event_id=EVENT,
        body_hash=BODY_HASH,
        outcome="accepted",
        checkpoint="cursor-1",
        expected_cursor_revision=0,
    )
    return {
        "installationRevision": installation.revision,
        "runOutcome": run.terminal_outcome,
        "claimOutcome": claim.outcome,
        "cursorRevision": cursor.revision if cursor else None,
        "cursorCheckpoint": cursor.checkpoint if cursor else None,
        "evidenceReference": receipt.evidence_reference,
    }


async def verify() -> dict[str, object]:
    repository = PostgresConnectorRepository(ConnectorDatabase(Settings()))
    evidence_root = Path(os.environ["PROJECTA_EVIDENCE_ROOT"])
    reference_paths = list((evidence_root / "references" / PROJECT).glob("ev_*.json"))
    if len(reference_paths) != 1:
        raise AssertionError("restored evidence reference index is incomplete")
    evidence_reference = reference_paths[0].stem
    installation = repository.get_installation(PROJECT, INSTALLATION)
    cursor = repository.get_cursor(PROJECT, INSTALLATION)
    run = repository.get_run(PROJECT, INSTALLATION, RUN)
    runs = repository.list_runs(PROJECT, INSTALLATION)
    replay = repository.claim_event(
        project_id=PROJECT,
        installation_id=INSTALLATION,
        event_id=EVENT,
        body_hash=BODY_HASH,
        content_reference=evidence_reference,
    )
    if installation is None or cursor is None or run is None:
        raise AssertionError("restored operational rows are incomplete")
    if cursor.checkpoint != "cursor-1" or cursor.revision != 1:
        raise AssertionError("restored cursor is not the accepted checkpoint")
    if run.terminal_outcome != "accepted" or len(runs) != 1:
        raise AssertionError("restored run state is not terminal and unique")
    if replay.outcome != "replayed":
        raise AssertionError(f"restored replay was not idempotent: {replay.outcome}")
    if replay.content_reference != evidence_reference:
        raise AssertionError("restored inbox does not reference restored evidence")
    store = LocalEvidenceStore(evidence_root)
    metadata = await store.head(EvidenceHeadRequest(PROJECT, evidence_reference))
    _, stream = await store.get(
        EvidenceGetRequest(PROJECT, evidence_reference), max_bytes=1024
    )
    restored = b"".join([chunk async for chunk in stream])
    if restored != CONTENT:
        raise AssertionError("restored evidence content differs")
    return {
        "installationRevision": installation.revision,
        "runRows": len(runs),
        "runOutcome": run.terminal_outcome,
        "replayOutcome": replay.outcome,
        "cursorRevision": cursor.revision,
        "cursorCheckpoint": cursor.checkpoint,
        "evidenceReference": metadata.evidence_reference,
        "evidenceSha256": metadata.sha256,
        "evidenceBytes": len(restored),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("seed", "verify"))
    args = parser.parse_args()
    result = asyncio.run(seed() if args.command == "seed" else verify())
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
