import { describe, expect, it, vi } from "vitest";

import { ApiError, ProjectaApiClient } from "./client";

describe("ProjectaApiClient", () => {
  it("adds request and idempotency headers to mutations", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ requestId: "req-1", candidates: [], note: { id: "note-1" } }), {
        status: 201,
        headers: { "content-type": "application/json", "X-Request-Id": "req-1" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await new ProjectaApiClient().extractQuickNote({ rawText: "hello" }, "operation-1");

    const request = fetchMock.mock.calls[0][1] as RequestInit;
    expect(new Headers(request.headers).get("Idempotency-Key")).toBe("operation-1");
    expect(new Headers(request.headers).get("X-Request-Id")).toMatch(/^[-a-z0-9]+$/i);
    expect(new Headers(request.headers).get("X-Operation-Id")).toMatch(/^[-a-z0-9]+$/i);
    vi.unstubAllGlobals();
  });

  it("maps RFC 7807 responses to ApiError", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ code: "INVALID_REQUEST", detail: "safe" }), {
          status: 400,
          headers: { "content-type": "application/problem+json", "X-Request-Id": "req-error" },
        }),
      ),
    );

    await expect(new ProjectaApiClient().getLiveness()).rejects.toBeInstanceOf(ApiError);
    vi.unstubAllGlobals();
  });

  it("rejects non-JSON and malformed success responses explicitly", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(
          new Response("upstream html", {
            status: 200,
            headers: { "content-type": "text/html", "X-Request-Id": "req-html" },
          }),
        )
        .mockResolvedValueOnce(
          new Response(JSON.stringify({ status: "not-live" }), {
            status: 200,
            headers: { "content-type": "application/json", "X-Request-Id": "req-bad" },
          }),
        ),
    );

    await expect(new ProjectaApiClient().getLiveness()).rejects.toMatchObject({
      problem: { code: "CLIENT_RESPONSE_INVALID" },
    });
    await expect(new ProjectaApiClient().getLiveness()).rejects.toMatchObject({
      problem: { code: "CLIENT_RESPONSE_INVALID" },
    });
    vi.unstubAllGlobals();
  });

  it("does not confuse the graph evidence filter with an evidence endpoint", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(async (_input: RequestInfo | URL, init?: RequestInit) => {
        const requestId = new Headers(init?.headers).get("X-Request-Id") ?? "req-graph";
        return new Response(JSON.stringify({ requestId, nodes: [], edges: [], stale: false }), {
          status: 200,
          headers: { "content-type": "application/json", "X-Request-Id": requestId },
        });
      }),
    );

    await expect(new ProjectaApiClient().getProjectGraph("project-h-alpha")).resolves.toMatchObject(
      {
        nodes: [],
        edges: [],
        stale: false,
      },
    );
    vi.unstubAllGlobals();
  });
});
