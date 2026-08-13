"""Create and restore an isolated Sprint 11 state bundle.

The bundle coordinates connector PostgreSQL, evidence, Keycloak export, and an
already-encrypted OpenBao snapshot. It never reads or writes plaintext secret
material and refuses to restore into the bundle itself or a parent directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tarfile
from datetime import UTC, datetime
from pathlib import Path

BACKUP_VERSION = "sprint11-state-bundle.v1"


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _require_file(path: Path, label: str) -> Path:
    if not path.is_file():
        raise ValueError(f"{label} is unavailable")
    return path


def create_bundle(
    output: Path,
    *,
    postgres_dump: Path,
    evidence_root: Path,
    keycloak_export: Path,
    openbao_snapshot: Path,
    confirm_quiesced: bool,
) -> Path:
    if not confirm_quiesced:
        raise ValueError("state bundle requires a quiesced write boundary")
    if output.exists():
        raise ValueError("state bundle output already exists")
    for path, label in (
        (postgres_dump, "PostgreSQL dump"),
        (keycloak_export, "Keycloak export"),
        (openbao_snapshot, "OpenBao snapshot"),
    ):
        _require_file(path, label)
    if not evidence_root.is_dir():
        raise ValueError("evidence root is unavailable")
    if openbao_snapshot.suffix != ".enc":
        raise ValueError("OpenBao snapshot must be encrypted (.enc)")

    output.mkdir(parents=True)
    files: dict[str, dict[str, str]] = {}
    for source, name in (
        (postgres_dump, "connector-postgres.dump"),
        (keycloak_export, "keycloak-export.json"),
        (openbao_snapshot, "openbao-snapshot.enc"),
    ):
        target = output / name
        shutil.copy2(source, target)
        files[name] = {"sha256": _digest(target), "kind": name.split(".")[0]}

    evidence_archive = output / "evidence.tar"
    with tarfile.open(evidence_archive, "w") as archive:
        archive.add(evidence_root, arcname="evidence", recursive=True)
    files[evidence_archive.name] = {"sha256": _digest(evidence_archive), "kind": "evidence"}

    manifest = {
        "backupVersion": BACKUP_VERSION,
        "createdAt": datetime.now(UTC).isoformat(),
        "quiesced": True,
        "files": files,
        "restoreContract": {
            "manualUnsealRequired": True,
            "workloadReauthenticationRequired": True,
            "invalidateProjectaSessions": True,
            "rpoHours": 24,
            "rtoMinutes": 60,
        },
    }
    manifest_path = output / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest_path


def restore_bundle(bundle: Path, isolated_root: Path, *, confirm_isolated: bool) -> Path:
    if not confirm_isolated:
        raise ValueError("restore requires --confirm-isolated")
    bundle = bundle.resolve()
    isolated_root = isolated_root.resolve()
    if not bundle.is_dir() or isolated_root == bundle or bundle in isolated_root.parents:
        raise ValueError("isolated restore target is unsafe")
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("backupVersion") != BACKUP_VERSION or manifest.get("quiesced") is not True:
        raise ValueError("state bundle contract is unsupported")
    isolated_root.mkdir(parents=True, exist_ok=True)
    files = manifest.get("files")
    if not isinstance(files, dict):
        raise TypeError("state bundle file manifest is invalid")
    for name, metadata in files.items():
        if not isinstance(name, str) or Path(name).name != name or not isinstance(metadata, dict):
            raise TypeError("state bundle file name is invalid")
        source = _require_file(bundle / name, "state bundle file")
        if metadata.get("sha256") != _digest(source):
            raise ValueError("state bundle digest mismatch")
        target = isolated_root / name
        if name == "evidence.tar":
            with tarfile.open(source, "r") as archive:
                archive.extractall(isolated_root, filter="data")
        else:
            shutil.copy2(source, target)
    (isolated_root / "restore-contract.json").write_text(
        json.dumps(manifest["restoreContract"], indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return isolated_root / "restore-contract.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sprint 11 coordinated state bundle")
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create")
    create.add_argument("--output", type=Path, required=True)
    create.add_argument("--postgres-dump", type=Path, required=True)
    create.add_argument("--evidence-root", type=Path, required=True)
    create.add_argument("--keycloak-export", type=Path, required=True)
    create.add_argument("--openbao-snapshot", type=Path, required=True)
    create.add_argument("--confirm-quiesced", action="store_true")
    restore = sub.add_parser("restore")
    restore.add_argument("--bundle", type=Path, required=True)
    restore.add_argument("--isolated-root", type=Path, required=True)
    restore.add_argument("--confirm-isolated", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "create":
            print(create_bundle(args.output, postgres_dump=args.postgres_dump, evidence_root=args.evidence_root, keycloak_export=args.keycloak_export, openbao_snapshot=args.openbao_snapshot, confirm_quiesced=args.confirm_quiesced))
        else:
            print(restore_bundle(args.bundle, args.isolated_root, confirm_isolated=args.confirm_isolated))
    except (OSError, ValueError, json.JSONDecodeError, tarfile.TarError) as error:
        print(f"sprint11 state bundle failed: {type(error).__name__}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
