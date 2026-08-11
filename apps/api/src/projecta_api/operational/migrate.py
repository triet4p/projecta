"""Standalone connector migration entry point.

Application replicas never run this module implicitly. Rollback is performed
from a reviewed backup/restore procedure; ``downgrade`` is not an app command.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from alembic.config import Config

from alembic import command
from projecta_api.config import Settings


def run_upgrade() -> None:
    settings = Settings()
    config = Config(str(Path(__file__).resolve().parents[3] / "alembic.ini"))
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[3] / "alembic"))
    # The URL is resolved inside env.py so credentials never enter Alembic logs.
    settings.connector_sync_database_url()
    command.upgrade(config, "head")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Migrate connector PostgreSQL state")
    parser.add_argument("command", choices=("upgrade",), help="Only forward migration is supported")
    args = parser.parse_args(argv)
    if args.command == "upgrade":
        try:
            run_upgrade()
        except Exception as exc:  # noqa: BLE001 - CLI must fail explicitly and safely.
            print(f"connector migration failed: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
