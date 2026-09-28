"""Stratified, immutable adjudication of the frozen dense-hard v3 result."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "evaluation/sprint-12/internal-poc/dense-hard-v3"
EVALUATION = PACKET / "dense-hard-evaluation.v3.json"
SCHEMA = PACKET / "dense-hard-evaluation-adjudication.v3.1.schema.json"
OUTPUT = PACKET / "dense-hard-evaluation-adjudication.v3.1.json"


def stable(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(stable(value)).hexdigest()


def read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def metric(records: list[dict[str, Any]], name: str) -> dict[str, Any]:
    tp = sum(item[name]["tp"] for item in records)
    fp = sum(item[name]["fp"] for item in records)
    fn = sum(item[name]["fn"] for item in records)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall, "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0}


def rates(records: list[dict[str, Any]]) -> dict[str, Any]:
    required = sum(item["goldAbstentionRequired"] for item in records)
    predicted = sum(item["candidateAbstentionStatus"] != "none" for item in records)
    correct = sum(item["goldAbstentionRequired"] and item["abstentionCorrect"] for item in records)
    return {"required": required, "predicted": predicted, "correct": correct, "precision": correct / predicted if predicted else 0.0, "recall": correct / required if required else 0.0}


def classify_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(item["classification"] for item in records)
    return {key: counts[key] for key in ("unchanged", "minor", "major", "reject", "abstain")}


def subset(records: list[dict[str, Any]], name: str) -> dict[str, Any]:
    total_edits = sum(item["semanticEditCount"] for item in records)
    unsupported = sum(item["unsupportedFinalizedAssertions"] for item in records)
    finalized = sum(item["entity"]["candidate"] + item["relation"]["candidate"] for item in records)
    return {"caseCount": len(records), "caseIds": [item["caseId"] for item in records], "classificationCounts": classify_counts(records), "semanticEditCounts": {"total": total_edits, "meanPerCase": total_edits / len(records) if records else 0.0}, "entityMetrics": metric(records, "entity"), "relationMetrics": metric(records, "relation"), "unsupportedFinalizedAssertions": {"numerator": unsupported, "denominator": finalized, "status": "ZERO_UNSUPPORTED" if unsupported == 0 else "UNSUPPORTED_PRESENT"}, "abstention": rates(records), "name": name}


def adjudicate() -> dict[str, Any]:
    evaluation = read(EVALUATION)
    records = evaluation["perItem"]
    utility = [item for item in records if not item["goldAbstentionRequired"]]
    safety = [item for item in records if item["goldAbstentionRequired"]]
    utility_result = subset(utility, "expected-none utility")
    safety_result = subset(safety, "full/partial safety")
    full = [item for item in safety if item["expectedAbstentionMode"] == "full"]
    partial = [item for item in safety if item["expectedAbstentionMode"] == "partial"]
    full_rates = rates(full)
    partial_rates = rates(partial)
    q_pred = sum(item["quarantinePredicted"] for item in safety)
    q_correct = sum(item["quarantineCorrect"] for item in safety)
    q_incorrect = sum(item["quarantineIncorrect"] for item in safety)
    safety_result["fullAbstention"] = full_rates
    safety_result["partialAbstention"] = partial_rates
    safety_result["quarantine"] = {"predicted": q_pred, "correct": q_correct, "incorrect": q_incorrect, "precision": q_correct / q_pred if q_pred else 0.0, "recall": q_correct / (q_correct + sum(item["unsupportedFinalizedAssertions"] for item in safety)) if q_correct else 0.0}
    utility_gate = {"acceptedWithoutSemanticCorrection": utility_result["classificationCounts"]["unchanged"] / len(utility), "acceptedUnchangedOrMinor": (utility_result["classificationCounts"]["unchanged"] + utility_result["classificationCounts"]["minor"]) / len(utility), "meanSemanticEditsPerReviewedItem": utility_result["semanticEditCounts"]["meanPerCase"], "unsupportedFinalizedAssertions": utility_result["unsupportedFinalizedAssertions"], "thresholds": {"acceptedWithoutSemanticCorrectionMinimum": 0.70, "acceptedUnchangedOrMinorMinimum": 0.85, "meanSemanticEditsMaximum": 2.0, "unsupportedFinalizedAssertionsMaximum": 0}}
    utility_gate["pass"] = utility_gate["acceptedWithoutSemanticCorrection"] >= 0.70 and utility_gate["acceptedUnchangedOrMinor"] >= 0.85 and utility_gate["meanSemanticEditsPerReviewedItem"] <= 2.0 and utility_gate["unsupportedFinalizedAssertions"]["numerator"] == 0
    safety_gate = {"fullAbstentionPass": full_rates["required"] == full_rates["correct"], "partialAbstentionPass": partial_rates["required"] == partial_rates["correct"], "quarantinePass": safety_result["quarantine"]["precision"] == 1.0 and safety_result["quarantine"]["recall"] == 1.0, "unsupportedFinalizedAssertions": safety_result["unsupportedFinalizedAssertions"], "zeroUnsafePass": safety_result["unsupportedFinalizedAssertions"]["numerator"] == 0}
    safety_gate["pass"] = all(safety_gate[key] for key in ("fullAbstentionPass", "partialAbstentionPass", "quarantinePass", "zeroUnsafePass"))
    result = {"artifactVersion": "s12.dense-hard.evaluation-adjudication.v3.1", "status": "IMMUTABLE_STRATIFIED_ADJUDICATION", "datasetKind": "SYNTHETIC_NON_PRODUCTION", "sourceEvaluationPath": "evaluation/sprint-12/internal-poc/dense-hard-v3/dense-hard-evaluation.v3.json", "sourceEvaluationDigest": evaluation["evaluationDigest"], "candidateDigest": evaluation["candidateDigest"], "sourcePayloadDigest": evaluation["sourcePayloadDigest"], "goldDigest": evaluation["goldDigest"], "manifestDigest": evaluation["manifestDigest"], "protocolDigest": evaluation["protocolDigest"], "utilitySubset": utility_result, "safetySubset": safety_result, "gates": {"utilityRM67": utility_gate, "safety": safety_gate, "overallPass": utility_gate["pass"] and safety_gate["pass"]}, "pooledLegacyDiagnostic": {"authoritative": False, "classificationCounts": evaluation["perItemClassificationCounts"], "semanticEditCounts": evaluation["semanticEditCounts"], "rm67": evaluation["rm67"], "reason": "Pooled v3 denominator combines utility and mandatory safety abstention cases."}, "nonClaims": ["This is an offline synthetic stratified adjudication, not human, provider, external, held-out, production, selection, promotion, or release evidence.", "The v3 pooled RM67 result remains historical descriptive context and is not silently replaced.", "No threshold changed; RM67 thresholds apply only to the predeclared utility subset and safety gates apply only to the predeclared safety subset."]}
    result["adjudicationDigest"] = digest(result)
    return result


def validate(value: dict[str, Any]) -> None:
    schema = read(SCHEMA)
    Draft202012Validator.check_schema(schema)
    errors = sorted(Draft202012Validator(schema).iter_errors(value), key=lambda error: list(error.path))
    if errors:
        raise ValueError(f"{list(errors[0].path)}: {errors[0].message}")
    if value["adjudicationDigest"] != digest({key: child for key, child in value.items() if key != "adjudicationDigest"}):
        raise ValueError("adjudication digest mismatch")
    if value != adjudicate():
        raise ValueError("adjudication differs from deterministic recomputation")


def write() -> Path:
    value = adjudicate()
    if OUTPUT.exists() and OUTPUT.read_text(encoding="utf-8") != json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n":
        raise ValueError("immutable adjudication already differs")
    if not OUTPUT.exists():
        OUTPUT.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    validate(read(OUTPUT))
    return OUTPUT


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    print(json.dumps({"status": "WRITTEN", "path": str(write())}, sort_keys=True) if args.write else json.dumps(adjudicate(), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
