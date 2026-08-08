"""Compare the committed frontend snapshot with the backend's public paths."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "apps" / "api" / "src"))
os.environ.setdefault("PROJECTA_LLM_TYPE", "openai-response")
os.environ.setdefault("PROJECTA_LLM_BASE_URL", "https://provider.example")
os.environ.setdefault("PROJECTA_LLM_API_KEY", "contract-test-not-a-secret")
os.environ.setdefault("PROJECTA_LLM_MODEL", "contract-test-model")

from projecta_api.main import app

SNAPSHOT = ROOT / "docs" / "architecture" / "application-api.sprint7.openapi.json"
INTERNAL_PATHS = {"/v1/entities/link-context"}
FORBIDDEN_FIELDS = {"_projecta_http_status", "secretReference", "X-Projecta-Context-Secret", "apiKey"}


def main() -> int:
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    snapshot_paths = set(snapshot["paths"])
    backend_paths = {
        re.sub(r"{([^}]+)}", lambda match: "{" + _camel_case(match.group(1)) + "}", path)
        for path in app.openapi()["paths"]
    } - INTERNAL_PATHS
    if snapshot_paths != backend_paths:
        print(f"API path drift: snapshot={sorted(snapshot_paths)} backend={sorted(backend_paths)}")
        return 1
    serialized = json.dumps(snapshot, sort_keys=True)
    leaked = sorted(field for field in FORBIDDEN_FIELDS if field in serialized)
    if leaked:
        print(f"Forbidden internal fields in API snapshot: {leaked}")
        return 1
    print(f"API snapshot matches {len(backend_paths)} public paths")
    return 0


def _camel_case(value: str) -> str:
    parts = value.split("_")
    return parts[0] + "".join(part.title() for part in parts[1:])


if __name__ == "__main__":
    raise SystemExit(main())
