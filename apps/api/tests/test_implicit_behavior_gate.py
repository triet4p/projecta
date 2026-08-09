from pathlib import Path

import pytest

pytestmark = pytest.mark.local_contract


def test_interactive_composition_declares_single_attempt() -> None:
    source = (Path(__file__).parents[1] / "src/projecta_api/main.py").read_text(encoding="utf-8")

    assert 'mode="interactive-single-attempt"' in source
    assert "max_retries=0" in source


def test_web_client_has_no_empty_json_fallback() -> None:
    source = (Path(__file__).parents[2] / "web/src/api/client.ts").read_text(encoding="utf-8")

    assert "response.json().catch(() => ({}))" not in source
