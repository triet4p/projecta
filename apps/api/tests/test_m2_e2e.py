"""Real HTTP acceptance test for the M2 Manual Quick Note lifecycle."""

import os
from uuid import uuid4

import httpx
import pytest


@pytest.mark.asyncio
async def test_manual_quick_note_lifecycle_over_real_http() -> None:
    """Capture, review, and read one project-scoped note without an inference step."""
    base_url = os.environ.get("PROJECTA_API_HTTP_URL")
    if not base_url:
        pytest.skip("real API runtime is only required in the Compose system suite")

    suffix = uuid4().hex[:10]
    project_id = f"m2-{suffix}"
    capture_key = f"capture-{suffix}"
    headers = {
        "X-Projecta-Project-Id": project_id,
        "X-Projecta-Actor-Id": "le",
        "X-Projecta-Context-Secret": os.environ.get(
            "PROJECTA_API_CONTEXT_SECRET", "system-test-context-secret"
        ),
        "X-Request-Id": f"req-{suffix}",
        "Idempotency-Key": capture_key,
    }
    body = {
        "rawText": "Confirm address. Tax timeout.",
        "segments": [
            {"type": "requirement", "startOffset": 0, "endOffset": 16, "text": "Confirm address."},
            {"type": "risk", "startOffset": 17, "endOffset": 29, "text": "Tax timeout."},
        ],
    }

    async with httpx.AsyncClient(base_url=base_url, timeout=15.0) as client:
        captured = await client.post("/v1/quick-notes", headers=headers, json=body)
        assert captured.status_code == 201, captured.text
        capture = captured.json()
        assert capture["requestId"] == headers["X-Request-Id"]
        assert len(capture["candidates"]) == 2

        replay = await client.post("/v1/quick-notes", headers=headers, json=body)
        assert replay.status_code == 200, replay.text
        assert replay.json() == capture

        requirement_id = capture["candidates"][0]["id"]
        risk_id = capture["candidates"][1]["id"]
        for candidate_id in (requirement_id, risk_id):
            validated = await client.post(f"/v1/candidates/{candidate_id}/validations", headers=headers)
            assert validated.status_code == 200, validated.text
            assert validated.json()["conforms"] is True

        wrong_type_confirmation = await client.post(
            f"/v1/candidates/{risk_id}/confirmations",
            headers=headers | {"Idempotency-Key": f"wrong-type-{suffix}"},
            json={
                "assertion": {
                    "type": "Requirement",
                    "label": "Risk must not become a requirement",
                    "validFrom": "2026-07-31",
                }
            },
        )
        assert wrong_type_confirmation.status_code == 409, wrong_type_confirmation.text

        confirmed = await client.post(
            f"/v1/candidates/{requirement_id}/confirmations",
            headers=headers | {"Idempotency-Key": f"confirm-{suffix}"},
            json={
                "assertion": {
                    "type": "Requirement",
                    "label": "Confirm address",
                    "validFrom": "2026-07-31",
                }
            },
        )
        assert confirmed.status_code == 201, confirmed.text
        asserted_id = confirmed.json()["assertedItemId"]
        assert "/" not in asserted_id

        rejected = await client.post(
            f"/v1/candidates/{risk_id}/rejections",
            headers=headers | {"Idempotency-Key": f"reject-{suffix}"},
            json={"reason": "Tracked as an operational risk, not a requirement."},
        )
        assert rejected.status_code == 201, rejected.text

        current = await client.get("/v1/knowledge-items/current?type=Requirement", headers=headers)
        assert current.status_code == 200 and current.json()["items"], current.text
        evidence = await client.get(f"/v1/knowledge-items/{asserted_id}/evidence", headers=headers)
        assert evidence.status_code == 200 and evidence.json()["items"], evidence.text
        chain = evidence.json()["items"][0]
        assert chain["sourceText"] == "Confirm address."
        assert chain["startOffset"] == "0"
        assert chain["endOffset"] == "16"
        history = await client.get(f"/v1/candidates/{risk_id}/history", headers=headers)
        assert history.status_code == 200 and history.json()["items"], history.text
