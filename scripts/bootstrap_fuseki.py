#!/usr/bin/env python3
"""Safely bootstrap Projecta ontology and optional projects through Fuseki HTTP."""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ONTOLOGY_GRAPH = "https://w3id.org/projecta/data/ontology/dev/"
MODULES = ("core.ttl", "communication.ttl", "provenance.ttl", "temporal.ttl", "evidence.ttl", "llm-extraction-v04.ttl", "m4-retrieval.ttl", "rules/m4-rules.ttl")
PROJECT_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
BOOTSTRAP_REVISION = 1


def main() -> int:
    ontology_dir = Path(os.environ.get("ONTOLOGY_DIRECTORY", "/data"))
    dataset_url = os.environ.get("FUSEKI_DATASET_URL", "http://fuseki:3030/projecta")
    marker_value = os.environ.get("PROJECTA_FUSEKI_BOOTSTRAP_MARKER_FILE", "").strip()
    marker_path = Path(marker_value) if marker_value else None
    marker_phase = _bootstrap_marker_phase(marker_path) if marker_path is not None else None
    if marker_phase in {"complete", "existing-data-preserved"}:
        print("Projecta Fuseki bootstrap is already complete")
        return 0
    if marker_path is not None and marker_phase is None:
        if _dataset_has_data(dataset_url):
            _write_bootstrap_marker(marker_path, "existing-data-preserved")
            print("Existing Fuseki data was left unchanged")
            return 0
        _write_bootstrap_marker(marker_path, "initializing")

    graph_url = f"{dataset_url.rstrip('/')}/data?{urllib.parse.urlencode({'graph': ONTOLOGY_GRAPH})}"
    payload = "\n\n".join((ontology_dir / module).read_text(encoding="utf-8") for module in MODULES)

    request = urllib.request.Request(
        graph_url,
        data=payload.encode("utf-8"),
        method="POST",
        headers={"Content-Type": "text/turtle; charset=utf-8"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        if not 200 <= response.status < 300:
            raise RuntimeError(f"Fuseki returned HTTP {response.status}")

    print(f"Added {len(MODULES)} local ontology modules to the configured ontology graph")
    seeded = _seed_acceptance_projects(dataset_url)
    if seeded:
        print(f"Added {seeded} explicitly configured acceptance projects")
    if marker_path is not None:
        _write_bootstrap_marker(marker_path, "complete")
    return 0


def _seed_acceptance_projects(dataset_url: str) -> int:
    """Load only an explicitly supplied local acceptance fixture."""

    raw = os.environ.get("PROJECTA_BOOTSTRAP_ACCEPTANCE_PROJECTS", "").strip()
    if not raw:
        return 0
    entries: list[tuple[str, str]] = []
    for item in raw.split(";"):
        parts = item.split("|", maxsplit=1)
        if len(parts) != 2:
            raise RuntimeError("acceptance project fixture entry is invalid")
        project_id, label = (part.strip() for part in parts)
        if not PROJECT_ID.fullmatch(project_id) or not label:
            raise RuntimeError("acceptance project fixture entry is invalid")
        entries.append((project_id, label))

    for project_id, label in entries:
        project_iri = f"https://w3id.org/projecta/data/project/{project_id}"
        graph_iri = f"{project_iri}/asserted/"
        graph_url = f"{dataset_url.rstrip('/')}/data?{urllib.parse.urlencode({'graph': graph_iri})}"
        payload = (
            "@prefix projecta: <https://w3id.org/projecta/ontology/> .\n"
            f"<{project_iri}> a projecta:Project ;\n"
            f"  projecta:name {json.dumps(label)} .\n"
        )
        request = urllib.request.Request(
            graph_url,
            data=payload.encode("utf-8"),
            method="POST",
            headers={"Content-Type": "text/turtle; charset=utf-8"},
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            if not 200 <= response.status < 300:
                raise RuntimeError(f"Fuseki returned HTTP {response.status}")
    return len(entries)


def _bootstrap_marker_phase(marker_path: Path) -> str | None:
    """Read a marker while refusing unknown, corrupt, or mismatched state."""

    if not marker_path.exists():
        return None
    try:
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError("Fuseki bootstrap marker is unreadable") from error
    if (
        not isinstance(marker, dict)
        or type(marker.get("schemaVersion")) is not int
        or marker.get("schemaVersion") != 1
    ):
        raise RuntimeError("Fuseki bootstrap marker has an unsupported format")
    revision = marker.get("bootstrapRevision")
    if type(revision) is not int or revision != BOOTSTRAP_REVISION:
        raise RuntimeError("Fuseki bootstrap marker revision does not match this package")
    phase = marker.get("phase")
    if (
        not isinstance(phase, str)
        or phase not in {"initializing", "complete", "existing-data-preserved"}
    ):
        raise RuntimeError("Fuseki bootstrap marker has an invalid phase")
    return phase


def _dataset_has_data(dataset_url: str) -> bool:
    """Detect any existing triple before initializing an unmarked store."""

    query = (
        "ASK { { ?subject ?predicate ?object } "
        "UNION { GRAPH ?graph { ?subject ?predicate ?object } } }"
    )
    query_url = f"{dataset_url.rstrip('/')}/query?{urllib.parse.urlencode({'query': query})}"
    request = urllib.request.Request(
        query_url,
        headers={"Accept": "application/sparql-results+json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        if not 200 <= response.status < 300:
            raise RuntimeError(f"Fuseki returned HTTP {response.status}")
        try:
            result = json.loads(response.read())
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise RuntimeError("Fuseki data-presence probe returned invalid JSON") from error
    if not isinstance(result, dict) or not isinstance(result.get("boolean"), bool):
        raise RuntimeError("Fuseki data-presence probe returned an invalid result")
    return result["boolean"]


def _write_bootstrap_marker(marker_path: Path, phase: str) -> None:
    """Atomically record the current initialization phase."""

    temporary_path: Path | None = None
    try:
        marker_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=marker_path.parent,
            prefix=f".{marker_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as marker_file:
            temporary_path = Path(marker_file.name)
            json.dump(
                {
                    "schemaVersion": 1,
                    "bootstrapRevision": BOOTSTRAP_REVISION,
                    "phase": phase,
                },
                marker_file,
                separators=(",", ":"),
            )
            marker_file.write("\n")
        temporary_path.replace(marker_path)
    except OSError as error:
        raise RuntimeError("Fuseki bootstrap state could not be recorded") from error
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, urllib.error.URLError) as error:
        print(f"Fuseki ontology bootstrap failed: {error}", file=sys.stderr)
        raise SystemExit(1)
