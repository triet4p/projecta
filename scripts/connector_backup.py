"""Explicit connector PostgreSQL/evidence backup and isolated restore tool.

The command never places a database password in argv. Restore requires an
explicit isolated target directory and confirmation so it cannot mutate a
shared deployment accidentally.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tarfile
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import unquote, urlparse

BACKUP_VERSION = "connector-backup.v1"


def _database_args(database_url: str, password: str) -> tuple[list[str], dict[str, str]]:
    parsed = urlparse(database_url)
    if parsed.scheme not in {"postgresql", "postgresql+psycopg"} or not parsed.hostname:
        raise ValueError("database configuration is invalid")
    env = os.environ.copy()
    env["PGPASSWORD"] = password
    args = [
        "--host", parsed.hostname,
        "--port", str(parsed.port or 5432),
        "--username", unquote(parsed.username or ""),
        "--dbname", (parsed.path or "/").lstrip("/"),
    ]
    return args, env


def _run_postgres_tool(
    tool: str,
    args: list[str],
    env: dict[str, str],
    *,
    mounted_file: Path,
) -> None:
    """Run a local PostgreSQL client or an explicitly configured containerized one."""
    if shutil.which(tool) is not None:
        subprocess.run([tool, *args], check=True, env=env)
        return

    image = os.environ.get("PROJECTA_CONNECTOR_BACKUP_TOOL_IMAGE", "")
    if not image:
        raise FileNotFoundError(f"{tool} is unavailable and no backup tool image is configured")
    mount_root = mounted_file.resolve().parent
    container_file = f"/backup/{mounted_file.name}"
    translated = list(args)
    for index, value in enumerate(translated):
        if value in {"127.0.0.1", "localhost"}:
            translated[index] = "host.docker.internal"
        elif value == str(mounted_file):
            translated[index] = container_file
    subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--volume",
            f"{mount_root}:/backup",
            "--env",
            "PGPASSWORD",
            image,
            tool,
            *translated,
        ],
        check=True,
        env=env,
    )


def create_backup(
    output: Path,
    database_url: str,
    database_password: str,
    evidence_root: Path,
    *,
    confirm_quiesced: bool,
) -> Path:
    if not confirm_quiesced:
        raise ValueError("backup requires a quiesced connector write boundary")
    if output.exists():
        raise ValueError("backup directory already exists")
    if not evidence_root.is_dir():
        raise ValueError("evidence root is unavailable")
    output.mkdir(parents=True)
    dump = output / "connector-postgres.dump"
    archive = output / "connector-evidence.tar"
    args, env = _database_args(database_url, database_password)
    _run_postgres_tool(
        "pg_dump", [*args, "--format=custom", "--file", str(dump)], env, mounted_file=dump
    )
    with tarfile.open(archive, "w") as handle:
        handle.add(evidence_root, arcname="evidence", recursive=True, filter=_safe_tar_info)
    manifest = {
        "backupVersion": BACKUP_VERSION,
        "createdAt": datetime.now(UTC).isoformat(),
        "databaseDump": dump.name,
        "evidenceArchive": archive.name,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output / "manifest.json"


def restore_backup(backup: Path, isolated_root: Path, database_url: str, database_password: str, confirm_isolated: bool) -> None:
    if not confirm_isolated:
        raise ValueError("restore requires --confirm-isolated")
    manifest = json.loads((backup / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("backupVersion") != BACKUP_VERSION:
        raise ValueError("backup version is unsupported")
    if isolated_root.resolve() == backup.resolve() or backup.resolve() in isolated_root.resolve().parents:
        raise ValueError("isolated restore target is unsafe")
    isolated_root.mkdir(parents=True, exist_ok=True)
    archive = backup / str(manifest["evidenceArchive"])
    with tarfile.open(archive, "r") as handle:
        handle.extractall(isolated_root, filter="data")
    dump = backup / str(manifest["databaseDump"])
    args, env = _database_args(database_url, database_password)
    _run_postgres_tool(
        "pg_restore", [*args, "--clean", "--if-exists", str(dump)], env, mounted_file=dump
    )


def _safe_tar_info(info: tarfile.TarInfo) -> tarfile.TarInfo:
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    return info


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Connector backup/isolated restore")
    sub = parser.add_subparsers(dest="command", required=True)
    backup = sub.add_parser("backup")
    backup.add_argument("--output", type=Path, required=True)
    backup.add_argument("--evidence-root", type=Path, required=True)
    backup.add_argument("--confirm-quiesced", action="store_true")
    restore = sub.add_parser("restore")
    restore.add_argument("--backup", type=Path, required=True)
    restore.add_argument("--isolated-root", type=Path, required=True)
    restore.add_argument("--confirm-isolated", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "backup":
            print(
                create_backup(
                    args.output,
                    _env("PROJECTA_CONNECTOR_BACKUP_DATABASE_URL"),
                    _env("PROJECTA_CONNECTOR_BACKUP_DATABASE_PASSWORD"),
                    args.evidence_root,
                    confirm_quiesced=args.confirm_quiesced,
                )
            )
        else:
            restore_backup(args.backup, args.isolated_root, _env("PROJECTA_CONNECTOR_BACKUP_DATABASE_URL"), _env("PROJECTA_CONNECTOR_BACKUP_DATABASE_PASSWORD"), args.confirm_isolated)
    except (OSError, ValueError, subprocess.SubprocessError, tarfile.TarError) as error:
        print(f"connector backup failed: {type(error).__name__}", file=sys.stderr)
        return 1
    return 0


def _env(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise ValueError(f"{name} is not configured")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
