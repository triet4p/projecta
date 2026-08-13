from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_phase_e_runbooks_and_safe_public_api_exist() -> None:
    runbooks = [
        ROOT / "docs/runbooks/identity-secret-operator-sprint-11.md",
        ROOT / "docs/runbooks/teams-administrator-sprint-11.md",
    ]
    for path in runbooks:
        text = path.read_text(encoding="utf-8")
        assert "OpenBao" in text
        assert "secret" in text.lower()
    ui = (ROOT / "apps/web/src/screens/ConnectionsScreen.tsx").read_text(encoding="utf-8")
    assert "teamsSetupHandle" in ui
    assert "Review Queue" in ui and "Knowledge" in ui
    assert "tenantId" not in ui and "channelId" not in ui and "secretReference" not in ui
