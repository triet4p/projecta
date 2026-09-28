"""S13 adversarial mutation checks for RM-57 quarantine accounting."""

from __future__ import annotations

import json
from collections import Counter

from projecta_api.extraction.item_validation import (
    ItemMaterializationError,
    require_materializable,
    serialize_item_validation,
    validate_item_batch,
)
from projecta_api.extraction.source_version import create_source_version
from projecta_api.extraction.text_anchor import resolve_text_anchor


def test_duplicate_invalid_items_keep_exact_quarantine_counts_and_block_writes() -> None:
    project_id = "project-alpha"
    content = "The task works."
    source = create_source_version(
        project_id=project_id,
        source_artifact_id="note-quarantine-mutation",
        content=content,
    )
    anchor = resolve_text_anchor(source, content, "task")
    valid = {
        "schemaVersion": "item-validation.v1",
        "kind": "entity",
        "projectId": project_id,
        "sourceVersionId": source.source_version_id,
        "anchor": anchor.model_dump(mode="json", by_alias=True),
        "payload": {"type": "Task", "label": "task", "candidateId": "candidate-valid"},
    }
    malformed = {**valid, "unexpectedField": "must quarantine this input"}
    stale = {**valid, "sourceVersionId": "sv_" + "0" * 64}
    items = [valid, malformed, {**malformed}, stale]

    batch = validate_item_batch(project_id, source, content, items)
    response = json.loads(serialize_item_validation(batch))
    rows = response["results"]

    assert len(rows) == len(items)
    assert [row["itemIndex"] for row in rows] == [0, 1, 2, 3]
    assert [row["reason"] for row in rows] == [
        "VALID",
        "UNKNOWN_SCHEMA_FIELD",
        "UNKNOWN_SCHEMA_FIELD",
        "SOURCE_VERSION_MISMATCH",
    ]
    assert Counter(row["outcome"] for row in rows) == Counter(
        {"contract-valid": 1, "quarantined": 2, "stale": 1}
    )

    materialization_attempts: list[int] = []
    for result in batch.results:
        try:
            require_materializable(result)
        except ItemMaterializationError:
            continue
        materialization_attempts.append(result.item_index)

    assert materialization_attempts == [0]
