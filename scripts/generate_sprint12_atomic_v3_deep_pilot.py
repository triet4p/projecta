#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Generate the versioned Sprint 12 atomic v3 deep-pilot fixture."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "evaluation/sprint-12/corpus/v3"
PERMISSION_REF = "sprint12-r09-deep-pilot-v1"
LICENSE = "Projecta-internal-synthetic-v3"


def _note(
    case_number: int,
    journey: str,
    scenario: str,
    split: str,
    language: str,
    text: str,
    entities: list[tuple[str, str]],
    relations: list[tuple[str, str, str, str]] | None = None,
    abstention_reason: str | None = None,
) -> dict[str, Any]:
    return {
        "caseNumber": case_number,
        "journeyId": journey,
        "scenarioId": scenario,
        "split": split,
        "language": language,
        "text": text,
        "entities": entities,
        "relations": relations or [],
        "abstentionReason": abstention_reason,
    }


NOTES = [
    _note(3001, "J1", "s12-s-101", "development", "vi", "Đối soát ví điện tử phải chốt trước kỳ billing thứ Sáu.", [("Đối soát ví điện tử", "Requirement")]),
    _note(3002, "J1", "s12-s-101", "development", "en", "Finance approved Stripe as the fallback when card retries fail.", [("Stripe as the fallback", "Decision")]),
    _note(3003, "J1", "s12-s-101", "development", "mixed", "Job reconcile-payments vẫn blocks release nếu settlement file thiếu.", [("Job reconcile-payments", "Task"), ("settlement file thiếu", "Risk")], [("blocks", "Job reconcile-payments", "settlement file thiếu", "Job reconcile-payments vẫn blocks release nếu settlement file thiếu.")]),
    _note(3004, "J1", "s12-s-101", "development", "vi", "Ai sẽ kiểm tra chargeback trước khi chốt tháng?", [("Ai sẽ kiểm tra chargeback trước khi chốt tháng?", "Question")]),
    _note(3005, "J1", "s12-s-101", "development", "en", "The replay job implements the approved ledger mapping.", [("replay job", "Task"), ("approved ledger mapping", "Requirement")], [("implements", "replay job", "approved ledger mapping", "The replay job implements the approved ledger mapping.")]),
    _note(3006, "J1", "s12-s-101", "development", "vi", "Nếu gateway trả 429, retry window có thể quá ngắn.", [("retry window có thể quá ngắn", "Risk")]),
    _note(3007, "J1", "s12-s-101", "development", "en", "Manual review is constrained by the two-hour refund window.", [("Manual review", "Task"), ("two-hour refund window", "Constraint")], [("constrainedBy", "Manual review", "two-hour refund window", "Manual review is constrained by the two-hour refund window.")]),
    _note(3008, "J1", "s12-s-101", "development", "mixed", "Refunds nên dùng ledger cũ hay mới? Chưa ai chốt.", [], abstention_reason="unresolved choice without an owner decision"),
    _note(3009, "J2", "s12-s-102", "development", "vi", "Đơn outbound phải được khóa trước khi xe rời kho.", [("Đơn outbound phải được khóa trước khi xe rời kho.", "Requirement")]),
    _note(3010, "J2", "s12-s-102", "development", "en", "The loading team decided to scan pallet labels at the bay.", [("scan pallet labels at the bay", "Decision")]),
    _note(3011, "J2", "s12-s-102", "development", "mixed", "Thiếu carton label blocks release shipment ở line B.", [("Thiếu carton label", "Risk"), ("release shipment", "Task")], [("blocks", "Thiếu carton label", "release shipment", "Thiếu carton label blocks release shipment ở line B.")]),
    _note(3012, "J2", "s12-s-102", "development", "vi", "Kho miền Trung hỏi ETA cho chuyến bổ sung sáng mai.", [("Kho miền Trung hỏi ETA cho chuyến bổ sung sáng mai.", "Question")]),
    _note(3013, "J2", "s12-s-102", "development", "en", "Picker training for the new scanner is complete.", [("Picker training for the new scanner is complete.", "ProgressClaim")]),
    _note(3014, "J2", "s12-s-102", "development", "vi", "Barcode bị mờ có thể làm giảm scan pass rate.", [("Barcode bị mờ có thể làm giảm scan pass rate.", "Risk")]),
    _note(3015, "J2", "s12-s-102", "development", "en", "Wave picking depends on the new slotting rule.", [("Wave picking", "Task"), ("new slotting rule", "Requirement")], [("dependsOn", "Wave picking", "new slotting rule", "Wave picking depends on the new slotting rule.")]),
    _note(3016, "J2", "s12-s-102", "development", "en", "We may route overflow to the 3PL, but no decision has been made.", [], abstention_reason="possible routing option without a resolved decision"),
    _note(3017, "J3", "s12-s-103", "development", "vi", "Mọi tenant phải có owner trước khi bật SSO.", [("Mọi tenant phải có owner trước khi bật SSO.", "Requirement")]),
    _note(3018, "J3", "s12-s-103", "development", "en", "The identity team chose OAuth device flow for the partner portal.", [("OAuth device flow for the partner portal", "Decision")]),
    _note(3019, "J3", "s12-s-103", "development", "en", "The migration script implements the approved SSO mapping.", [("migration script", "Task"), ("approved SSO mapping", "Requirement")], [("implements", "migration script", "approved SSO mapping", "The migration script implements the approved SSO mapping.")]),
    _note(3020, "J3", "s12-s-103", "development", "vi", "Ai duyệt danh sách tenant bị khóa trước cutover?", [("Ai duyệt danh sách tenant bị khóa trước cutover?", "Question")]),
    _note(3021, "J3", "s12-s-103", "development", "en", "The dry run for tenant import finished without rejected rows.", [("The dry run for tenant import finished without rejected rows.", "ProgressClaim")]),
    _note(3022, "J3", "s12-s-103", "development", "mixed", "Nếu mapping thiếu region, tenant có thể vào nhầm policy.", [("tenant có thể vào nhầm policy", "Risk")]),
    _note(3023, "J3", "s12-s-103", "development", "en", "Mobile login is constrained by the device-binding policy.", [("Mobile login", "Task"), ("device-binding policy", "Constraint")], [("constrainedBy", "Mobile login", "device-binding policy", "Mobile login is constrained by the device-binding policy.")]),
    _note(3024, "J3", "s12-s-103", "development", "vi", "Giữ login cũ hay tắt ngay? Chưa có quyết định.", [], abstention_reason="unresolved migration choice without a decision"),
    _note(3025, "J4", "s12-s-104", "development", "vi", "Claim draft phải giữ được audit trail từ lúc tạo đến lúc trả tiền.", [("Claim draft phải giữ được audit trail từ lúc tạo đến lúc trả tiền.", "Requirement")]),
    _note(3026, "J4", "s12-s-104", "development", "en", "The claims team approved a two-step review for high-value payouts.", [("two-step review for high-value payouts", "Decision")]),
    _note(3027, "J4", "s12-s-104", "development", "mixed", "Rule fraud-check hỗ trợ reviewer khi claim có dấu hiệu bất thường.", [("Rule fraud-check", "Task"), ("reviewer", "Task")], [("supports", "Rule fraud-check", "reviewer", "Rule fraud-check hỗ trợ reviewer khi claim có dấu hiệu bất thường.")]),
    _note(3028, "J4", "s12-s-104", "development", "vi", "Ai chịu trách nhiệm sign-off claim bị thiếu chứng từ?", [("Ai chịu trách nhiệm sign-off claim bị thiếu chứng từ?", "Question")]),
    _note(3029, "J4", "s12-s-104", "development", "en", "The batch export completed, but two partner files were late.", [("The batch export completed", "ProgressClaim"), ("two partner files were late", "Risk")]),
    _note(3030, "J4", "s12-s-104", "development", "mixed", "Thiếu policy exception blocks auto payout cho claim VIP.", [("Thiếu policy exception", "Risk"), ("auto payout", "Task")], [("blocks", "Thiếu policy exception", "auto payout", "Thiếu policy exception blocks auto payout cho claim VIP.")]),
    _note(3031, "J4", "s12-s-104", "development", "en", "The FAQ assistant answers the question about duplicate claims.", [("FAQ assistant", "Task"), ("the question about duplicate claims", "Question")], [("answers", "FAQ assistant", "the question about duplicate claims", "The FAQ assistant answers the question about duplicate claims.")]),
    _note(3032, "J4", "s12-s-104", "development", "vi", "Export toàn bộ claim hay chỉ các claim đã duyệt? Chưa rõ phạm vi.", [], abstention_reason="scope is unresolved and no owner decision is recorded"),
    _note(3033, "J5", "s12-s-105", "validation", "vi", "Lịch khám phải chừa buffer cho ca tái khám khẩn.", [("Lịch khám phải chừa buffer cho ca tái khám khẩn.", "Requirement")]),
    _note(3034, "J5", "s12-s-105", "validation", "en", "The clinic chose SMS as the default appointment reminder.", [("SMS as the default appointment reminder", "Decision")]),
    _note(3035, "J5", "s12-s-105", "validation", "mixed", "Thiếu consent form blocks appointment confirmation.", [("Thiếu consent form", "Risk"), ("appointment confirmation", "Task")], [("blocks", "Thiếu consent form", "appointment confirmation", "Thiếu consent form blocks appointment confirmation.")]),
    _note(3036, "J5", "s12-s-105", "validation", "vi", "Bệnh nhân có thể đổi lịch qua kênh nào sau khi check-in?", [("Bệnh nhân có thể đổi lịch qua kênh nào sau khi check-in?", "Question")]),
    _note(3037, "J5", "s12-s-105", "validation", "en", "The nurse pilot finished with no missed reminder.", [("The nurse pilot finished with no missed reminder.", "ProgressClaim")]),
    _note(3038, "J5", "s12-s-105", "validation", "en", "Appointment confirmation depends on the consent check.", [("Appointment confirmation", "Task"), ("consent check", "Requirement")], [("dependsOn", "Appointment confirmation", "consent check", "Appointment confirmation depends on the consent check.")]),
    _note(3039, "J5", "s12-s-105", "validation", "ja", "予約確認メールは診療前に必ず送信する。", [("予約確認メールは診療前に必ず送信する。", "Requirement")]),
    _note(3040, "J5", "s12-s-105", "validation", "vi", "Có nên gom lịch tái khám vào một queue không? Chưa thống nhất.", [], abstention_reason="unresolved scheduling policy without agreement"),
    _note(3041, "J6", "s12-s-106", "validation", "vi", "Kỹ thuật viên phải thấy lịch bảo trì trước khi nhận ca.", [("Kỹ thuật viên phải thấy lịch bảo trì trước khi nhận ca.", "Requirement")]),
    _note(3042, "J6", "s12-s-106", "validation", "en", "The field team selected offline mode for the first rollout.", [("offline mode for the first rollout", "Decision")]),
    _note(3043, "J6", "s12-s-106", "validation", "en", "The dispatch checklist implements the safety review agreed yesterday.", [("dispatch checklist", "Task"), ("safety review agreed yesterday", "Requirement")], [("implements", "dispatch checklist", "safety review agreed yesterday", "The dispatch checklist implements the safety review agreed yesterday.")]),
    _note(3044, "J6", "s12-s-106", "validation", "vi", "Ai xác nhận spare part đã tới công trường?", [("Ai xác nhận spare part đã tới công trường?", "Question")]),
    _note(3045, "J6", "s12-s-106", "validation", "en", "The first mobile rollout completed in the pilot region.", [("The first mobile rollout completed in the pilot region.", "ProgressClaim")]),
    _note(3046, "J6", "s12-s-106", "validation", "mixed", "Mất mạng blocks technician sync ở khu vực xa.", [("Mất mạng", "Risk"), ("technician sync", "Task")], [("blocks", "Mất mạng", "technician sync", "Mất mạng blocks technician sync ở khu vực xa.")]),
    _note(3047, "J6", "s12-s-106", "validation", "ja", "現場アプリは端末の省電力設定に制約される。", [("現場アプリ", "Task"), ("端末の省電力設定", "Constraint")], [("constrainedBy", "現場アプリ", "端末の省電力設定", "現場アプリは端末の省電力設定に制約される。")]),
    _note(3048, "J6", "s12-s-106", "validation", "vi", "Sửa lịch bảo trì hay giữ như cũ? Owner chưa trả lời.", [], abstention_reason="unresolved maintenance choice without an owner answer"),
]


