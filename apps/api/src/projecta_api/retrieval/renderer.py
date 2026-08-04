"""Grounded rendering and claim/citation verification."""

from projecta_api.retrieval.contracts import Answer, Citation, Fact, ProjectionMeta, QueryIntent
from projecta_api.retrieval.errors import RetrievalError, RetrievalErrorCode


def verify(facts: list[Fact], citations: list[Citation]) -> None:
    ids = {citation.id for citation in citations}
    if any(not fact.citation_ids for fact in facts):
        raise RetrievalError(RetrievalErrorCode.NO_EVIDENCE)
    if any(citation_id not in ids for fact in facts for citation_id in fact.citation_ids):
        raise RetrievalError(RetrievalErrorCode.NO_EVIDENCE)
    if any(fact.status == "inferred" and (fact.derivation is None or not fact.derivation.input_ids) for fact in facts):
        raise RetrievalError(RetrievalErrorCode.RULE_FAILURE)


def render(query: QueryIntent, facts: list[Fact], citations: list[Citation], meta: ProjectionMeta) -> Answer:
    verify(facts, citations)
    if meta.stale:
        raise RetrievalError(RetrievalErrorCode.STALE_PROJECTION)
    if not facts:
        text = "No verified facts were found in this project for the requested question."
        return Answer(query=query, text=text, facts=[], citations=[], meta=meta, complete=False, abstained=True, warnings=["no_evidence"])
    elif query.query_id == "current-requirements":
        text = "Current requirements: " + "; ".join(fact.label for fact in facts) + "."
    elif query.query_id == "requirement-history":
        text = "Requirement history: " + "; ".join(fact.label for fact in facts) + "."
    else:
        text = "Unresolved blockers: " + "; ".join(fact.label for fact in facts) + "."
    return Answer(query=query, text=text, facts=facts, citations=citations, meta=meta, complete=True, abstained=False)
