"""Map approved connector evidence to the existing structured source contract."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import cast

from projecta_api.connectors.contracts import CanonicalEvent
from projecta_api.models import NoteItemType, SemanticCaptureRequest, TypedSegment


class ConnectorSourceMappingError(ValueError):
    """Finite mapping failure; raw connector content never enters the message."""

    def __init__(self, code: str = "CONNECTOR_SOURCE_ABSTAINED") -> None:
        self.code = code
        super().__init__(code)


def map_event_to_capture(
    event: CanonicalEvent, content: bytes, *, actor_id: str
) -> SemanticCaptureRequest:
    """Build one bounded Note input from the JSON/Mock source shape."""
    if not actor_id or event.connector_type != "json-mock":
        raise ConnectorSourceMappingError("CONNECTOR_SOURCE_SCOPE_INVALID")
    try:
        decoded = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ConnectorSourceMappingError("CONNECTOR_SOURCE_INVALID") from error
    if not isinstance(decoded, Mapping):
        raise ConnectorSourceMappingError("CONNECTOR_SOURCE_ABSTAINED")
    payload = cast(Mapping[str, object], decoded)
    title = payload.get("title")
    items = payload.get("items")
    if not isinstance(title, str) or not title.strip() or not isinstance(items, list) or not items:
        raise ConnectorSourceMappingError("CONNECTOR_SOURCE_ABSTAINED")
    raw_parts: list[str] = []
    segments: list[TypedSegment] = []
    cursor = 0
    for item in cast(list[object], items):
        if not isinstance(item, Mapping):
            raise ConnectorSourceMappingError("CONNECTOR_SOURCE_ABSTAINED")
        typed_item = cast(Mapping[str, object], item)
        item_type = typed_item.get("type")
        text = typed_item.get("text")
        allowed_types = {
            "requirement", "decision", "question", "task", "risk", "assumption",
            "constraint", "progress-update", "research-need",
        }
        if not isinstance(item_type, str) or item_type not in allowed_types or not isinstance(text, str):
            raise ConnectorSourceMappingError("CONNECTOR_SOURCE_ABSTAINED")
        if raw_parts:
            cursor += 1
        start = cursor
        raw_parts.append(text)
        cursor += len(text)
        segments.append(TypedSegment(type=cast(NoteItemType, item_type), startOffset=start, endOffset=cursor, text=text))
    return SemanticCaptureRequest(
        title=title,
        rawText="\n".join(raw_parts),
        segments=segments,
        sourceKind="connector",
        sourceContentHash=event.content.content_hash,
    )
