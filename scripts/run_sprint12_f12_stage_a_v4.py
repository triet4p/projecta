# /// script
# requires-python = ">=3.12"
# dependencies = ["jsonschema>=4.23,<5"]
# ///
"""Guarded S12-f-12 runner v4 for the RM-22C remediation.

This module reuses the frozen v3 execution mechanics but installs v4-only
oracle, slice, schema, and authorization guards before delegating execution.
The v3 runner remains historical and is never modified by this wrapper.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import run_sprint12_f12_stage_a_v2 as v2
import run_sprint12_f12_stage_a_v3 as v3
from sprint12_f12_two_step_contracts_v5 import (
    RelationCandidate,
    materialize_evidence_context,
)

PACKAGE = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm22c-execution-package.v4.json"
PREREG = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm22c-issuance-draft.v4.json"
FREEZE = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm22c-technical-freeze.v4.json"
REPORT_SCHEMA = ROOT / "evaluation/sprint-12/harness/s12-f-12-stage-a-report.schema.v4.json"
OUTPUT = ROOT / "evaluation/sprint-12/optimization/s12-f-12-stage-a-report.v4.json"

_ORACLE_TRIGGER_BY_PREDICATE = {"constrainedBy": "bị giới hạn bởi"}
_ORIGINAL_VALIDATE_AUTHORIZATION = v3.validate_authorization


def _trigger(source: str, predicate: str) -> tuple[int, str] | None:
    candidates = [(source.find(predicate), predicate)]
    mapped = _ORACLE_TRIGGER_BY_PREDICATE.get(predicate)
    if mapped is not None:
        candidates.append((source.find(mapped), mapped))
    valid = [(start, quote) for start, quote in candidates if start >= 0]
    return min(valid, key=lambda item: item[0]) if valid else None


def _normalize_gold_relations(case: Mapping[str, Any]) -> list[dict[str, object]]:
    source = str(case["source"]["rawText"])
    result: list[dict[str, object]] = []
    for relation in case["gold"]["relations"]:
        item = dict(relation)
        trigger = _trigger(source, str(relation["predicate"]))
        item["triggerDigest"] = (
            "sha256:" + hashlib.sha256(trigger[1].encode("utf-8")).hexdigest()
            if trigger is not None
            else "sha256:missing"
        )
        item["startOffset"] = int(relation["span"]["start"])
        item["endOffset"] = int(relation["span"]["end"])
        result.append(item)
    return result


def _contexts(case: Mapping[str, Any]) -> dict[tuple[str, str, str], Any]:
    source = str(case["source"]["rawText"])
    contexts: dict[tuple[str, str, str], Any] = {}
    for relation in _normalize_gold_relations(case):
        trigger = _trigger(source, str(relation["predicate"]))
        if trigger is None:
            continue
        start, quote = trigger
        span = relation["span"]
        context = materialize_evidence_context(
            source,
            [(start, start + len(quote))],
            sentence=(0, len(source)),
            clause=(int(span["start"]), int(span["end"])),
        )
        key = (
            str(relation["predicate"]),
            str(relation["sourceEntityId"]),
            str(relation["targetEntityId"]),
        )
        contexts[key] = context
        contexts[
            (
                str(relation["predicate"]),
                f"gold-{relation['sourceEntityId']}",
                f"gold-{relation['targetEntityId']}",
            )
        ] = context
    return contexts


def _gold_relation_candidates(case: Mapping[str, Any]) -> tuple[RelationCandidate, ...]:
    source = str(case["source"]["rawText"])
    candidates: list[RelationCandidate] = []
    for relation in case["gold"]["relations"]:
        predicate = str(relation["predicate"])
        trigger = _trigger(source, predicate)
        candidates.append(
            RelationCandidate(
                predicate,
                f"gold-{relation['sourceEntityId']}",
                f"gold-{relation['targetEntityId']}",
                v3.Decimal(1),
                int(relation["span"]["start"]),
                int(relation["span"]["end"]),
                trigger[1] if trigger is not None else None,
            )
        )
    return tuple(candidates)


def _slice_groups(
    records: Sequence[Mapping[str, Any]],
) -> list[tuple[str, str, list[Mapping[str, Any]], str]]:
    groups = [("all-development", "all-development", list(records), "cases")]
    groups.append(
        (
            "relation-positive",
            "relation-positive",
            [r for r in records if int(r["goldRelationCount"]) > 0],
            "relations",
        )
    )
    groups.append(
        (
            "relation-negative",
            "relation-negative",
            [
                r
                for r in records
                if int(r["goldRelationCount"]) == 0
                and not bool(r["goldAbstentionRequired"])
            ],
            "cases",
        )
    )
    groups.append(
        (
            "abstention-required",
            "abstention-required",
            [r for r in records if bool(r["goldAbstentionRequired"])],
            "cases",
        )
    )
    groups.append(
        (
            "abstention-not-required",
            "abstention-not-required",
            [r for r in records if not bool(r["goldAbstentionRequired"])],
            "cases",
        )
    )
    for journey in ("J1", "J2", "J3", "J4", "J5", "J6"):
        groups.append(
            (
                "journey",
                journey,
                [r for r in records if r["journeyId"] == journey],
                "cases",
            )
        )
    for language in ("en", "ja", "mixed", "vi"):
        groups.append(
            (
                "language",
                language,
                [r for r in records if r["language"] == language],
                "cases",
            )
        )
    return groups


def _validate_report_schema(report: dict[str, Any]) -> None:
    report["artifactVersion"] = "s12-f-12.stage-a-report.v4"
    try:
        from jsonschema import Draft202012Validator
    except ImportError as error:
        raise v3.F12StageAV3Error(
            "jsonschema is required; refusing permissive fallback validation"
        ) from error
    schema = v3.load(REPORT_SCHEMA)
    errors = sorted(
        Draft202012Validator(schema).iter_errors(report),
        key=lambda item: list(item.path),
    )
    if errors:
        location = ".".join(str(item) for item in errors[0].path) or "<root>"
        raise v3.F12StageAV3Error(
            f"report v4 JSON Schema validation failed at {location}: {errors[0].message}"
        )


def validate_authorization(
    authorization_path: Path,
    *,
    package_path: Path = PACKAGE,
    freeze_path: Path = FREEZE,
    output_path: Path = OUTPUT,
) -> dict[str, Any]:
    authorization = v3.load(authorization_path)
    if authorization.get("experimentId") != "s12-f-12":
        raise v3.F12StageAV3Error("authorization experimentId is not s12-f-12")
    required_false = (
        "heldOutInspected",
        "stageBAuthorized",
        "candidateSelectionAuthorized",
        "promotionAuthorized",
    )
    if any(authorization.get(key) is not False for key in required_false):
        raise v3.F12StageAV3Error("authorization opens a sealed governance scope")
    return _ORIGINAL_VALIDATE_AUTHORIZATION(
        authorization_path,
        package_path=package_path,
        freeze_path=freeze_path,
        output_path=output_path,
    )


def _configure() -> None:
    v3.PACKAGE = PACKAGE
    v3.PREREG = PREREG
    v3.FREEZE = FREEZE
    v3.REPORT_SCHEMA = REPORT_SCHEMA
    v3.OUTPUT = OUTPUT
    v3._gold_relation_candidates = _gold_relation_candidates
    v3._slice_groups = _slice_groups
    v3._validate_report_schema = _validate_report_schema
    v3.validate_authorization = validate_authorization
    v2._normalize_gold_relations = _normalize_gold_relations
    v2._contexts = _contexts


def run_stage_a(**kwargs: Any) -> dict[str, Any]:
    _configure()
    return v3.run_stage_a(**kwargs)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Guarded S12-f-12 Stage A runner v4")
    parser.add_argument("--authorization", required=True, type=Path)
    parser.add_argument("--output", default=OUTPUT, type=Path)
    args = parser.parse_args(argv)
    from sprint12_f12_provider_adapter_v2 import F12ProviderAdapterV2

    run_stage_a(
        provider_adapter=F12ProviderAdapterV2.from_environment(),
        authorization_path=args.authorization.resolve(),
        output_path=args.output.resolve(),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
