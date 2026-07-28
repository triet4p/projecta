#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "rdflib==7.6.0",
# ]
# ///
# pyright: strict

"""Run the complete Sprint 1 ontology validation suite.

The canonical invocation runs this file inside the Jena tools container:

    docker compose run --build --rm ontology-test
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import rdflib
from rdflib.namespace import OWL, RDF
from rdflib.query import ResultRow

ONTOLOGY_DIR = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/data")
CQ_DIR = ONTOLOGY_DIR / "competency-questions"
EXAMPLES_DIR = ONTOLOGY_DIR / "examples"

ONTOLOGY_FILES = (
    ONTOLOGY_DIR / "core.ttl",
    ONTOLOGY_DIR / "communication.ttl",
)
SYNTAX_FILES = ONTOLOGY_FILES + (
    EXAMPLES_DIR / "quick-note-demo.trig",
    EXAMPLES_DIR / "negative-orphan-noteitem.trig",
    EXAMPLES_DIR / "negative-missing-project.trig",
    EXAMPLES_DIR / "negative-invalid-itemtype.trig",
)

EXPECTED_ROWS = {
    "CQ-NOTE-001": 1,
    "CQ-NOTE-002": 1,
    "CQ-NOTE-003": 1,
    "CQ-NOTE-004": 1,
    "CQ-NOTEITEM-001": 6,
    "CQ-NOTEITEM-002": 1,
    "CQ-NOTEITEM-003": 1,
    "CQ-PROV-001": 1,
    "CQ-PROV-002": 1,
    "CQ-PROV-003": 6,
    "CQ-COUNT-001": 6,
    "CQ-COUNT-002": 1,
}
EXPECTED_ASK = {
    "CQ-BOUND-001": False,
    "CQ-BOUND-002": False,
}
NEGATIVE_FIXTURES = {
    "NEG-ORPHAN-NOTEITEM": "negative-orphan-noteitem.trig",
    "NEG-MISSING-PROJECT": "negative-missing-project.trig",
    "NEG-INVALID-ITEMTYPE": "negative-invalid-itemtype.trig",
}
EXPECTED_ITEM_TYPES = {
    "requirement",
    "decision",
    "question",
    "task",
    "risk",
    "assumption",
}


@dataclass
class Check:
    name: str
    passed: bool
    detail: str = ""


def merge_dataset(files: tuple[Path, ...]) -> rdflib.Graph:
    dataset = rdflib.Dataset()
    for path in files:
        dataset.parse(path, format="trig" if path.suffix == ".trig" else "turtle")

    graph = rdflib.Graph()
    for context in dataset.graphs():
        for triple in context:
            graph.add(triple)
    return graph


def query_blocks(path: Path) -> dict[str, str]:
    content = path.read_text(encoding="utf-8")
    matches = list(
        re.finditer(
            r"(?m)^# --- ([A-Z]+(?:-[A-Z]+)*-\d+|NEG-[A-Z-]+) ---\s*$",
            content,
        )
    )
    if not matches:
        raise ValueError(f"No delimited queries found in {path}")

    prefix = content[: matches[0].start()]
    blocks: dict[str, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
        blocks[match.group(1)] = prefix + content[match.start() : end]
    return blocks


def validate_syntax() -> list[Check]:
    checks: list[Check] = []
    for path in SYNTAX_FILES:
        result = subprocess.run(
            ["riot", "--validate", str(path)],
            capture_output=True,
            check=False,
            text=True,
        )
        detail = (result.stderr or result.stdout).strip()
        checks.append(
            Check(
                f"Jena syntax: {path.relative_to(ONTOLOGY_DIR)}",
                result.returncode == 0,
                detail,
            )
        )
    return checks


def validate_vocabulary(graph: rdflib.Graph) -> list[Check]:
    projecta = rdflib.Namespace("https://w3id.org/projecta/ontology/")
    actual = {
        "classes": len(set(graph.subjects(RDF.type, OWL.Class))),
        "object properties": len(set(graph.subjects(RDF.type, OWL.ObjectProperty))),
        "datatype properties": len(set(graph.subjects(RDF.type, OWL.DatatypeProperty))),
        "NoteItemType individuals": len(
            set(graph.subjects(RDF.type, projecta.NoteItemType))
        ),
    }
    expected = {
        "classes": 9,
        "object properties": 6,
        "datatype properties": 3,
        "NoteItemType individuals": 9,
    }
    return [
        Check(
            f"Vocabulary count: {name}",
            actual[name] == count,
            f"expected={count}, actual={actual[name]}",
        )
        for name, count in expected.items()
    ]


def validate_competency_queries(graph: rdflib.Graph) -> list[Check]:
    checks: list[Check] = []
    blocks = query_blocks(CQ_DIR / "quick-note-queries.rq")

    expected_ids = set(EXPECTED_ROWS) | set(EXPECTED_ASK)
    checks.append(
        Check(
            "Competency query inventory",
            set(blocks) == expected_ids,
            f"expected={len(expected_ids)}, actual={len(blocks)}",
        )
    )

    for query_id, query in blocks.items():
        try:
            result = graph.query(query)
            if result.type == "ASK":
                actual = bool(result.askAnswer)
                expected = EXPECTED_ASK[query_id]
                checks.append(
                    Check(
                        query_id,
                        actual == expected,
                        f"expected={expected}, actual={actual}",
                    )
                )
                continue

            rows = [cast(ResultRow, row) for row in result]
            expected_count = EXPECTED_ROWS[query_id]
            passed = len(rows) == expected_count
            detail = f"expected rows={expected_count}, actual rows={len(rows)}"

            if query_id == "CQ-NOTEITEM-001" and passed:
                actual_types = {str(row[1]).rsplit("/", 1)[-1] for row in rows}
                passed = actual_types == EXPECTED_ITEM_TYPES
                detail += f", types={sorted(actual_types)}"
            elif query_id == "CQ-COUNT-001" and passed:
                passed = all(int(str(row[1])) == 1 for row in rows)
                detail += ", each count=1"
            elif query_id == "CQ-COUNT-002" and passed:
                passed = int(str(rows[0][0])) == 1
                detail += f", count={rows[0][0]}"

            checks.append(Check(query_id, passed, detail))
        except Exception as exc:  # noqa: BLE001 - report every query before exit.
            checks.append(Check(query_id, False, str(exc)))
    return checks


def validate_negative_fixtures(clean_graph: rdflib.Graph) -> list[Check]:
    checks: list[Check] = []
    blocks = query_blocks(CQ_DIR / "negative-queries.rq")
    checks.append(
        Check(
            "Negative query inventory",
            set(blocks) == set(NEGATIVE_FIXTURES),
            f"expected={len(NEGATIVE_FIXTURES)}, actual={len(blocks)}",
        )
    )

    for query_id, fixture_name in NEGATIVE_FIXTURES.items():
        query = blocks[query_id]
        clean_result = bool(clean_graph.query(query).askAnswer)
        checks.append(
            Check(
                f"{query_id}: clean graph",
                clean_result is False,
                f"expected=False, actual={clean_result}",
            )
        )

        negative_graph = merge_dataset(ONTOLOGY_FILES + (EXAMPLES_DIR / fixture_name,))
        negative_result = bool(negative_graph.query(query).askAnswer)
        checks.append(
            Check(
                f"{query_id}: negative fixture",
                negative_result is True,
                f"expected=True, actual={negative_result}",
            )
        )
    return checks


def main() -> int:
    checks = validate_syntax()
    clean_graph = merge_dataset(
        ONTOLOGY_FILES + (EXAMPLES_DIR / "quick-note-demo.trig",)
    )
    checks.extend(validate_vocabulary(clean_graph))
    checks.extend(validate_competency_queries(clean_graph))
    checks.extend(validate_negative_fixtures(clean_graph))

    for check in checks:
        status = "PASS" if check.passed else "FAIL"
        suffix = f" — {check.detail}" if check.detail else ""
        print(f"{status:4} {check.name}{suffix}")

    failures = [check for check in checks if not check.passed]
    print(f"\nResult: {len(checks) - len(failures)}/{len(checks)} checks passed")
    if failures:
        print("Failed: " + ", ".join(check.name for check in failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
