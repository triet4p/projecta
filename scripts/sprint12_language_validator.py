#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Audit Sprint 12 declared source languages without reading held-out data."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "evaluation/sprint-12/corpus"
VALIDATOR_VERSION = "s12.language-validator.v2"
ALLOWED_LANGUAGES = {"en", "vi", "ja", "mixed"}
GENERATOR_MARKER_PATTERN = re.compile(
    r"\b(?:evidence\s+marker|distinguishing\s+phrase)\b"
    r"[^.!?;\n]*(?:[.!?;]|$)",
    re.IGNORECASE,
)
TOKEN_PATTERN = re.compile(r"[a-z]+", re.IGNORECASE)
VI_DIACRITIC_PATTERN = re.compile(r"[ăâđêôơưáàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệ"
                                   r"íìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ]", re.IGNORECASE)
VI_WORDS = {
    "bị",
    "cho",
    "chạy",
    "có",
    "đã",
    "định",
    "giả",
    "giải",
    "khai",
    "phải",
    "triển",
    "trong",
    "trễ",
    "tạm",
    "ổn",
}
EN_WORDS = {
    "an",
    "and",
    "asserted",
    "be",
    "commitment",
    "create",
    "decided",
    "delivery",
    "details",
    "from",
    "ignore",
    "in",
    "is",
    "item",
    "later",
    "link",
    "may",
    "new",
    "of",
    "or",
    "previous",
    "private",
    "project",
    "question",
    "release",
    "requirement",
    "review",
    "risk",
    "rule",
    "scope",
    "team",
    "the",
    "this",
    "to",
    "unclear",
    "use",
    "without",
}


