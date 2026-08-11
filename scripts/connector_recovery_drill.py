"""Verify an isolated connector backup restore without touching shared state."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from connector_backup import BACKUP_VERSION, restore_backup


def verify_evidence(isolated_root: Path) -> int:
    evidence = isolated_root / "evidence"
    references: set[str] = set()
    for metadata in evidence.rglob("metadata.json"):
        payload = json.loads(metadata.read_text(encoding="utf-8"))
        reference = str(payload["evidence_reference"])
        if reference in references:
            raise ValueError("duplicate evidence reference after restore")
        references.add(reference)
    return len(references)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Connector isolated recovery drill")
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--isolated-root", type=Path, required=True)
    parser.add_argument("--confirm-isolated", action="store_true")
    args = parser.parse_args(argv)
    manifest = json.loads((args.backup / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("backupVersion") != BACKUP_VERSION:
        raise SystemExit("unsupported connector backup version")
    # restore_backup reads database URL/password only from environment through
    # its CLI boundary; this drill is intentionally not a shared-stack command.
    from connector_backup import _env

    restore_backup(
        args.backup,
        args.isolated_root,
        _env("PROJECTA_CONNECTOR_BACKUP_DATABASE_URL"),
        _env("PROJECTA_CONNECTOR_BACKUP_DATABASE_PASSWORD"),
        args.confirm_isolated,
    )
    print(f"restored evidence objects: {verify_evidence(args.isolated_root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
