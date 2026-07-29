#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "rdflib==7.6.0",
# ]
# ///
# pyright: strict

"""Run the complete Sprint 2 ontology validation suite.

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
SHAPES_DIR = ONTOLOGY_DIR / "shapes"

# ── v0.1 files ──────────────────────────────────────────────────────
ONTOLOGY_FILES = (
    ONTOLOGY_DIR / "core.ttl",
    ONTOLOGY_DIR / "communication.ttl",
)
V01_SYNTAX_FILES = ONTOLOGY_FILES + (
    EXAMPLES_DIR / "quick-note-demo.trig",
    EXAMPLES_DIR / "negative-orphan-noteitem.trig",
    EXAMPLES_DIR / "negative-missing-project.trig",
    EXAMPLES_DIR / "negative-invalid-itemtype.trig",
)

# ── v0.2 files ──────────────────────────────────────────────────────
V02_ONTOLOGY_FILES = ONTOLOGY_FILES + (
    ONTOLOGY_DIR / "provenance.ttl",
    ONTOLOGY_DIR / "temporal.ttl",
)
V02_SYNTAX_FILES = V02_ONTOLOGY_FILES + (
    EXAMPLES_DIR / "lifecycle-demo.trig",
    EXAMPLES_DIR / "benchmark-assertion-node.trig",
    EXAMPLES_DIR / "benchmark-rdf-reification.trig",
    EXAMPLES_DIR / "benchmark-rdf-star.trig",
    EXAMPLES_DIR / "negative-note-no-timestamp.trig",
    EXAMPLES_DIR / "negative-noteitem-no-content.trig",
    SHAPES_DIR / "source-shapes.ttl",
    SHAPES_DIR / "candidate-shapes.ttl",
    SHAPES_DIR / "isolation-shapes.ttl",
    SHAPES_DIR / "temporal-shapes.ttl",
)

# ── v0.1 expected results ───────────────────────────────────────────
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

# ── v0.2 expected results ───────────────────────────────────────────
LIFECYCLE_EXPECTED_ROWS = {
    "CQ-LC-001": 1,
    "CQ-LC-002": 1,
    "CQ-LC-003": 3,
    "CQ-EV-001": 1,
    "CQ-EV-002": 1,
    "CQ-EV-003": 1,
    "CQ-REV-001": 1,
    "CQ-TEMP-001": 1,
    "CQ-TEMP-004": 1,
    "CQ-SCOPE-001": 7,  # 1 Candidate + 2 Requirement types + 4 provenance (3 Activity + 1 Statement)
}
LIFECYCLE_EXPECTED_ASK = {
    "CQ-ISO-001": False,
    "CQ-ISO-002": False,
    "CQ-SCOPE-002": False,
}

# ── SHACL positive fixtures (must conform) ──────────────────────────
SHACL_POSITIVE = (
    EXAMPLES_DIR / "quick-note-demo.trig",
    EXAMPLES_DIR / "lifecycle-demo.trig",
)

# ── SHACL negative fixtures (must fail specific shapes) ─────────────
SHACL_NEGATIVE = {
    EXAMPLES_DIR
    / "shacl-negative-missing-project.ttl": "A Note must belong to exactly one Project.",
    EXAMPLES_DIR
    / "shacl-negative-orphan-noteitem.ttl": "A NoteItem must belong to exactly one Note via isItemOf.",
    EXAMPLES_DIR
    / "shacl-negative-invalid-itemtype.ttl": "A NoteItem's hasItemType must be one of the 9 controlled NoteItemType individuals.",
    EXAMPLES_DIR
    / "shacl-negative-note-no-timestamp.ttl": "A Note must have exactly one recordedAt timestamp of type xsd:dateTime.",
    EXAMPLES_DIR
    / "shacl-negative-noteitem-no-content.ttl": "A NoteItem must have exactly one contentText of type xsd:string.",
}

ISOLATION_NEGATIVE = {
    EXAMPLES_DIR / "shacl-negative-candidate-in-asserted.trig": (
        "projecta:CandidateNotInAssertedShape",
        rdflib.URIRef("https://w3id.org/projecta/ontology/CandidateNotInAssertedShape"),
    ),
    EXAMPLES_DIR / "shacl-negative-knowledgeitem-in-candidates.trig": (
        "projecta:KnowledgeItemNotInCandidatesShape",
        rdflib.URIRef("https://w3id.org/projecta/ontology/KnowledgeItemNotInCandidatesShape"),
    ),
    EXAMPLES_DIR / "shacl-negative-noteitem-outside-sources.trig": (
        "projecta:NoteItemNotOutsideSourcesShape",
        rdflib.URIRef("https://w3id.org/projecta/ontology/NoteItemNotOutsideSourcesShape"),
    ),
    EXAMPLES_DIR / "shacl-negative-activity-outside-provenance.trig": (
        "projecta:ProvActivityNotInProvenanceShape",
        rdflib.URIRef("https://w3id.org/projecta/ontology/ProvActivityNotInProvenanceShape"),
    ),
    EXAMPLES_DIR / "shacl-negative-cross-project-provenance.trig": (
        "projecta:CrossProjectProvenanceShape",
        rdflib.URIRef("https://w3id.org/projecta/ontology/CrossProjectProvenanceShape"),
    ),
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


# ══════════════════════════════════════════════════════════════════════
# v0.1 Validation
# ══════════════════════════════════════════════════════════════════════


def validate_syntax(files: tuple[Path, ...], label: str) -> list[Check]:
    checks: list[Check] = []
    for path in files:
        result = subprocess.run(
            ["riot", "--validate", str(path)],
            capture_output=True,
            check=False,
            text=True,
        )
        detail = (result.stderr or result.stdout).strip()
        checks.append(
            Check(
                f"Jena syntax ({label}): {path.relative_to(ONTOLOGY_DIR)}",
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
        "LifecycleStatus individuals": len(
            set(graph.subjects(RDF.type, projecta.LifecycleStatus))
        ),
    }
    expected = {
        "classes": 13,  # 9 v0.1 + 4 v0.2
        "object properties": 10,  # 6 v0.1 + 4 v0.2 (supersededBy + supersedes inverse)
        "datatype properties": 9,  # 3 v0.1 + 6 v0.2
        "NoteItemType individuals": 9,
        "LifecycleStatus individuals": 8,
    }
    return [
        Check(
            f"Vocabulary count: {name}",
            actual[name] == count,
            f"expected={count}, actual={actual[name]}",
        )
        for name, count in expected.items()
    ]


def validate_competency_queries(
    graph: rdflib.Graph,
    path: Path,
    expected_rows: dict[str, int],
    expected_ask: dict[str, bool],
    label: str,
    dataset: rdflib.Dataset | None = None,
) -> list[Check]:
    checks: list[Check] = []
    blocks = query_blocks(path)

    expected_ids = set(expected_rows) | set(expected_ask)
    checks.append(
        Check(
            f"Competency query inventory ({label})",
            set(blocks) == expected_ids,
            f"expected={len(expected_ids)}, actual={len(blocks)}",
        )
    )

    for query_id, query in blocks.items():
        try:
            # Use Dataset for queries with GRAPH clauses, plain Graph otherwise
            query_target = dataset if (dataset is not None and "GRAPH" in query) else graph
            result = query_target.query(query)
            if result.type == "ASK":
                actual = bool(result.askAnswer)
                expected = expected_ask[query_id]
                checks.append(
                    Check(
                        query_id,
                        actual == expected,
                        f"expected={expected}, actual={actual}",
                    )
                )
                continue

            rows = [cast(ResultRow, row) for row in result]
            expected_count = expected_rows[query_id]
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
        except Exception as exc:  # noqa: BLE001
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


# ══════════════════════════════════════════════════════════════════════
# v0.2 SHACL Validation
# ══════════════════════════════════════════════════════════════════════


def _to_flat_turtle(data_file: Path) -> Path:
    """Convert a TriG or Turtle file to flat Turtle (no named graphs).

    Jena's ``shacl validate --data`` operates on a graph and ignores named
    graph data in TriG files. This helper is therefore intentionally limited
    to graph-agnostic SHACL constraints; named-graph isolation is evaluated
    separately against the unflattened RDF dataset below.
    """
    dataset = rdflib.Dataset()
    # Shapes use sh:class and controlled vocabulary values that are declared
    # by the ontology, so validate the fixture in its actual ontology context.
    for ontology_file in V02_ONTOLOGY_FILES:
        dataset.parse(ontology_file, format="turtle")
    fmt = "trig" if data_file.suffix == ".trig" else "turtle"
    dataset.parse(data_file, format=fmt)

    merged = rdflib.Graph()
    for context in dataset.graphs():
        for triple in context:
            merged.add(triple)

    tmp = Path("/tmp") / data_file.with_suffix(".flat.ttl").name
    merged.serialize(destination=str(tmp), format="turtle")
    # Return path relative to /data so Jena CLI can resolve it
    # (absolute /data paths break on Docker Desktop Windows)
    return Path("..") / "tmp" / tmp.name


def _shacl_data_path(data_file: Path) -> str:
    """Return a path for a SHACL data file that works from any cwd.

    Graph-agnostic data files are converted to flat Turtle in /tmp and referenced
    via ``../../tmp/name`` (which resolves to /tmp/name from any cwd
    under /data or /scripts).  This avoids Docker Desktop Windows
    path-translation issues with absolute paths and cwd uncertainty
    from ``uv run --script``.
    """
    flat_file = _to_flat_turtle(data_file)
    # flat_file = Path("..") / "tmp" / name
    return str(flat_file)


def _shacl_report(result: subprocess.CompletedProcess[str]) -> rdflib.Graph | None:
    """Parse Jena's RDF validation report; its exit code is not conformance."""
    report = result.stdout.strip()
    if not report:
        return None
    graph = rdflib.Graph()
    try:
        graph.parse(data=report, format="turtle")
    except Exception:  # noqa: BLE001
        return None
    return graph


