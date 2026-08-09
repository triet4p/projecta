#!/usr/bin/env python3
"""Idempotently load Projecta's local M2 ontology draft through Fuseki HTTP."""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ONTOLOGY_GRAPH = "https://w3id.org/projecta/data/ontology/dev/"
MODULES = ("core.ttl", "communication.ttl", "provenance.ttl", "temporal.ttl", "evidence.ttl", "llm-extraction-v04.ttl", "m4-retrieval.ttl", "rules/m4-rules.ttl")
PROJECT_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")


def main() -> int:
    ontology_dir = Path(os.environ.get("ONTOLOGY_DIRECTORY", "/data"))
    dataset_url = os.environ.get("FUSEKI_DATASET_URL", "http://fuseki:3030/projecta")
    graph_url = f"{dataset_url.rstrip('/')}/data?{urllib.parse.urlencode({'graph': ONTOLOGY_GRAPH})}"
    payload = "\n\n".join((ontology_dir / module).read_text(encoding="utf-8") for module in MODULES)

    request = urllib.request.Request(
        graph_url,
        data=payload.encode("utf-8"),
        method="PUT",
        headers={"Content-Type": "text/turtle; charset=utf-8"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        if not 200 <= response.status < 300:
            raise RuntimeError(f"Fuseki returned HTTP {response.status}")

    print(f"Loaded {len(MODULES)} local ontology modules into the configured ontology graph")
    seeded = _seed_acceptance_projects(dataset_url)
    if seeded:
        print(f"Loaded {seeded} explicitly configured acceptance projects")
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
            method="PUT",
            headers={"Content-Type": "text/turtle; charset=utf-8"},
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            if not 200 <= response.status < 300:
                raise RuntimeError(f"Fuseki returned HTTP {response.status}")
    return len(entries)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, urllib.error.URLError) as error:
        print(f"Fuseki ontology bootstrap failed: {error}", file=sys.stderr)
        raise SystemExit(1)
