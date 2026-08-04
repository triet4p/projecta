#!/usr/bin/env python3
"""Load only the deterministic M4 fixture into its named project graphs."""

from __future__ import annotations

import os
import urllib.parse
import urllib.request
from pathlib import Path

import rdflib


def main() -> int:
    dataset = rdflib.Dataset()
    dataset.parse(Path(os.environ.get("ONTOLOGY_DIRECTORY", "/data")) / "examples" / "m4-retrieval-demo.trig", format="trig")
    base = os.environ.get("FUSEKI_DATASET_URL", "http://fuseki:3030/projecta").rstrip("/") + "/data"
    for graph in dataset.graphs():
        if not graph:
            continue
        identifier = str(graph.identifier)
        if not identifier.startswith("https://w3id.org/projecta/data/project/ecommerce-checkout/"):
            continue
        payload = graph.serialize(format="turtle").encode("utf-8")
        url = base + "?" + urllib.parse.urlencode({"graph": identifier})
        request = urllib.request.Request(url, data=payload, method="PUT", headers={"Content-Type": "text/turtle"})
        with urllib.request.urlopen(request, timeout=30) as response:
            if not 200 <= response.status < 300:
                raise RuntimeError(f"Fuseki fixture load failed: HTTP {response.status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
