"""Static repository contract gate for the Sprint 10 connector boundary."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def _method_block(source: str, method: str) -> str:
    match = re.search(
        rf"^    def {re.escape(method)}\b[\s\S]*?(?=^    def |\Z)", source, re.MULTILINE
    )
    if match is None:
        raise AssertionError(f"repository method is missing: {method}")
    return match.group(0)


def validate(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    public_api = (
        root / "apps/api/src/projecta_api/connectors/public_api.py"
    ).read_text(encoding="utf-8")
    web_files = [
        root / "apps/web/src/screens/ConnectionsScreen.tsx",
        root / "apps/web/src/connections-state.ts",
        root / "apps/web/src/api/client.ts",
        root / "apps/web/src/api/generated.ts",
    ]
    web = "\n".join(path.read_text(encoding="utf-8") for path in web_files)
    runtime_files = list((root / "apps/api/src/projecta_api/connectors").rglob("*.py"))
    runtime_files += list(
        (root / "apps/api/src/projecta_api/operational").rglob("*.py")
    )
    runtime = "\n".join(path.read_text(encoding="utf-8") for path in runtime_files)
    repository = (
        root / "apps/api/src/projecta_api/operational/repository.py"
    ).read_text(encoding="utf-8")
    main = (root / "apps/api/src/projecta_api/main.py").read_text(encoding="utf-8")

    for pattern, description in (
        (r"local-project|local-user", "authority-bearing local default"),
        (r"setdefault\(", "implicit authority default"),
        (r"max_retries\s*=\s*[1-9]", "hidden automatic retry"),
    ):
        if re.search(pattern, runtime + main):
            errors.append(description)

    for field in (
        "secretReference",
        "storagePath",
        "filesystemPath",
        "rawPayload",
        "graphIri",
    ):
        if field in public_api:
            errors.append(f"raw/internal public connector field: {field}")
    for field in (
        "X-Projecta-Context-Secret",
        "secretReference",
        "postgresql://",
        "SPARQL",
    ):
        if field in web:
            errors.append(f"browser connector authority or storage detail: {field}")

    for term in ("rdflib", "from rdflib", "import rdflib", "SPARQL", "tdb2", "fuseki"):
        if term in runtime:
            errors.append(
                f"connector operational state crossed into semantic storage: {term}"
            )

    if "le=100" not in public_api or "limit=limit" not in public_api:
        errors.append("public connector collection limits are not explicit")
    if "min(limit, 100)" not in repository or "min(offset, 10_000)" not in repository:
        errors.append("repository connector collection limits are not bounded")
    if 'mode="interactive-single-attempt"' not in main or "max_retries=0" not in main:
        errors.append("interactive provider retry policy is not explicit")

    for method in (
        "get_installation",
        "list_installations",
        "upsert_installation",
        "claim_event",
        "complete_event",
        "get_cursor",
        "start_run",
        "finish_run",
        "get_run",
        "list_runs",
        "record_dead_letter",
        "record_audit",
        "list_audit",
    ):
        block = _method_block(repository, method)
        if "project_id" not in block:
            errors.append(f"missing project predicate in {method}")

    return errors


def main() -> int:
    errors = validate()
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print(
        "Sprint 10 repository contract passed: bounded, project-scoped, opaque, and non-semantic operational state."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
