#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "pydantic>=2,<3",
# ]
# ///
"""Generate the v2 provider schema from the released Pydantic envelope model."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api" / "src"))

from projecta_api.extraction.relation_evidence_envelope import (
    RelationEvidenceEnvelopeV1,
)

OUTPUT = ROOT / "evaluation/sprint-12/harness/relation-evidence-envelope.schema.v2.json"


def build_schema() -> dict[str, Any]:
    """Return a strict on-wire schema whose nested types mirror Pydantic."""

    schema = RelationEvidenceEnvelopeV1.model_json_schema(by_alias=True)
    schema["$id"] = "s12.relation-evidence-envelope.schema.v2"
    schema["title"] = "S12 relation evidence envelope provider schema v2"
    schema["$comment"] = (
        "Generated from RelationEvidenceEnvelopeV1.model_json_schema(by_alias=True); "
        "the required lists below make defaulted Pydantic fields mandatory on the wire."
    )
    schema["x-runtime-validator"] = (
        "projecta_api.extraction.relation_evidence_envelope.RelationEvidenceEnvelopeV1"
    )
    schema["x-validation-invariants"] = [
        "m3.v2 entity candidateId values are present and unique",
        "abstentionReason is mutually exclusive with extraction candidates",
        "empty extraction requires abstentionReason",
        "one unique relationTriggers item exists for every relation endpoint tuple",
        "EvidenceSpan startOffset is less than endOffset",
    ]
    schema["required"] = ["schemaVersion", "extraction", "relationTriggers"]
    extraction = schema["$defs"]["ExtractionResponse"]
    extraction["required"] = [
        "schemaVersion",
        "modelId",
        "modelVersion",
        "entities",
        "relations",
        "links",
    ]
    return schema


def main() -> None:
    OUTPUT.write_text(
        json.dumps(build_schema(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
