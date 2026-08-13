"""Idempotent operator membership seed; input must remain untracked."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from projecta_api.config import Settings
from projecta_api.identity.repository import PostgresIdentityRepository
from sqlalchemy import create_engine

ALLOWED_ROLES = {"project-reader", "reviewer", "connector-admin"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed additive Projecta project memberships")
    parser.add_argument("path", type=Path, help="untracked JSON file containing memberships")
    args = parser.parse_args()
    payload = json.loads(args.path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise SystemExit("membership seed must be a JSON array")
    repository = PostgresIdentityRepository(create_engine(Settings().identity_sync_database_url(), hide_parameters=True))
    for item in payload:
        if not isinstance(item, dict) or not isinstance(item.get("subject"), str) or not isinstance(item.get("projectId"), str) or not isinstance(item.get("roles"), list):
            raise SystemExit("each membership requires subject, projectId, and roles")
        roles = tuple(item["roles"])
        if not roles or any(role not in ALLOWED_ROLES for role in roles):
            raise SystemExit("membership contains an unsupported role")
        repository.replace_membership(item["subject"], item["projectId"], roles)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
