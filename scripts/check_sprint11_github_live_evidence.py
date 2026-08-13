#!/usr/bin/env python3
"""Validate executable, provenance-bearing GitHub Public Issues evidence."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "docs/sprint-plans/sprint-11/artifacts/s11-A18-github-live-acceptance.json"
JOURNEY = ROOT / "docs/sprint-plans/sprint-11/artifacts/s11-A18-github-live-journey.json"
G2_PACKET = ROOT / "docs/sprint-plans/sprint-11/g2-review-packet.md"
PRODUCERS = {
    "scripts/run_sprint11_github_public_issues_acceptance.ps1",
    "scripts/run_sprint11_github_public_issues_edit_journey.ps1",
}


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{path.name} must contain one JSON object")
    return value


def _journey_waiver_applies(record: dict[str, Any]) -> bool:
    """Accept only the exact failed diagnostic explicitly approved at G2."""
    try:
        packet = G2_PACKET.read_text(encoding="utf-8")
        accepted = _read(ARTIFACT)
        journey_hash = hashlib.sha256(JOURNEY.read_bytes()).hexdigest()
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return False
    return (
        "G2 product/security/release approval: `APPROVED_WITH_RESIDUAL_RISK`" in packet
        and "live edit/replay is explicitly waived" in packet
        and journey_hash in packet
        and record.get("schemaVersion") == "sprint11.github-public-issues-live-journey.v2"
        and record.get("status") == "failed"
        and record.get("generatedBy") == "scripts/run_sprint11_github_public_issues_edit_journey.ps1"
        and isinstance(record.get("failure"), str)
        and bool(record.get("failure"))
        and record.get("credentialsPersisted") is False
        and record.get("rawProviderPayload") is False
        and record.get("projectHandlePersisted") is False
        and _timestamp_order(record.get("startedAt"), record.get("finishedAt"))
        and record.get("repositoryHash") == accepted.get("repositoryHash")
        and record.get("baselineRun") == accepted.get("baselineRun")
        and record.get("providerSnapshot") == accepted.get("providerSnapshot")
    )


def _timestamp(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _timestamp_order(*values: object) -> bool:
    if not all(_timestamp(value) for value in values):
        return False
    parsed = [datetime.fromisoformat(str(value).replace("Z", "+00:00")) for value in values]
    return all(left <= right for left, right in pairwise(parsed))


def _digest(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def _cursor_digest(value: object) -> bool:
    return isinstance(value, str) and value.startswith("sha256:") and _digest(value[7:])


def _contains_asserted_boolean(value: object) -> bool:
    if isinstance(value, dict):
        return any(key == "verified" or _contains_asserted_boolean(item) for key, item in value.items())
    if isinstance(value, list):
        return any(_contains_asserted_boolean(item) for item in value)
    return False


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _run_provenance_digest(run: dict[str, Any]) -> str:
    before = "" if run.get("cursorBeforeDigest") is None else str(run.get("cursorBeforeDigest"))
    after = "" if run.get("cursorAfterDigest") is None else str(run.get("cursorAfterDigest"))
    started_at = _canonical_timestamp(run.get("startedAt"))
    terminal_at = _canonical_timestamp(run.get("terminalAt"))
    return _sha256(
        f"{run.get('state')}|{run.get('eventCount')}|{run.get('runDigest')}|"
        f"{before}|{after}|{started_at}|{terminal_at}"
    )


def _canonical_timestamp(value: object) -> str:
    if not isinstance(value, str):
        return ""
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return ""
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    # PowerShell's REST JSON conversion exposes the API timestamps at second
    # precision to the producer; bind the same normalized precision here while
    # retaining the full timestamp separately for ordering checks.
    return parsed.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.000000Z")


def _snapshot_digest(snapshot: dict[str, Any]) -> str:
    return _sha256(
        f"{snapshot.get('recordDigest')}|{snapshot.get('issueCount')}|{snapshot.get('commentCount')}|"
        f"{snapshot.get('providerCommentCount')}|{snapshot.get('pullRequestCount')}|"
        f"{snapshot.get('excludedPullRequestCommentCount')}"
    )


def _validate_snapshot(snapshot: object, label: str, errors: list[str]) -> None:
    if not isinstance(snapshot, dict):
        errors.append(f"{label} is missing")
        return
    counts = (
        snapshot.get("issueCount"),
        snapshot.get("commentCount"),
        snapshot.get("providerCommentCount"),
        snapshot.get("excludedPullRequestCommentCount"),
        snapshot.get("pullRequestCount"),
        snapshot.get("expectedEventCount"),
        snapshot.get("recordCount"),
    )
    if not all(isinstance(value, int) and value >= 0 for value in counts):
        errors.append(f"{label} counts are invalid")
    elif snapshot["expectedEventCount"] != snapshot["issueCount"] + snapshot["commentCount"]:
        errors.append(f"{label} expected event count is inconsistent")
    if snapshot.get("recordCount") != snapshot.get("expectedEventCount"):
        errors.append(f"{label} record count does not cover the imported resource set")
    if not _timestamp(snapshot.get("observedAt")):
        errors.append(f"{label} timestamp is invalid")
    for key in ("recordDigest", "snapshotDigest"):
        if not _digest(snapshot.get(key)):
            errors.append(f"{label} {key} is not a SHA-256 digest")
    if _digest(snapshot.get("recordDigest")) and _digest(snapshot.get("snapshotDigest")) and snapshot["snapshotDigest"] != _snapshot_digest(snapshot):
        errors.append(f"{label} snapshot digest does not bind its record digest and cardinality")


def _validate_run(run: object, label: str, errors: list[str], *, state: str | None = None) -> dict[str, Any] | None:
    if not isinstance(run, dict):
        errors.append(f"{label} is missing")
        return None
    if state is not None and run.get("state") != state:
        errors.append(f"{label} state is not {state}")
    if not isinstance(run.get("eventCount"), int) or run.get("eventCount", 0) < 0:
        errors.append(f"{label} event count is invalid")
    if not _digest(run.get("runDigest")):
        errors.append(f"{label} run digest is not a SHA-256 digest")
    for key in ("cursorBeforeDigest", "cursorAfterDigest"):
        value = run.get(key)
        if value is not None and not _cursor_digest(value):
            errors.append(f"{label} {key} is malformed")
    if not _timestamp_order(run.get("startedAt"), run.get("terminalAt")):
        errors.append(f"{label} timestamps are invalid or out of order")
    if not _digest(run.get("provenanceDigest")):
        errors.append(f"{label} provenance digest is missing")
    elif run.get("provenanceDigest") != _run_provenance_digest(run):
        errors.append(f"{label} provenance digest does not bind run state/count/cursors/timestamps")
    return run


def _validate_replay(replay: object, target: dict[str, Any] | None, label: str, errors: list[str]) -> None:
    run = _validate_run(replay, label, errors, state="replayed")
    if run is None or target is None:
        return
    for replay_key, target_key in (
        ("replayOfRunDigest", "runDigest"),
        ("replayOfEventCount", "eventCount"),
        ("replayOfCursorBeforeDigest", "cursorBeforeDigest"),
        ("replayOfCursorAfterDigest", "cursorAfterDigest"),
    ):
        if run.get(replay_key) != target.get(target_key):
            errors.append(f"{label} does not identify the exact target run for {replay_key}")
    if run.get("eventCount") != target.get("eventCount"):
        errors.append(f"{label} eventCount does not match the run it replays")
    if run.get("cursorAfterDigest") != target.get("cursorAfterDigest"):
        errors.append(f"{label} cursorAfterDigest does not match the run it replays")


def _validate_continuity(continuity: object, snapshot: dict[str, Any] | None, errors: list[str]) -> None:
    if not isinstance(continuity, dict):
        errors.append("candidate/evidence continuity is missing")
        return
    expected = snapshot.get("expectedEventCount") if snapshot else None
    required_ints = (
        "preRunCandidateCount", "postRunCandidateCount", "candidateDeltaCount", "candidateRemovedCount",
        "preRunCandidateGraphCount", "postRunCandidateGraphCount", "candidateGraphDeltaCount", "candidateGraphRemovedCount",
        "preRunEvidenceNodeCount", "postRunEvidenceNodeCount", "evidenceNodeDeltaCount", "evidenceNodeRemovedCount",
        "runEventCount",
    )
    if not all(isinstance(continuity.get(key), int) and continuity.get(key) >= 0 for key in required_ints):
        errors.append("candidate/evidence continuity counts are invalid")
        return
    if isinstance(expected, int):
        if continuity["candidateDeltaCount"] != expected or continuity["candidateGraphDeltaCount"] != expected:
            errors.append("candidate continuity delta is not exactly the imported event count")
        if continuity["evidenceNodeDeltaCount"] < expected:
            errors.append("evidence continuity delta does not cover the imported event count")
        if continuity["runEventCount"] != expected:
            errors.append("continuity is not bound to the baseline run event count")
    if continuity["postRunCandidateCount"] - continuity["preRunCandidateCount"] != continuity["candidateDeltaCount"]:
        errors.append("candidate continuity delta does not match before/after counts")
    if continuity["postRunCandidateGraphCount"] - continuity["preRunCandidateGraphCount"] != continuity["candidateGraphDeltaCount"]:
        errors.append("candidate graph continuity delta does not match before/after counts")
    if continuity["postRunEvidenceNodeCount"] - continuity["preRunEvidenceNodeCount"] != continuity["evidenceNodeDeltaCount"]:
        errors.append("evidence continuity delta does not match before/after counts")
    for key in (
        "preRunCandidateSetDigest", "postRunCandidateSetDigest", "candidateDeltaDigest",
        "preRunCandidateGraphSetDigest", "postRunCandidateGraphSetDigest", "candidateGraphDeltaDigest",
        "preRunEvidenceSetDigest", "postRunEvidenceSetDigest", "evidenceDeltaDigest",
        "preRunSourceRevisionDigest", "postRunSourceRevisionDigest",
    ):
        if not _digest(continuity.get(key)):
            errors.append(f"continuity {key} is not a SHA-256 digest")


def _validate(record: dict[str, Any], *, journey: bool) -> list[str]:
    errors: list[str] = []
    expected_schema = "sprint11.github-public-issues-live-journey.v2" if journey else "sprint11.github-public-issues-live.v2"
    if record.get("schemaVersion") != expected_schema:
        errors.append("schema version is not the executable v2 contract")
    if record.get("status") != "passed":
        errors.append("status is not passed")
    if record.get("generatedBy") not in PRODUCERS:
        errors.append("producer is not the checked-in acceptance runner")
    if not any((ROOT / producer).is_file() for producer in PRODUCERS):
        errors.append("producer script is missing")
    for key in ("credentialsPersisted", "rawProviderPayload", "projectHandlePersisted"):
        if record.get(key) is not False:
            errors.append(f"{key} is not false")
    if not _digest(record.get("repositoryHash")):
        errors.append("repository hash is not a SHA-256 digest")
    if _contains_asserted_boolean(record):
        errors.append("artifact contains hand-asserted verified boolean")
    if not _timestamp_order(record.get("startedAt"), record.get("finishedAt")):
        errors.append("artifact timestamps are invalid or out of order")

    snapshot = record.get("providerSnapshot")
    _validate_snapshot(snapshot, "provider snapshot", errors)
    if isinstance(snapshot, dict) and (snapshot.get("pullRequestCount", 0) < 1 or snapshot.get("expectedEventCount", 0) < 1):
        errors.append("provider snapshot does not prove a non-empty PR exclusion journey")

    baseline = _validate_run(record.get("baselineRun"), "baseline run", errors, state="succeeded")
    if baseline is not None and isinstance(snapshot, dict):
        if baseline.get("eventCount") != snapshot.get("expectedEventCount") or baseline.get("eventCount", 0) <= 0:
            errors.append("baseline run did not prove a positive exact import")
        if not _cursor_digest(baseline.get("cursorAfterDigest")):
            errors.append("baseline run did not commit a cursor digest")
        if not _timestamp_order(snapshot.get("observedAt"), baseline.get("startedAt"), baseline.get("terminalAt"), record.get("finishedAt")):
            errors.append("baseline snapshot/run/artifact timestamp order is invalid")

    if not journey:
        _validate_replay(record.get("replayRun"), baseline, "exact replay", errors)

    _validate_continuity(record.get("continuity"), snapshot if isinstance(snapshot, dict) else None, errors)

    exclusion = record.get("pullRequestExclusion")
    if not isinstance(exclusion, dict) or exclusion.get("providerPullRequestCount", 0) < 1 or exclusion.get("importedEventCount") != (snapshot or {}).get("expectedEventCount"):
        errors.append("PR exclusion provenance is incomplete")
    isolation = record.get("projectIsolation")
    if not isinstance(isolation, dict) or isolation.get("forgedProjectStatus") != 404:
        errors.append("project isolation provenance is incomplete")
    if not _digest(record.get("installationDigest")):
        errors.append("installation digest is missing")

    if journey and record.get("generatedBy") == "scripts/run_sprint11_github_public_issues_edit_journey.ps1":
        edit = record.get("editLifecycle")
        before = _validate_run(record.get("beforeEditRun"), "pre-edit run", errors, state="succeeded")
        after = _validate_run(record.get("afterEditRun"), "post-edit run", errors, state="succeeded")
        before_snapshot = record.get("beforeEditSnapshot")
        after_snapshot = record.get("afterEditSnapshot")
        _validate_snapshot(before_snapshot, "before-edit snapshot", errors)
        _validate_snapshot(after_snapshot, "after-edit snapshot", errors)
        if not isinstance(edit, dict) or edit.get("verifiedByRun") is not True:
            errors.append("edit lifecycle is not verified by the producer run")
        if before is not None and baseline is not None and before.get("cursorBeforeDigest") != baseline.get("cursorAfterDigest"):
            errors.append("pre-edit cursor does not continue the baseline cursor")
        if after is not None and before is not None and after.get("cursorBeforeDigest") != before.get("cursorAfterDigest"):
            errors.append("post-edit cursor does not continue the pre-edit cursor")
        if before is not None and after is not None and (before.get("eventCount") != 2 or after.get("eventCount") != 2):
            errors.append("edit runs do not each contain exactly two observations")
        if isinstance(before_snapshot, dict) and isinstance(after_snapshot, dict):
            if before_snapshot.get("expectedEventCount") != after_snapshot.get("expectedEventCount"):
                errors.append("edit lifecycle changed provider cardinality unexpectedly")
            if isinstance(snapshot, dict) and before_snapshot.get("expectedEventCount") != snapshot.get("expectedEventCount", 0) + 2:
                errors.append("edit lifecycle snapshot does not prove exactly two newly created observations")
            if before_snapshot.get("recordDigest") == after_snapshot.get("recordDigest") or before_snapshot.get("snapshotDigest") == after_snapshot.get("snapshotDigest"):
                errors.append("edit lifecycle snapshots do not prove a content/revision change")
        replay = _validate_run(record.get("replayRun"), "post-edit exact replay", errors, state="replayed")
        if replay is not None and after is not None:
            _validate_replay(replay, after, "post-edit exact replay", errors)
        if not _timestamp_order(
            record.get("baselineFinishedAt"),
            before_snapshot.get("observedAt") if isinstance(before_snapshot, dict) else None,
            before.get("startedAt") if before else None,
            before.get("terminalAt") if before else None,
            after_snapshot.get("observedAt") if isinstance(after_snapshot, dict) else None,
            after.get("startedAt") if after else None,
            after.get("terminalAt") if after else None,
            record.get("finishedAt"),
        ):
            errors.append("baseline/edit snapshot/run timestamps are invalid or out of order")
    return errors


def main() -> int:
    checks: dict[str, bool] = {}
    errors: list[str] = []
    for label, path, journey in (("runner evidence", ARTIFACT, False), ("journey evidence", JOURNEY, True)):
        try:
            record = _read(path)
            errors_for_record = _validate(record, journey=journey)
            if journey and errors_for_record and _journey_waiver_applies(record):
                label = "journey evidence (G2 residual-risk waiver)"
                errors_for_record = []
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as error:
            errors_for_record = [str(error)]
        checks[label] = not errors_for_record
        errors.extend(f"{label}: {error}" for error in errors_for_record)
    for label, passed in checks.items():
        print(f"{'PASS' if passed else 'FAIL'} {label}")
    for error in errors:
        print(f"FAIL {error}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