def _digest(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _span(text: str, phrase: str) -> dict[str, Any]:
    start = text.find(phrase)
    if start < 0:
        raise ValueError(f"phrase not found: {phrase}")
    return {"start": start, "end": start + len(phrase), "text": phrase}


def build_case(note: dict[str, Any]) -> dict[str, Any]:
    text = note["text"]
    entity_ids: dict[str, str] = {}
    entities = []
    for index, (phrase, entity_type) in enumerate(note["entities"], start=1):
        entity_id = f"entity-{index:02d}"
        entity_ids[phrase] = entity_id
        entities.append(
            {
                "id": entity_id,
                "type": entity_type,
                "label": phrase,
                "span": _span(text, phrase),
            }
        )
    relations = []
    for predicate, source, target, evidence in note["relations"]:
        relations.append(
            {
                "predicate": predicate,
                "sourceEntityId": entity_ids[source],
                "targetEntityId": entity_ids[target],
                "span": _span(text, evidence),
            }
        )
    abstention_required = note["abstentionReason"] is not None
    gold = {
        "entities": [] if abstention_required else entities,
        "relations": [] if abstention_required else relations,
        "links": [],
        "abstention": {
            "required": abstention_required,
            "reason": note["abstentionReason"],
        },
        "semanticGaps": [],
    }
    source = {
        "rawText": text,
        "language": note["language"],
        "origin": "agent-authored-synthetic",
        "sensitivity": "synthetic",
        "license": LICENSE,
        "permissionRef": PERMISSION_REF,
        "contentDigest": "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "authoringNote": "R09 deep pilot synthetic Quick Note; not human-authored evidence.",
    }
    return {
        "caseId": f"s12-a-{note['caseNumber']}",
        "schemaVersion": "s12.atomic.v1",
        "journeyId": note["journeyId"],
        "scenarioId": note["scenarioId"],
        "source": source,
        "split": note["split"],
        "gold": gold,
    }


def build_dataset() -> tuple[dict[str, Any], dict[str, Any]]:
    cases = [build_case(note) for note in NOTES]
    dataset = {
        "datasetVersion": "s12.corpus.atomic.v3.deep-pilot",
        "status": "DEEP_PILOT_AUTHORED_PENDING_QA",
        "authoringTrack": "agent-authored-synthetic",
        "humanEvidence": False,
        "cases": cases,
    }
    entries = []
    for case in cases:
        entries.append(
            {
                "caseId": case["caseId"],
                "scenarioId": case["scenarioId"],
                "journeyId": case["journeyId"],
                "split": case["split"],
                "language": case["source"]["language"],
                "origin": case["source"]["origin"],
                "contentDigest": case["source"]["contentDigest"],
                "caseDigest": _digest(case),
            }
        )
    manifest = {
        "manifestVersion": "s12.corpus.manifest.v3.deep-pilot",
        "datasetVersion": dataset["datasetVersion"],
        "status": "DEEP_PILOT_AUTHORED_PENDING_QA",
        "humanEvidence": False,
        "qualifiedHumanEvidence": False,
        "atomicCounts": {
            "development": sum(case["split"] == "development" for case in cases),
            "validation": sum(case["split"] == "validation" for case in cases),
            "test": 0,
            "total": len(cases),
        },
        "atomicCases": entries,
        "permissionRef": PERMISSION_REF,
        "testPayloadPresent": False,
    }
    manifest["manifestDigest"] = _digest(manifest)
    return dataset, manifest


def write_dataset(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    dataset, manifest = build_dataset()
    (output_dir / "atomic-deep-pilot.v1.json").write_text(
        json.dumps(dataset, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "manifest.v1.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"dataset": dataset["datasetVersion"], **manifest["atomicCounts"]}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    write_dataset(args.output_dir)


if __name__ == "__main__":
    main()
