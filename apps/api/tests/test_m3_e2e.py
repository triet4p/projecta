"""Opt-in real HTTP M3 acceptance tests; canonical unit CI stays offline."""

import os
from uuid import uuid4

import httpx
import pytest


@pytest.mark.asyncio
async def test_m3_untyped_note_abstention_and_project_negative_over_http() -> None:
    base_url = os.environ.get("PROJECTA_API_HTTP_URL")
    if not base_url or os.environ.get("PROJECTA_M3_E2E") != "1":
        pytest.skip("M3 HTTP evaluation requires explicit PROJECTA_M3_E2E=1")

    suffix = uuid4().hex[:10]
    headers = {
        "X-Projecta-Project-Id": f"m3-{suffix}",
        "X-Projecta-Actor-Id": "le",
        "X-Projecta-Context-Secret": os.environ.get("PROJECTA_API_CONTEXT_SECRET", "system-test-context-secret"),
        "X-Request-Id": f"req-{suffix}",
        "Idempotency-Key": f"extract-{suffix}",
    }
    body = {"rawText": "Confirm the shipping address before payment.", "extractionVersion": "m3.v1"}

    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:
        response = await client.post("/v1/quick-notes/extractions", headers=headers, json=body)
        assert response.status_code in {200, 201}, response.text
        payload = response.json()
        assert payload["candidates"], "configured live extraction must produce a lifecycle-test candidate"
        assert payload["note"]["id"]

        replay = await client.post("/v1/quick-notes/extractions", headers=headers, json=body)
        assert replay.status_code == 200, replay.text
        assert replay.json()["note"]["id"] == payload["note"]["id"]

        candidate_id = payload["candidates"][0]["id"]
        validation = await client.post(f"/v1/candidates/{candidate_id}/validations", headers=headers)
        assert validation.status_code == 200, validation.text
        rejection_headers = headers | {"Idempotency-Key": f"reject-{suffix}"}
        rejected = await client.post(
            f"/v1/candidates/{candidate_id}/rejections",
            headers=rejection_headers,
            json={"reason": "M3 lifecycle integration test"},
        )
        assert rejected.status_code in {200, 201}, rejected.text
        history = await client.get(f"/v1/candidates/{candidate_id}/history", headers=headers)
        assert history.status_code == 200, history.text
        assert history.json()["items"]

        other_headers = headers | {
            "X-Projecta-Project-Id": f"other-{suffix}",
            "X-Request-Id": f"other-req-{suffix}",
            "Idempotency-Key": f"other-extract-{suffix}",
        }
        context = await client.get("/v1/entities/link-context", headers=other_headers)
        assert context.status_code == 200, context.text
        assert all("--" in item["id"] for item in context.json()["entities"])