def _shacl_conforms(report: rdflib.Graph) -> bool | None:
    """Return ``sh:conforms`` from a parsed Jena validation report."""
    conforms = rdflib.URIRef("http://www.w3.org/ns/shacl#conforms")
    values = list(report.objects(None, conforms))
    if len(values) != 1:
        return None
    return bool(values[0].toPython())


def validate_shacl_positive(
    data_files: tuple[Path, ...],
    shape_files: tuple[Path, ...],
) -> list[Check]:
    """Run Jena SHACL: every positive fixture must conform to all shapes."""
    checks: list[Check] = []
    for data_file in data_files:
        shape_args: list[str] = []
        for sf in shape_files:
            shape_args.extend(["-shapes", str(sf.relative_to(ONTOLOGY_DIR))])
        cmd = ["shacl", "validate"] + shape_args + ["-datafile", _shacl_data_path(data_file)]
        result = subprocess.run(cmd, capture_output=True, check=False, text=True, cwd=str(ONTOLOGY_DIR))
        report = _shacl_report(result)
        conforms = _shacl_conforms(report) if report is not None else None
        passed = result.returncode == 0 and conforms is True
        detail = "sh:conforms=true" if passed else (
            "missing or malformed Jena SHACL report" if conforms is None
            else "sh:conforms=false"
        )
        checks.append(
            Check(
                f"SHACL conforms: {data_file.relative_to(ONTOLOGY_DIR)}",
                passed,
                detail,
            )
        )
    return checks


