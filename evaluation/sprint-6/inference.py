"""Pure deterministic M4 inference functions used by offline and integration tests."""

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DerivedFact:
    id: str
    label: str
    rule_id: str
    rule_version: str
    input_ids: tuple[str, ...]


def infer_unresolved_dependencies(rows: Iterable[dict[str, str]]) -> list[DerivedFact]:
    return [DerivedFact(r["taskId"], r["questionLabel"], "m4.unresolved-dependency", "1", (r["questionId"], r["taskId"])) for r in rows if r.get("questionStatus") == "Open" and r.get("blocks") == "true"]


def infer_delivery_risks(rows: Iterable[dict[str, str]]) -> list[DerivedFact]:
    return [DerivedFact(r["requirementId"], r["requirementLabel"], "m4.delivery-risk", "1", (r["taskId"], r["requirementId"])) for r in rows if r.get("taskStatus") == "Blocked" and r.get("implements") == "true"]


def infer_impact_reviews(rows: Iterable[dict[str, str]]) -> list[DerivedFact]:
    return [DerivedFact(r["taskId"], r["taskLabel"], "m4.impact-review", "1", (r["oldRequirementId"], r["taskId"])) for r in rows if r.get("superseded") == "true" and r.get("implements") == "true"]
