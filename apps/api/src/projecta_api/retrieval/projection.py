"""Typed projection mapping from Semantic Core rows."""

import re
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import cast

from projecta_api.retrieval.contracts import Citation, Derivation, Fact, ProjectionMeta
from projecta_api.retrieval.errors import RetrievalError, RetrievalErrorCode

JsonObject = Mapping[str, object]


def project(payload: object) -> tuple[list[Fact], list[Citation], ProjectionMeta]:
    root = _mapping(payload)
    raw_items = root.get("items")
    if not isinstance(raw_items, list):
        raise RetrievalError(RetrievalErrorCode.MALFORMED_PROVIDER_OUTPUT)
    meta_raw = _mapping(root.get("meta"))
    source_revision = meta_raw.get("sourceRevision")
    if not isinstance(source_revision, str) or not source_revision:
        raise RetrievalError(RetrievalErrorCode.MALFORMED_PROVIDER_OUTPUT)
    as_of = meta_raw.get("asOf")
    if as_of is not None and not isinstance(as_of, (str, datetime)):
        raise RetrievalError(RetrievalErrorCode.MALFORMED_PROVIDER_OUTPUT)
    try:
        meta = ProjectionMeta.model_validate({
            "projectionVersion": "m4.v1",
            "sourceRevision": source_revision,
            "asOf": as_of or datetime.now(UTC),
            "partial": bool(meta_raw.get("partial", False)),
            "stale": bool(meta_raw.get("stale", False)),
        })
    except (TypeError, ValueError) as error:
        raise RetrievalError(RetrievalErrorCode.MALFORMED_PROVIDER_OUTPUT) from error

    facts: list[Fact] = []
    citations: list[Citation] = []
    for raw_value in cast(list[object], raw_items):
        raw = _mapping(raw_value)
        try:
            fact_id = raw.get("id")
            if not isinstance(fact_id, str) or re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", fact_id) is None:
                raise ValueError("fact ID must be opaque")
            fact_type = raw.get("type")
            label = raw.get("label")
            status = raw.get("status", "asserted")
            if not all(isinstance(value, str) for value in (fact_type, label, status)):
                raise ValueError("fact fields are malformed")
            raw_as_of = raw.get("asOf")
            if raw_as_of is not None and not isinstance(raw_as_of, (str, datetime)):
                raise ValueError("fact as-of is malformed")
            raw_citations = raw.get("citations")
            citation_values: list[object] = cast(list[object], raw_citations) if isinstance(raw_citations, list) else [raw.get("citation")]
            citation_ids: list[str] = []
            for citation_value in citation_values:
                if isinstance(citation_value, Mapping):
                    citation = Citation.model_validate(_plain(cast(Mapping[object, object], citation_value)))
                    citations.append(citation)
                    citation_ids.append(citation.id)
            derivation_value = raw.get("derivation")
            derivation = Derivation.model_validate(_plain(cast(Mapping[object, object], derivation_value))) if isinstance(derivation_value, Mapping) else None
            facts.append(Fact.model_validate({
                "id": fact_id,
                "type": fact_type,
                "label": label,
                "status": status,
                "asOf": raw_as_of,
                "citationIds": citation_ids,
                "derivation": derivation,
            }))
        except (KeyError, TypeError, ValueError) as error:
            raise RetrievalError(RetrievalErrorCode.MALFORMED_PROVIDER_OUTPUT) from error
    return facts, citations, meta


def _mapping(value: object) -> JsonObject:
    if not isinstance(value, Mapping):
        raise RetrievalError(RetrievalErrorCode.MALFORMED_PROVIDER_OUTPUT)
    return cast(JsonObject, value)


def _plain(value: Mapping[object, object]) -> dict[str, object]:
    return {str(key): item for key, item in value.items()}