def validate_shacl_negative(
    shape_files: tuple[Path, ...],
) -> list[Check]:
    """Run Jena SHACL: each negative fixture must fail on its expected shape."""
    checks: list[Check] = []
    for data_file, expected_shape in SHACL_NEGATIVE.items():
        shape_args: list[str] = []
        for sf in shape_files:
            shape_args.extend(["-shapes", str(sf.relative_to(ONTOLOGY_DIR))])
        cmd = ["shacl", "validate"] + shape_args + ["-datafile", _shacl_data_path(data_file)]
        result = subprocess.run(cmd, capture_output=True, check=False, text=True, cwd=str(ONTOLOGY_DIR))
        report = _shacl_report(result)
        conforms = _shacl_conforms(report) if report is not None else None
        messages = {
            str(message)
            for message in report.objects(None, rdflib.URIRef("http://www.w3.org/ns/shacl#resultMessage"))
        } if report is not None else set()
        passed = result.returncode == 0 and conforms is False and expected_shape in messages
        detail = (
            f"sh:conforms=false; detected expected constraint: {expected_shape}"
            if passed
            else f"expected sh:conforms=false with message {expected_shape!r}; "
            f"actual conforms={conforms}, messages={sorted(messages)}"
        )
        checks.append(
            Check(
                f"SHACL fails: {data_file.relative_to(ONTOLOGY_DIR)}",
                passed,
                detail,
            )
        )
    return checks


def _dataset_from_files(files: tuple[Path, ...]) -> rdflib.Dataset:
    dataset = rdflib.Dataset()
    for path in files:
        dataset.parse(path, format="trig" if path.suffix == ".trig" else "turtle")
    return dataset


def _focus_nodes(dataset: rdflib.Dataset, target_class: rdflib.term.Node) -> set[rdflib.term.Node]:
    return {
        subject
        for context in dataset.graphs()
        for subject in context.subjects(RDF.type, target_class)
    }


