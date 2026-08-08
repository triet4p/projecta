"""Allowlisted browser projections for finite project knowledge views."""

from __future__ import annotations

import re
from hashlib import sha256
from typing import cast
from urllib.parse import unquote, urlsplit

_SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")


def project_current_knowledge(payload: object) -> dict[str, object]:
    """Project Semantic Core bindings into the stable opaque knowledge contract."""
    mapping = _mapping(payload)
    return {
        "requestId": _string(mapping.get("requestId")),
        "items": [
            {
                "id": _opaque_id(row.get("id", row.get("item"))),
                "label": _string(row.get("label")),
                "type": "Requirement",
                "validFrom": _string(row.get("validFrom")),
            }
            for row in _rows(mapping.get("items"))
        ],
    }


def project_candidate_history(payload: object, candidate_id: str) -> dict[str, object]:
    """Project lifecycle history without RDF resource or person IRIs."""
    mapping = _mapping(payload)
    return {
        "requestId": _string(mapping.get("requestId")),
        "candidateId": _opaque_id(candidate_id),
        "items": [
            {
                "id": _opaque_id(row.get("id", row.get("activity"))),
                "decision": _token(row.get("decision")),
                "reviewerId": _opaque_id(row.get("reviewerId", row.get("reviewer"))),
                "endedAt": _string(row.get("endedAt")),
            }
            for row in _rows(mapping.get("items"))
        ],
    }


def project_evidence(payload: object, item_id: str) -> dict[str, object]:
    """Project evidence provenance into IDs and exact user-visible source spans."""
    mapping = _mapping(payload)
    return {
        "requestId": _string(mapping.get("requestId")),
        "itemId": _opaque_id(item_id),
        "items": [
            {
                "candidateId": _opaque_id(row.get("candidateId", row.get("candidate"))),
                "sourceId": _opaque_id(row.get("sourceId", row.get("source"))),
                "noteId": _opaque_id(row.get("noteId", row.get("note"))),
                "authorId": _opaque_id(row.get("authorId", row.get("author"))),
                "reviewerId": _opaque_id(row.get("reviewerId", row.get("reviewer"))),
                "evidenceText": _string(row.get("evidenceText", row.get("sourceText"))),
                "startOffset": _integer(row.get("startOffset")),
                "endOffset": _integer(row.get("endOffset")),
            }
            for row in _rows(mapping.get("items"))
        ],
    }


def _mapping(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    return cast(dict[str, object], value)


def _rows(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    items = cast(list[object], value)
    rows: list[dict[str, object]] = []
    for item in items:
        if isinstance(item, dict):
            rows.append(_mapping(cast(dict[str, object], item)))
    return rows


def _string(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _integer(value: object) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _token(value: object) -> str | None:
    """Return a finite token while removing URI syntax from semantic values."""
    if not isinstance(value, str):
        return None
    return _opaque_id(value)


def _opaque_id(value: object) -> str | None:
    """Expose only the local resource token needed by another finite API route."""
    if not isinstance(value, str) or not value:
        return None
    parsed = urlsplit(value)
    candidate = unquote(parsed.fragment or parsed.path.rsplit("/", 1)[-1] or parsed.path)
    if _SAFE_ID.fullmatch(candidate):
        return candidate
    digest = sha256(value.encode("utf-8")).hexdigest()[:16]
    return f"resource-{digest}"
