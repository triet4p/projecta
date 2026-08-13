"""Run the non-destructive part of the Sprint 11 cold-recovery contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sprint11_backup import restore_bundle


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sprint 11 cold recovery drill")
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--isolated-root", type=Path, required=True)
    parser.add_argument("--manual-unseal-confirmed", action="store_true")
    parser.add_argument("--sessions-invalidated", action="store_true")
    parser.add_argument("--workload-reauthenticated", action="store_true")
    args = parser.parse_args(argv)
    if not (args.manual_unseal_confirmed and args.sessions_invalidated and args.workload_reauthenticated):
        parser.error("manual unseal, session invalidation, and workload re-authentication must be confirmed")
    contract = restore_bundle(args.bundle, args.isolated_root, confirm_isolated=True)
    evidence = {
        "schemaVersion": "sprint11.cold-recovery.v1",
        "status": "restored-isolated",
        "manualUnseal": True,
        "sessionsInvalidated": True,
        "workloadReauthenticated": True,
        "replayMustRemainIdempotent": True,
        "contractFile": contract.name,
    }
    print(json.dumps(evidence, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