def _isolation_violations(dataset: rdflib.Dataset) -> dict[rdflib.term.Node, set[rdflib.term.Node]]:
    """Execute each isolation shape's own SPARQL against the preserved dataset."""
    sh = rdflib.Namespace("http://www.w3.org/ns/shacl#")
    shape_graph = rdflib.Graph()
    shape_graph.parse(SHAPES_DIR / "isolation-shapes.ttl", format="turtle")
    violations: dict[rdflib.term.Node, set[rdflib.term.Node]] = {}
    for shape in shape_graph.subjects(RDF.type, sh.NodeShape):
        query = shape_graph.value(shape, sh.sparql)
        select = shape_graph.value(query, sh.select) if query is not None else None
        if select is None:
            continue
        target_class = shape_graph.value(shape, sh.targetClass)
        target_property = shape_graph.value(shape, sh.targetSubjectsOf)
        if target_class is not None:
            focus = _focus_nodes(dataset, target_class)
        elif target_property is not None:
            focus = {
                subject
                for context in dataset.graphs()
                for subject in context.subjects(target_property, None)
            }
        else:
            raise ValueError(f"Isolation shape {shape} has no SHACL target")
        for node in focus:
            rows = dataset.query(str(select), initBindings={"this": node})
            if any(True for _ in rows):
                violations.setdefault(shape, set()).add(node)
    return violations


def validate_named_graph_isolation() -> list[Check]:
    """Test graph-sensitive SHACL constraints without flattening TriG fixtures."""
    checks: list[Check] = []
    clean = _dataset_from_files((EXAMPLES_DIR / "lifecycle-demo.trig",))
    clean_violations = _isolation_violations(clean)
    for fixture, (shape_label, shape) in ISOLATION_NEGATIVE.items():
        invalid = _dataset_from_files((fixture,))
        invalid_violations = _isolation_violations(invalid)
        passed = not clean_violations.get(shape) and bool(invalid_violations.get(shape))
        checks.append(
            Check(
                f"Named-graph SHACL: {shape_label}",
                passed,
                "clean fixture has no violation; negative TriG fixture is detected"
                if passed
                else f"clean={clean_violations.get(shape, set())}, "
                f"negative={invalid_violations.get(shape, set())}",
            )
        )
    return checks


# ══════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════


def main() -> int:
    checks: list[Check] = []

    # ── v0.1 regression: 32 checks ──────────────────────────────────
    checks.extend(validate_syntax(V01_SYNTAX_FILES, "v0.1"))
    clean_graph = merge_dataset(
        ONTOLOGY_FILES + (EXAMPLES_DIR / "quick-note-demo.trig",)
    )
    checks.extend(validate_vocabulary(merge_dataset(V02_ONTOLOGY_FILES)))
    checks.extend(
        validate_competency_queries(
            clean_graph,
            CQ_DIR / "quick-note-queries.rq",
            EXPECTED_ROWS,
            EXPECTED_ASK,
            "v0.1",
        )
    )
    checks.extend(validate_negative_fixtures(clean_graph))

    # ── v0.2 syntax ─────────────────────────────────────────────────
    checks.extend(validate_syntax(V02_SYNTAX_FILES, "v0.2"))

    # ── v0.2 lifecycle competency queries ────────────────────────────
    lifecycle_graph = merge_dataset(V02_ONTOLOGY_FILES + (EXAMPLES_DIR / "lifecycle-demo.trig",))
    lifecycle_dataset = rdflib.Dataset()
    for p in V02_ONTOLOGY_FILES + (EXAMPLES_DIR / "lifecycle-demo.trig",):
        lifecycle_dataset.parse(p, format="trig" if p.suffix == ".trig" else "turtle")
    checks.extend(
        validate_competency_queries(
            lifecycle_graph,
            CQ_DIR / "lifecycle-queries.rq",
            LIFECYCLE_EXPECTED_ROWS,
            LIFECYCLE_EXPECTED_ASK,
            "v0.2",
            dataset=lifecycle_dataset,
        )
    )

    # ── v0.2 SHACL graph-agnostic constraints ───────────────────────
    # Jena's CLI intentionally receives only shapes that do not need a
    # DatasetGraph. Isolation shapes run against original TriG datasets below.
    graph_shape_files: tuple[Path, ...] = (
        SHAPES_DIR / "source-shapes.ttl",
        SHAPES_DIR / "candidate-shapes.ttl",
        SHAPES_DIR / "temporal-shapes.ttl",
    )
    checks.extend(validate_shacl_positive(SHACL_POSITIVE, graph_shape_files))

    # ── v0.2 SHACL intended-invalid fixtures ─────────────────────────
    checks.extend(validate_shacl_negative(graph_shape_files))

    # ── v0.2 named-graph SHACL SPARQL constraints ────────────────────
    checks.extend(validate_named_graph_isolation())

    # ── Report ──────────────────────────────────────────────────────
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
