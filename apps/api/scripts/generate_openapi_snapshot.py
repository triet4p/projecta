"""Regenerate the redacted public Application API snapshot for Sprint 8."""

from __future__ import annotations

import copy
import json
import re
import sys
from importlib import import_module
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "apps" / "api" / "src"))

app = import_module("projecta_api.main").app


SNAPSHOT = ROOT / "docs" / "architecture" / "application-api.sprint7.openapi.json"
INTERNAL_PATHS = {"/v1/entities/link-context"}
FORBIDDEN_HEADER = "X-Projecta-Context-Secret"
OPERATION_IDS = {
    ("/v1/projects/{handle}/notes/drafts", "post"): "createNoteDraft",
    ("/v1/projects/{handle}/notes/drafts/{draftHandle}", "get"): "readNoteDraft",
    ("/v1/projects/{handle}/notes/drafts/{draftHandle}", "put"): "updateNoteDraft",
    ("/v1/projects/{handle}/notes/drafts/{draftHandle}/commit", "post"): "commitNoteDraft",
    ("/v1/projects/{handle}/notes", "get"): "listStructuredNotes",
    ("/v1/projects/{handle}/notes/{noteHandle}", "get"): "readStructuredNote",
    ("/v1/projects/{handle}/notes/import", "post"): "importNoteText",
    ("/v1/projects/{handle}/candidates/{candidateHandle}/edits", "post"):
        "editStructuredCandidate",
}


def camel_path(path: str) -> str:
    return re.sub(
        r"{([^}]+)}",
        lambda match: "{" + _camel_case(match.group(1)) + "}",
        path,
    )


def _camel_case(value: str) -> str:
    parts = value.split("_")
    return parts[0] + "".join(part.title() for part in parts[1:])


def redact_operation(operation: dict[str, object], path: str, method: str) -> dict[str, object]:
    redacted = copy.deepcopy(operation)
    parameters = redacted.get("parameters")
    if isinstance(parameters, list):
        redacted["parameters"] = [
            parameter
            for parameter in parameters
            if parameter.get("name") != FORBIDDEN_HEADER
        ]
    redacted["operationId"] = OPERATION_IDS.get((path, method), redacted.get("operationId"))
    return redacted


def main() -> None:
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    backend = app.openapi()
    for raw_path, raw_operations in backend["paths"].items():
        if raw_path in INTERNAL_PATHS:
            continue
        path = camel_path(raw_path)
        if path in snapshot["paths"]:
            continue
        snapshot["paths"][path] = {
            method: redact_operation(operation, path, method)
            for method, operation in raw_operations.items()
            if method in {"get", "post", "put", "patch", "delete"}
        }

    components = snapshot.setdefault("components", {})
    schemas = components.setdefault("schemas", {})
    for name, schema in backend.get("components", {}).get("schemas", {}).items():
        if name not in schemas:
            schemas[name] = schema

    snapshot["info"]["title"] = "Projecta Application API — Sprint 8 Frontend Contract"
    snapshot["info"]["version"] = "s8.0"
    snapshot["info"]["description"] = (
        "Redacted browser-facing Application API contract for Sprint 8. "
        "The snapshot exposes only finite project, graph, candidate, Note, Q&A, "
        "health, and configuration boundary contracts."
    )
    serialized = json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n"
    forbidden = {"_projecta_http_status", "secretReference", FORBIDDEN_HEADER, "apiKey"}
    leaked = sorted(field for field in forbidden if field in serialized)
    if leaked:
        raise SystemExit(f"Snapshot contains forbidden internal fields: {leaked}")
    SNAPSHOT.write_text(serialized, encoding="utf-8")


if __name__ == "__main__":
    main()
