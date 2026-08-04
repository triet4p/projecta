"""Deterministic bounded question interpretation."""

import re

from projecta_api.retrieval.contracts import QueryIntent
from projecta_api.retrieval.errors import RetrievalError, RetrievalErrorCode

_HISTORY = re.compile(r"\b(history|changed|change|supersed|previous|before|what changed)\b", re.I)
_BLOCKER = re.compile(r"\b(block|blocking|blocker|blockers|blocked|dependency|dependencies)\b", re.I)
_CURRENT = re.compile(r"\b(current|present|active|latest|requirements?)\b", re.I)
_DIRECT_ID = re.compile(r"\breq-[a-z0-9][a-z0-9-]{0,62}\b", re.I)
_LABELED_ID = re.compile(r"\b(?:requirement|req)[\s:#]+([a-z0-9][a-z0-9-]{0,62})\b", re.I)


def interpret(question: str, *, limit: int = 50) -> QueryIntent:
    """Map supported language to one allowlisted query and typed parameters."""
    if not question or not question.strip():
        raise RetrievalError(RetrievalErrorCode.UNKNOWN_INTENT)
    if limit < 1 or limit > 100:
        raise RetrievalError(RetrievalErrorCode.UNSUPPORTED_FILTER)
    text = question.strip()
    if re.search(r"\bproject\s+(?!this\b|the\b|current\b)[a-z0-9-]+", text, re.I):
        raise RetrievalError(RetrievalErrorCode.CROSS_PROJECT_ACCESS)
    params: dict[str, str | int] = {"limit": limit}
    direct_match = _DIRECT_ID.search(text)
    labeled_match = _LABELED_ID.search(text)
    if _HISTORY.search(text):
        if not direct_match and not labeled_match:
            raise RetrievalError(RetrievalErrorCode.AMBIGUOUS_MATCH)
        if direct_match:
            requirement_id = direct_match.group(0)
        else:
            assert labeled_match is not None
            requirement_id = labeled_match.group(1)
        params["requirementId"] = requirement_id.lower()
        return QueryIntent(queryId="requirement-history", parameters=params)
    if _BLOCKER.search(text):
        return QueryIntent(queryId="unresolved-blockers", parameters=params)
    if _CURRENT.search(text):
        return QueryIntent(queryId="current-requirements", parameters=params)
    raise RetrievalError(RetrievalErrorCode.UNKNOWN_INTENT)
