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
  it("streams portable project files without JSON-encoding their bytes", async () => {
    const fetchMock = vi.fn().mockImplementation(async (_input: RequestInfo | URL, init?: RequestInit) => {
      const requestId = new Headers(init?.headers).get("X-Request-Id") ?? "req-import";
      return new Response(
        JSON.stringify({
          requestId,
          importId: "b50dc4e1-9605-4191-9b49-0b3bf675523a",
          projectId: "portable-project",
          projectName: "Portable Project",
          exportId: "a50dc4e1-9605-4191-9b49-0b3bf675523a",
          exportedAt: "2026-10-05T00:00:00Z",
          archiveSha256: "a".repeat(64),
          sizeBytes: 7,
          destinationAction: "add-project",
          counts: { notes: 1 },
          plaintextWarning: "Review before applying.",
        }),
        {
          status: 200,
          headers: { "content-type": "application/json", "X-Request-Id": requestId },
        },
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    await new ProjectaApiClient().previewPortableImport(new Blob(["archive"]));

    const [, init] = fetchMock.mock.calls[0] as [RequestInfo | URL, RequestInit];
    expect(new Headers(init.headers).get("Content-Type")).toBe("application/octet-stream");
    expect(init.body).toBeInstanceOf(Blob);
    await expect((init.body as Blob).text()).resolves.toBe("archive");
    vi.unstubAllGlobals();
  });

  it("tracks staged portable imports until the published result is available", async () => {
    const importId = "b50dc4e1-9605-4191-9b49-0b3bf675523a";
    const fetchMock = vi.fn().mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const requestId = new Headers(init?.headers).get("X-Request-Id") ?? "req-import-result";
      const path = new URL(String(input), "http://projecta.test").pathname;
      const result = path.endsWith("/apply")
        ? {
            requestId,
            importId,
            projectId: "portable-project",
            projectName: "Portable Project",
            alreadyImported: false,
            restartRequired: true,
            status: "staging",
          }
        : {
            requestId,
            importId,
            projectId: "portable-project",
            projectName: "Portable Project",
            status: "complete",
          };
      return new Response(JSON.stringify(result), {
        status: 200,
        headers: { "content-type": "application/json", "X-Request-Id": requestId },
      });
    });
    vi.stubGlobal("fetch", fetchMock);

    const api = new ProjectaApiClient();
    await expect(api.applyPortableImport(importId, true)).resolves.toMatchObject({
      importId,
      status: "staging",
      restartRequired: true,
    });
    await expect(api.getPortableImportResult(importId)).resolves.toMatchObject({
      importId,
      status: "complete",
      projectId: "portable-project",
    });
    expect(String(fetchMock.mock.calls[1][0])).toContain(`/v1/imports/${importId}`);
    vi.unstubAllGlobals();
  });
  it("accepts a portable import preview whose path also matches the result pattern", async () => {
    const requestId = "req-import-preview-path";
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          requestId,
          importId: "b50dc4e1-9605-4191-9b49-0b3bf675523a",
          projectId: "portable-project",
          projectName: "Portable Project",
          exportId: "a50dc4e1-9605-4191-9b49-0b3bf675523a",
          exportedAt: "2026-10-04T20:08:22.325728Z",
          archiveSha256: "a3127b6bc912ec8c64d160fdcd293857e9879fe9ac02a6b53ed7af86a321f97f",
          sizeBytes: 6827,
          destinationAction: "already-imported",
          counts: { namedGraphs: 5 },
          plaintextWarning: "Unsigned plaintext package.",
        }),
        {
          status: 200,
          headers: { "content-type": "application/json", "X-Request-Id": requestId },
        },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    await expect(new ProjectaApiClient().previewPortableImport(new Blob(["archive"]))).resolves.toMatchObject({
      importId: "b50dc4e1-9605-4191-9b49-0b3bf675523a",
      destinationAction: "already-imported",
    });
    vi.unstubAllGlobals();
  });
  it("previews and confirms a project deletion with typed identity", async () => {
    const requestId = "req-deletion-1";
    const fetchMock = vi.fn().mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const outgoing = new Headers(init?.headers).get("X-Request-Id") ?? requestId;
      const path = new URL(String(input), "http://projecta.test").pathname;
      const body =
        path.endsWith("/delete")
          ? {
              requestId: outgoing,
              projectId: "portable-project",
              projectName: "Portable Project",
              outcome: "deleted",
              restartRequired: true,
              graphTriplesRemoved: 3,
              evidenceObjectsRemoved: 1,
              sqliteRowsRemoved: 2,
              postgresRowsRemoved: 1,
              ledgerEntriesForgotten: 1,
              membershipsRemoved: 0,
              retained: ["other projects unchanged"],
            }
          : {
              requestId: outgoing,
              projectId: "portable-project",
              projectName: "Portable Project",
              graphTriples: { sources: 2, asserted: 1 },
              evidenceObjects: 1,
              sqliteRows: { structured_note_drafts: 2 },
              postgresRows: { review_decision_receipts: 1 },
              ledgerEntries: 1,
              warnings: ["There is no undo."],
            };
      return new Response(JSON.stringify(body), {
        status: 200,
        headers: { "content-type": "application/json", "X-Request-Id": outgoing },
      });
    });
    vi.stubGlobal("fetch", fetchMock);

    const api = new ProjectaApiClient();
    await expect(api.previewProjectDeletion("portable-project", "Portable Project")).resolves.toMatchObject({
      projectId: "portable-project",
      evidenceObjects: 1,
    });
    await expect(
      api.deleteProject("portable-project", "Portable Project", "Portable Project"),
    ).resolves.toMatchObject({ outcome: "deleted", ledgerEntriesForgotten: 1 });
    const [, deleteInit] = fetchMock.mock.calls[1] as [RequestInfo | URL, RequestInit];
    expect(String(deleteInit.body)).toContain('"confirmed":true');
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

  it("posts a project-scoped abstain receipt with an idempotency key", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          requestId: "req-abstain",
          contractVersion: "review-receipt.v1",
          decision: "abstain",
          outcome: "accepted",
          receipt: { receiptDigest: "sha256:" + "a".repeat(64) },
        }),
        {
          status: 200,
          headers: { "content-type": "application/json", "X-Request-Id": "req-abstain" },
        },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    await new ProjectaApiClient().abstainSelectedCandidate(
      "project-h-alpha",
      "candidate-h-1",
      {
        candidateRevision: 1,
        expectedCandidateRevision: 0,
        sourceVersionId: "sv_" + "b".repeat(64),
        sourceVersionRevision: 1,
        constrainedContractVersion: "constrained-relation.v1",
      },
      "abstain-1",
    );
    const [input, init] = fetchMock.mock.calls[0] as [RequestInfo | URL, RequestInit];
    expect(String(input)).toContain("/abstentions");
    expect(new Headers(init.headers).get("Idempotency-Key")).toBe("abstain-1");
    const body = JSON.parse(String(init.body)) as { decision?: unknown; candidateRevision: number };
    expect(body.candidateRevision).toBe(1);
    expect(body.decision).toBeUndefined();
    vi.unstubAllGlobals();
  });
});
