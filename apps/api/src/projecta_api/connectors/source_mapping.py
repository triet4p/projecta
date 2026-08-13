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
    if not actor_id or event.connector_type not in {"json-mock", "teams", "github-public-issues"}:
        raise ConnectorSourceMappingError("CONNECTOR_SOURCE_SCOPE_INVALID")
    try:
        decoded = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ConnectorSourceMappingError("CONNECTOR_SOURCE_INVALID") from error
    if not isinstance(decoded, Mapping):
        raise ConnectorSourceMappingError("CONNECTOR_SOURCE_ABSTAINED")
    payload = cast(Mapping[str, object], decoded)
    if event.connector_type == "teams":
        body_text = payload.get("bodyText")
        if not isinstance(body_text, str) or not body_text.strip():
            raise ConnectorSourceMappingError("CONNECTOR_SOURCE_ABSTAINED")
        deleted = payload.get("deleted") is True
        title = "Teams message (deleted)" if deleted else "Teams message"
        return SemanticCaptureRequest(
            title=title,
            rawText=body_text,
            segments=[
                TypedSegment(
                    type=cast(NoteItemType, "progress-update"),
                    startOffset=0,
                    endOffset=len(body_text),
                    text=body_text,
                )
            ],
            sourceKind="connector",
            sourceContentHash=event.content.content_hash,
        )
    if event.connector_type == "github-public-issues":
        kind = payload.get("kind")
        if kind == "issue":
            title = payload.get("title")
            body = payload.get("body")
            state = payload.get("state")
            if (
                not isinstance(title, str)
                or not title.strip()
                or not isinstance(body, (str, type(None)))
                or state not in {"open", "closed"}
            ):
                raise ConnectorSourceMappingError("CONNECTOR_SOURCE_ABSTAINED")
            body_text = body.strip() if isinstance(body, str) else ""
            raw_text = title.strip() + ("\n" + body_text if body_text else "")
            return SemanticCaptureRequest(
                title="GitHub issue: " + title.strip(),
                rawText=raw_text,
                segments=[
                    TypedSegment(
                        type=cast(NoteItemType, "task" if state == "open" else "progress-update"),
                        startOffset=0,
                        endOffset=len(raw_text),
                        text=raw_text,
                    )
                ],
                sourceKind="connector",
                sourceContentHash=event.content.content_hash,
            )
        if kind == "issue-comment":
            body = payload.get("body")
            if not isinstance(body, str) or not body.strip():
                raise ConnectorSourceMappingError("CONNECTOR_SOURCE_ABSTAINED")
            body_text = body.strip()
            return SemanticCaptureRequest(
                title="GitHub issue comment",
                rawText=body_text,
                segments=[
                    TypedSegment(
                        type=cast(NoteItemType, "progress-update"),
                        startOffset=0,
                        endOffset=len(body_text),
                        text=body_text,
                    )
                ],
                sourceKind="connector",
                sourceContentHash=event.content.content_hash,
            )
        raise ConnectorSourceMappingError("CONNECTOR_SOURCE_ABSTAINED")
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
