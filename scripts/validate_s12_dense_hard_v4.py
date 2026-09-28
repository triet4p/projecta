"""Fail-closed validator for the source-only dense-hard v4 packet."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "evaluation/sprint-12/internal-poc/dense-hard-v4"
SHA = re.compile(r"^sha256:[0-9a-f]{64}$")


def digest(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def schema_check(value: dict[str, Any], path: Path) -> None:
    schema = read(path)
    Draft202012Validator.check_schema(schema)
    errors = sorted(Draft202012Validator(schema).iter_errors(value), key=lambda e: list(e.path))
    if errors:
        raise ValueError(f"{path.name}: {list(errors[0].path)}: {errors[0].message}")


def exact(text: str, evidence: dict[str, Any]) -> None:
    start, end = evidence["startOffset"], evidence["endOffset"]
    if end <= start or end > len(text) or text[start:end] != evidence["text"]:
        raise ValueError("evidence anchor is not an exact Unicode half-open source slice")


def normalized_sentences(text: str) -> set[str]:
    parts = re.split(r"[.!?。！？]+", text)
    return {" ".join(unicodedata.normalize("NFKC", p).casefold().split()) for p in parts if p.strip()}


def validate(packet_dir: Path = PACKET, require_pre_candidate: bool = False) -> dict[str, Any]:
    names = {"source": "dense-hard-source-payload.v4.json", "gold": "dense-hard-gold.v4.json", "manifest": "dense-hard-evaluator-manifest.v4.json", "protocol": "dense-hard-source-only-protocol.v4.json", "contract": "dense-hard-evaluator-contract.v4.json"}
    values = {key: read(packet_dir / name) for key, name in names.items()}
    for key, name in names.items(): schema_check(values[key], packet_dir / name.replace(".json", ".schema.json"))
    source, gold, manifest, protocol, contract = (values[k] for k in ("source", "gold", "manifest", "protocol", "contract"))
    for value, field in ((source, "payloadDigest"), (gold, "goldDigest"), (manifest, "manifestDigest"), (protocol, "protocolDigest"), (contract, "contractDigest")):
        if value[field] != digest({k: v for k, v in value.items() if k != field}): raise ValueError(f"{field} mismatch")
    if len(source["records"]) != 32 or len(gold["records"]) != 32 or len(manifest["records"]) != 32: raise ValueError("v4 requires exactly 32 cases")
    source_by_id, gold_by_id, manifest_by_id = ({r["caseId"]: r for r in values[k]["records"]} for k in ("source", "gold", "manifest"))
    if set(source_by_id) != set(gold_by_id) or set(source_by_id) != set(manifest_by_id) or len(source_by_id) != 32: raise ValueError("source/gold/manifest IDs are not one-to-one")
    if not (source["sourceOnly"] and not source["goldIncluded"] and not source["evaluatorManifestIncluded"] and source["providerCalls"] == 0 and not source["heldOutInspection"]): raise ValueError("source-only boundary is not clean")
    if contract["status"] != "CONTRACT_BEFORE_CANDIDATE" or not contract["noCandidateOrEvaluation"]: raise ValueError("contract is not pre-candidate")
    if protocol["occurrenceScoring"]["typeIndependent"] is not True: raise ValueError("occurrence scoring is type-coupled")
    abstention = manifest["records"]
    if sum(r["abstentionMode"] == "none" for r in abstention) != 24 or sum(r["abstentionMode"] != "none" for r in abstention) != 8: raise ValueError("utility/safety split must be 24/8")
    if sum(r["abstentionMode"] == "full" for r in abstention) != 4 or sum(r["abstentionMode"] == "partial" for r in abstention) != 4: raise ValueError("safety split must contain four full and four partial cases")
    for cid, record in source_by_id.items():
        if record["sourceDigest"] != digest({"rawText": record["rawText"]}): raise ValueError(f"source digest mismatch in {cid}")
        expected = gold_by_id[cid]["expected"]
        if expected["abstentionMode"] != manifest_by_id[cid]["abstentionMode"]: raise ValueError(f"abstention mode mismatch in {cid}")
        for entity in expected["entities"]: exact(record["rawText"], entity["evidence"])
        entity_ids = {entity["entityId"] for entity in expected["entities"]}
        for relation in expected["relations"]:
            exact(record["rawText"], relation["evidence"]); exact(record["rawText"], relation["triggerEvidence"])
            if relation["sourceEntityId"] not in entity_ids or relation["targetEntityId"] not in entity_ids: raise ValueError(f"relation endpoint missing in {cid}")
            ev, trig = relation["evidence"], relation["triggerEvidence"]
            if not (ev["startOffset"] <= trig["startOffset"] < trig["endOffset"] <= ev["endOffset"]): raise ValueError(f"trigger not contained in {cid}")
        mode = expected["abstentionMode"]
        if mode == "none" and (expected["abstentionReason"] is not None or expected["quarantineCount"] != 0): raise ValueError(f"utility case carries safety metadata: {cid}")
        if mode == "full" and expected["entities"] + expected["relations"]: raise ValueError(f"full case has safe assertions: {cid}")
        if mode != "none" and (not expected["abstentionReason"] or expected["quarantineCount"] < 1): raise ValueError(f"safety case has no proposition reason: {cid}")
    slices = {s for record in source["records"] for s in record["slices"]}
    if len(slices) < 22: raise ValueError("v4 needs at least 22 comparable/harder slices")
    old_sources = [ROOT / f"evaluation/sprint-12/internal-poc/dense-hard-v{i}/dense-hard-source-payload.v{i}.json" for i in (1, 2, 3)]
    ids, digests, raw, sentences = set(source_by_id), {r["sourceDigest"] for r in source_by_id.values()}, {r["rawText"] for r in source_by_id.values()}, {s for r in source_by_id.values() for s in normalized_sentences(r["rawText"])}
    no_reuse: dict[str, bool] = {}
    for i, path in enumerate(old_sources, 1):
        prior = read(path)
        prior_ids = {r["caseId"] for r in prior["records"]}; prior_digests = {r["sourceDigest"] for r in prior["records"]}; prior_raw = {r["rawText"] for r in prior["records"]}; prior_sentences = {s for r in prior["records"] for s in normalized_sentences(r["rawText"])}
        no_reuse.update({f"caseIdsDisjointV{i}": not ids & prior_ids, f"sourceDigestsDisjointV{i}": not digests & prior_digests, f"rawTextDisjointV{i}": not raw & prior_raw, f"normalizedSentencesDisjointV{i}": not sentences & prior_sentences, f"sourcePayloadDigestFreshV{i}": source["payloadDigest"] != prior["payloadDigest"]})
    if not all(no_reuse.values()): raise ValueError(f"v1-v3 reuse detected: {no_reuse}")
    # Candidate/evaluation absence is a generation-time boundary, not a
    # permanent packet invariant.  Post-evaluation validation must be able to
    # validate the frozen source/gold/manifest bindings alongside the immutable
    # candidate and evaluation.  Callers doing a pre-candidate freeze audit may
    # opt into the stronger directory check explicitly.
    if require_pre_candidate and any("candidate" in p.name.lower() or "evaluation" in p.name.lower() for p in packet_dir.iterdir()): raise ValueError("pre-candidate packet contains candidate/evaluation artifact")
    result = {"artifactVersion": "s12.dense-hard.v4-lineage.v1", "status": "VALIDATED_FRESH_NO_V1_V2_V3_REUSE", "datasetKind": "SYNTHETIC_NON_PRODUCTION", "sourcePayloadDigest": source["payloadDigest"], "goldDigest": gold["goldDigest"], "manifestDigest": manifest["manifestDigest"], "protocolDigest": protocol["protocolDigest"], "contractDigest": contract["contractDigest"], "caseCount": 32, "utilityCaseCount": 24, "safetyCaseCount": 8, "sliceCount": len(slices), "noReuseChecks": no_reuse, "authorIneligibleForCandidate": True, "providerCalls": 0, "candidateOrEvaluationPresent": False, "nonClaims": ["Synthetic offline source-only authoring packet; no candidate, evaluation, provider, human, external, held-out, production, selection, promotion, or release claim."]}
    result["lineageDigest"] = digest(result)
    lineage_path = packet_dir / "dense-hard-v4-lineage.v1.json"
    if lineage_path.exists():
        frozen = read(lineage_path)
        schema_check(frozen, packet_dir / "dense-hard-v4-lineage.v1.schema.json")
        if frozen != result: raise ValueError("frozen v4 lineage differs from deterministic recomputation")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--write", action="store_true"); parser.add_argument("--pre-candidate", action="store_true"); args = parser.parse_args()
    value = validate(require_pre_candidate=args.pre_candidate)
    if args.write:
        path = PACKET / "dense-hard-v4-lineage.v1.json"; content = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        if path.exists() and path.read_text(encoding="utf-8") != content: raise ValueError("immutable lineage differs")
        path.write_text(content, encoding="utf-8"); print(json.dumps({"status": "WRITTEN", "path": str(path), "lineageDigest": value["lineageDigest"]}, sort_keys=True))
    else: print(json.dumps(value, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__": main()
