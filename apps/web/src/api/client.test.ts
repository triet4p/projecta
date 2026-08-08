import { describe, expect, it, vi } from "vitest";

import { ApiError, ProjectaApiClient } from "./client";

describe("ProjectaApiClient", () => {
  it("adds request and idempotency headers to mutations", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ requestId: "req-1", candidates: [], note: { id: "note-1" } }), {
        status: 201,
        headers: { "content-type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await new ProjectaApiClient().extractQuickNote({ rawText: "hello" }, "operation-1");

    const request = fetchMock.mock.calls[0][1] as RequestInit;
    expect(new Headers(request.headers).get("Idempotency-Key")).toBe("operation-1");
    expect(new Headers(request.headers).get("X-Request-Id")).toMatch(/^[-a-z0-9]+$/i);
    vi.unstubAllGlobals();
  });

  it("maps RFC 7807 responses to ApiError", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ code: "INVALID_REQUEST", detail: "safe" }), {
          status: 400,
          headers: { "content-type": "application/problem+json" },
        }),
      ),
    );

    await expect(new ProjectaApiClient().getLiveness()).rejects.toBeInstanceOf(ApiError);
    vi.unstubAllGlobals();
  });
});