class LanguageValidationError(ValueError):
    """Raised when the validator receives malformed or sealed input."""


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _hash(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _has_japanese(text: str) -> bool:
    return any(
        0x3040 <= ord(character) <= 0x30FF or 0x4E00 <= ord(character) <= 0x9FFF
        for character in text
    )


def infer_language(text: str) -> dict[str, Any]:
    """Infer a coarse language class for deterministic metadata triage."""

    text_without_markers = GENERATOR_MARKER_PATTERN.sub(" ", text)
    tokens = TOKEN_PATTERN.findall(text_without_markers.casefold())
    english_hits = sum(token in EN_WORDS for token in tokens)
    vietnamese_hits = sum(token in VI_WORDS for token in tokens)
    has_vietnamese_signal = bool(VI_DIACRITIC_PATTERN.search(text_without_markers))
    has_english_signal = english_hits >= 2
    has_japanese_signal = _has_japanese(text_without_markers)
    script_count = sum(
        (has_english_signal, has_vietnamese_signal, has_japanese_signal)
    )

    if script_count >= 2 or (has_japanese_signal and (has_english_signal or has_vietnamese_signal)):
        language = "mixed"
    elif has_japanese_signal:
        language = "ja"
    elif has_vietnamese_signal:
        language = "vi"
    elif has_english_signal:
        language = "en"
    else:
        language = "unknown"
    confidence = "high" if language != "unknown" else "low"
    return {
        "language": language,
        "confidence": confidence,
        "englishLexicalHits": english_hits,
        "vietnameseLexicalHits": vietnamese_hits,
        "vietnameseDiacriticSignal": has_vietnamese_signal,
        "japaneseScriptSignal": has_japanese_signal,
    }


def _slice_rows(
    cases: list[dict[str, Any]],
    mismatches: list[dict[str, Any]],
    qualified_review: bool,
) -> dict[str, Any]:
    declared_counts = Counter(str(case["source"]["language"]) for case in cases)
    mismatch_by_language = Counter(str(row["declaredLanguage"]) for row in mismatches)
    rows = []
    for language in sorted(declared_counts):
        rows.append(
            {
                "language": language,
                "caseCount": declared_counts[language],
                "mismatchCount": mismatch_by_language[language],
                "qualifiedReview": qualified_review,
                "eligibleForBenchmark": qualified_review
                and mismatch_by_language[language] == 0,
            }
        )
    return {
        "declaredLanguageCounts": dict(sorted(declared_counts.items())),
        "slices": rows,
        "eligibleSlices": [
            row["language"] for row in rows if row["eligibleForBenchmark"]
        ],
    }


def analyze_cases(
    cases: list[dict[str, Any]], qualified_review: bool
) -> dict[str, Any]:
    if any(case.get("split") == "test" for case in cases):
        raise LanguageValidationError(
            "test payload was supplied; language validation must not read held-out data"
        )
    mismatches = []
    inferred_counts = Counter()
    for case in cases:
        case_id = str(case["caseId"])
        source = case.get("source")
        if not isinstance(source, dict) or not isinstance(source.get("rawText"), str):
            raise LanguageValidationError(f"missing rawText for atomic case {case_id}")
        declared = source.get("language")
        if declared not in ALLOWED_LANGUAGES:
            raise LanguageValidationError(
                f"unsupported declared language {declared!r} for {case_id}"
            )
        inferred = infer_language(source["rawText"])
        inferred_counts[inferred["language"]] += 1
        if inferred["confidence"] == "high" and inferred["language"] != declared:
            mismatches.append(
                {
                    "caseId": case_id,
                    "split": str(case["split"]),
                    "declaredLanguage": declared,
                    "inferredLanguage": inferred["language"],
                    "confidence": inferred["confidence"],
                    "evidenceHash": _hash(json.dumps(inferred, sort_keys=True)),
                }
            )
    slices = _slice_rows(cases, mismatches, qualified_review)
    return {
        "caseCount": len(cases),
        "splitCounts": {
            split: sum(case.get("split") == split for case in cases)
            for split in ("development", "validation")
        },
        "inferredLanguageCounts": dict(sorted(inferred_counts.items())),
        "mismatchCount": len(mismatches),
        "mismatches": mismatches,
        "slices": slices,
        "qualifiedReview": qualified_review,
        "pass": not mismatches and qualified_review,
    }


def validate(
    atomic_payload: dict[str, Any],
    manifest: dict[str, Any],
    qa_report: dict[str, Any],
) -> dict[str, Any]:
    qualified_review = bool(
        qa_report.get("humanEvidence") is True
        and qa_report.get("independentLabelsPresent") is True
    )
    atomic = analyze_cases(atomic_payload["cases"], qualified_review)
    declared_slices = sorted(atomic["slices"]["declaredLanguageCounts"])
    return {
        "reportVersion": VALIDATOR_VERSION,
        "datasetVersion": atomic_payload.get("datasetVersion"),
        "status": "BLOCKED_LANGUAGE_METADATA"
        if not atomic["pass"]
        else "LANGUAGE_METADATA_READY",
        "readScope": {
            "atomicPayloadSplits": atomic["splitCounts"],
            "testPayloadRead": False,
            "testPayloadStatus": "not-available-custody",
            "testManifestCount": manifest.get("atomicCounts", {}).get("test"),
        },
        "review": {
            "qualifiedReview": qualified_review,
            "sourceReportVersion": qa_report.get("reportVersion"),
            "humanEvidence": qa_report.get("humanEvidence"),
            "independentLabelsPresent": qa_report.get("independentLabelsPresent"),
            "excludedSlicesWithoutQualifiedReview": declared_slices
            if not qualified_review
            else [],
        },
        "atomic": atomic,
        "gates": {
            "languageMetadataConsistent": atomic["mismatchCount"] == 0,
            "qualifiedReviewPresent": qualified_review,
            "eligibleLanguageSlices": atomic["slices"]["eligibleSlices"],
        },
    }


def validate_paths(
    atomic_path: Path, manifest_path: Path, qa_path: Path
) -> dict[str, Any]:
    return validate(read_json(atomic_path), read_json(manifest_path), read_json(qa_path))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--atomic",
        type=Path,
        default=CORPUS / "atomic-development-validation.v2.json",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=CORPUS / "manifest.v2.json",
    )
    parser.add_argument(
        "--qa",
        type=Path,
        default=CORPUS / "qa/qa-report.v2.json",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = validate_paths(args.atomic, args.manifest, args.qa)
    serialized = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(serialized, encoding="utf-8")
    print(serialized, end="")


if __name__ == "__main__":
    main()
