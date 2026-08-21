"""Deterministic, sanitized diagnostics for the closed S12-f-12 run.

RM-28 is deliberately report-only.  This module never calls a provider, reads
held-out data, or attempts to reconstruct a provider payload.  It computes the
small set of findings that remain provable from the immutable report and marks
the missing validation detail as unknown.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "evaluation/sprint-12/optimization/s12-f-12-stage-a-report.v6.json"
REPORT_DIGEST = (
    "sha256:419ac3c7aa7fad06287b231432d1ae167990ece45ca11ef94882fb6139569233"
)


def digest(path: Path) -> str:
    """Return a canonical SHA-256 digest for an immutable artifact."""

    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def load_report(path: Path = REPORT) -> dict[str, Any]:
    """Load the closed report and refuse a changed historical input."""

    if digest(path) != REPORT_DIGEST:
        raise ValueError("RM-28 refuses a changed or replaced immutable report")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError("the Stage A report must be a JSON object")
    return value


def _schema_failures(
    records: list[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], Counter[str]]:
    failures: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    for record in records:
        case_id = str(record["caseId"])
        run_id = int(record["runId"])
        for arm in ("predicted-entities", "gold-entities", "gold-relations"):
            arm_record = record["arms"][arm]
            for stage in ("stage1", "stage2"):
                stage_record = arm_record[stage]
                if stage_record["responseReceived"] and not stage_record["schemaValid"]:
                    key = f"{arm}:{stage}"
                    counts[key] += 1
                    failures.append(
                        {
                            "caseId": case_id,
                            "runId": run_id,
                            "arm": arm,
                            "stage": stage,
                            "failureClass": stage_record["failureClass"],
                            "responseDigest": stage_record["responseDigest"],
                            "rawValidationPath": "unknown_sanitized_report",
                        }
                    )
    return failures, counts


def _evidence_findings(records: list[Mapping[str, Any]]) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    bucket_counts: Counter[str] = Counter()
    semantic_counts: Counter[str] = Counter()
    endpoint_counts: Counter[str] = Counter()
    for record in records:
        arm = record["arms"]["gold-entities"]
        count = int(arm["invalidEvidenceCount"])
        if not count:
            continue
        evidence = arm["relation"]["evidence"]
        semantic = arm["relation"]["semantic"]
        endpoint = arm["relation"]["endpointResolution"]
        bucket_counts.update(
            {key: int(value) for key, value in evidence["counts"].items()}
        )
        semantic_counts.update(
            {key: int(value) for key, value in semantic["counts"].items()}
        )
        endpoint_counts.update(
            {
                "resolved": int(endpoint["resolved"]),
                "wrong": int(endpoint["wrong"]),
                "missing": int(endpoint["missing"]),
            }
        )
        findings.append(
            {
                "caseId": str(record["caseId"]),
                "runId": int(record["runId"]),
                "count": count,
                "semanticDisposition": "exactMatch_only_if_reconciled",
                "observedSemanticBuckets": dict(semantic["counts"]),
                "observedEvidenceBuckets": dict(evidence["counts"]),
                "endpointResolution": {
                    "resolved": int(endpoint["resolved"]),
                    "wrong": int(endpoint["wrong"]),
                    "missing": int(endpoint["missing"]),
                },
                "materializerReason": "unknown_sanitized_report",
            }
        )
    return {
        "findingCount": sum(item["count"] for item in findings),
        "affectedCaseRuns": len(findings),
        "bucketTotals": dict(bucket_counts),
        "semanticBucketTotals": dict(semantic_counts),
        "endpointTotals": dict(endpoint_counts),
        "findings": findings,
    }


def build_diagnostic_artifact(report: Mapping[str, Any]) -> dict[str, Any]:
    """Build a deterministic RM-28 artifact from sanitized report fields."""

    records = list(report["caseRecords"])
    schema_failures, schema_counts = _schema_failures(records)
    evidence = _evidence_findings(records)
    accounting = report["accounting"]
    gold_relations = [record["arms"]["gold-relations"] for record in records]
    control_invalid_evidence = sum(
        int(item["invalidEvidenceCount"]) for item in gold_relations
    )
    return {
        "artifactVersion": "s12.s12-f-12.rm28-offline-remediation.v1",
        "status": "OFFLINE_REMEDIATION_PREPARED_PENDING_OWNER_REVIEW",
        "taskId": "S12-RM-28",
        "experimentId": "s12-f-12",
        "sourceEvidence": {
            "path": REPORT.relative_to(ROOT).as_posix(),
            "digest": REPORT_DIGEST,
            "providerCallsAttempted": int(accounting["providerCallsAttempted"]),
            "retryCount": int(accounting["retryCount"]),
            "rawProviderPayloadsAvailable": False,
            "heldOutDataInspected": False,
        },
        "provenFindings": {
            "schemaInvalidTotal": int(accounting["failureClasses"]["schemaInvalid"]),
            "schemaInvalidByArmStage": dict(schema_counts),
            "schemaInvalidResponses": schema_failures,
            "invalidEvidenceTotal": int(evidence["findingCount"]),
            "invalidEvidence": evidence,
            "goldRelationsControlInvalidEvidence": control_invalid_evidence,
            "candidateIdentityBottleneck": {
                "predictedEntityStage1SchemaInvalid": int(
                    schema_counts["predicted-entities:stage1"]
                ),
                "goldEntityStage2EndpointWrongOrMissing": evidence["endpointTotals"],
                "claim": "candidate entity/identity path is implicated; exact provider cause is not observable",
            },
        },
        "unknownsPreserved": [
            "exact malformed provider field or JSON Schema path for the six schema-invalid responses",
            "whether each schema-invalid response failed envelope JSON shape or semantic parser constraints",
            "exact triggerQuote/evidence offsets and source slice for the 17 unsupported findings",
            "sole provider, model, prompt or sampling causality",
        ],
        "remediation": {
            "diagnosticContract": "evaluation/sprint-12/optimization/s12-f-12-rm28-diagnostic-contract.v1.json",
            "serverOwnedChanges": [
                "classify schema failures into a finite reason code before sanitization",
                "materialize trigger quote digest and evidence support checks from runtime source",
                "persist only reason codes, counts, response digests and denominators",
                "retain typed candidate-table identity mapping and fail closed on unresolved endpoints",
            ],
            "promptChanges": [
                "retain the existing two-step prompt as a superseding candidate input only",
                "require schema-only JSON and candidate IDs from the server-owned table",
                "require one non-empty triggerQuote and evidence span per relation",
            ],
            "finiteBacklog": [
                {"id": "RM28-SCHEMA-01", "status": "pending_owner_review", "scope": "add sanitized schema reason codes"},
                {"id": "RM28-EVIDENCE-01", "status": "pending_owner_review", "scope": "add sanitized evidence rejection reason counts"},
                {"id": "RM28-IDENTITY-01", "status": "implemented_offline", "scope": "reuse typed span identity map and endpoint accounting"},
                {"id": "RM28-EXEC-01", "status": "closed", "scope": "new provider run requires superseding lineage and owner authorization"},
            ],
        },
        "governance": {
            "providerExecutionAuthorized": False,
            "preregistrationIssued": False,
            "technicalFreezeIssued": False,
            "newAuthorizationIssued": False,
            "validationAccessAuthorized": False,
            "heldOutAccessAuthorized": False,
            "stageBAuthorized": False,
            "candidateSelectionAuthorized": False,
            "promotionAuthorized": False,
            "nextGate": "owner review of RM-28 offline remediation package",
        },
    }


def build_from_immutable_report(path: Path = REPORT) -> dict[str, Any]:
    return build_diagnostic_artifact(load_report(path))


if __name__ == "__main__":
    print(json.dumps(build_from_immutable_report(), indent=2, sort_keys=True))
