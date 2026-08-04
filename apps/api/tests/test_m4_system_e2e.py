"""Real Compose HTTP M4 acceptance test; skipped outside the system suite."""

import os

import httpx
import pytest


@pytest.mark.asyncio
async def test_m4_real_http_history_blocker_and_rebuild() -> None:
    base_url = os.environ.get("PROJECTA_API_HTTP_URL")
    if not base_url:
        pytest.skip("real API runtime is only required in the Compose system suite")
    headers = {
        "X-Projecta-Project-Id": "ecommerce-checkout",
        "X-Projecta-Actor-Id": "le",
        "X-Projecta-Context-Secret": os.environ.get("PROJECTA_API_CONTEXT_SECRET", "system-test-context-secret"),
        "X-Request-Id": "m4-real-e2e",
    }
    async with httpx.AsyncClient(base_url=base_url, timeout=20.0) as client:
        rebuilt = await client.post("/v1/project-context/inference/rebuild", headers=headers)
        assert rebuilt.status_code == 200, rebuilt.text
        assert rebuilt.json()["materializedRuleIds"] == [
            "m4.delivery-risk", "m4.impact-review", "m4.unresolved-dependency"
        ]
        rebuilt_again = await client.post("/v1/project-context/inference/rebuild", headers=headers)
        assert rebuilt_again.status_code == 200, rebuilt_again.text
        assert rebuilt_again.json()["sourceRevision"] == rebuilt.json()["sourceRevision"]
        assert rebuilt_again.json()["materializationRevision"] == rebuilt.json()["materializationRevision"]
        history = await client.post("/v1/project-context/answers", headers=headers, json={"question": "What changed in requirement req-new?"})
        assert history.status_code == 200, history.text
        assert len(history.json()["facts"]) == 2
        assert history.json()["citations"]
        blockers = await client.post("/v1/project-context/answers", headers=headers, json={"question": "What is blocking checkout?"})
        assert blockers.status_code == 200, blockers.text
        assert blockers.json()["facts"][0]["status"] == "inferred"
        assert blockers.json()["facts"][0]["derivation"]["ruleId"] == "m4.unresolved-dependency"
