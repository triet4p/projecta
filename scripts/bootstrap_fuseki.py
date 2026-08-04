#!/usr/bin/env python3
"""Idempotently load Projecta's local M2 ontology draft through Fuseki HTTP."""

from __future__ import annotations

import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path


ONTOLOGY_GRAPH = "https://w3id.org/projecta/data/ontology/dev/"
MODULES = ("core.ttl", "communication.ttl", "provenance.ttl", "temporal.ttl", "evidence.ttl", "llm-extraction-v04.ttl", "m4-retrieval.ttl", "rules/m4-rules.ttl")


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

    print(f"Loaded {len(MODULES)} local ontology modules into {ONTOLOGY_GRAPH}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, urllib.error.URLError) as error:
        print(f"Fuseki ontology bootstrap failed: {error}", file=sys.stderr)
        raise SystemExit(1)
