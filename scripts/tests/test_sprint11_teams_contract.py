"""Repository contracts for the read-only Teams adapter slice."""

import json
from pathlib import Path


def root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_teams_adapter_uses_approved_permission_and_fixed_graph_boundary() -> None:
    contract = (root() / "docs/architecture/teams-provider-contract.md").read_text(encoding="utf-8")
    adapter = (root() / "apps/api/src/projecta_api/connectors/teams.py").read_text(encoding="utf-8")
    assert "ChannelMessage.Read.Group" in contract
    assert "ChannelMessage.Read.All" in contract
    assert "graph.microsoft.com" in adapter
    assert "follow_redirects=False" in adapter
    assert "login.microsoftonline.com" in (root() / "apps/api/src/projecta_api/connectors/teams_auth.py").read_text(encoding="utf-8")
    assert "ChannelMessage.Read.All" not in adapter


def test_teams_bounds_and_internal_provider_config_are_explicit() -> None:
    adapter = (root() / "apps/api/src/projecta_api/connectors/teams.py").read_text(encoding="utf-8")
    for marker in ("$top\": \"50\"", "max_replies_per_root", "max_replies_total", "max_run_bytes", "max_event_bytes", "truncated"):
        assert marker in adapter
    assert "provider_config" in adapter
    assert "teams://message/" in adapter
    assert "parentReference" in adapter


def test_sanitized_replay_fixtures_are_bounded_and_provider_scoped() -> None:
    fixture_dir = root() / "evaluation/sprint-11/teams"
    root_page = json.loads((fixture_dir / "root-page.json").read_text(encoding="utf-8"))
    replies = json.loads((fixture_dir / "replies-root-1.json").read_text(encoding="utf-8"))
    assert len(root_page["value"]) <= 50
    assert len(replies["value"]) <= 10
    assert "access_token" not in json.dumps(root_page)
    assert "privateKeyPem" not in json.dumps(replies)
