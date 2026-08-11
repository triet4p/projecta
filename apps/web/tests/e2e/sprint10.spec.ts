import { expect, test, type Page, type Route } from "@playwright/test";

const project = {
  handle: "project-h-alpha",
  name: "Alpha workspace",
  summary: "Deterministic connector acceptance workspace",
  status: "active",
  counts: { requirements: 0, tasks: 0, questions: 0, risks: 0, notes: 0, candidates: 0 },
  lastActivityAt: "2026-08-10T00:00:00Z",
  health: "fresh",
  freshness: { state: "current", revision: "source-r1" },
};

async function json(route: Route, body: Record<string, unknown>, status = 200) {
  const requestId = route.request().headers()["x-request-id"] ?? "req-s10-fixture";
  await route.fulfill({
    status,
    contentType: "application/json",
    headers: { "X-Request-Id": requestId },
    body: JSON.stringify({ ...body, requestId }),
  });
}

async function mockConnectorApi(page: Page) {
  let installed = false;
  let enabled = false;
  await page.route("**/health/live", (route) => void json(route, { status: "live" }));
  await page.route("**/health/ready", (route) => void json(route, { status: "ready" }));
  await page.route("**/v1/**", async (route) => {
    const request = route.request();
    const { pathname } = new URL(request.url());
    if (pathname === "/v1/projects" && request.method() === "GET") {
      return json(route, { catalogRevision: "catalog-r1", projects: [project] });
    }
    if (pathname === "/v1/projects/selection") {
      return json(route, { selectionRevision: "selection-r1", project });
    }
    if (pathname === "/v1/connectors/catalog") {
      return json(route, {
        items: [
          {
            connectorType: "json-mock",
            contractVersion: "connector-contract.v1",
            displayName: "JSON/Mock",
            capabilities: ["inbound-import"],
            limits: { maxEvents: 100 },
          },
        ],
      });
    }
    if (pathname.endsWith("/connectors/installations") && request.method() === "GET") {
      return json(route, {
        items: installed
          ? [
              {
                requestId: "req-install",
                handle: "ci_public",
                connectorType: "json-mock",
                capabilities: ["inbound-import"],
                enabled,
                revision: enabled ? 2 : 1,
                secretConfigured: false,
                fixtureConfigured: true,
              },
            ]
          : [],
        nextOffset: null,
      });
    }
    if (pathname.endsWith("/connectors/installations") && request.method() === "POST") {
      installed = true;
      return json(
        route,
        {
          handle: "ci_public",
          connectorType: "json-mock",
          capabilities: ["inbound-import"],
          enabled: false,
          revision: 1,
          secretConfigured: false,
          fixtureConfigured: true,
        },
        201,
      );
    }
    if (pathname.endsWith("/enable")) {
      enabled = true;
      return json(route, {
        handle: "ci_public",
        connectorType: "json-mock",
        capabilities: ["inbound-import"],
        enabled: true,
        revision: 2,
        secretConfigured: false,
        fixtureConfigured: true,
      });
    }
    if (pathname.endsWith("/runs") && request.method() === "GET") return json(route, { items: [] });
    if (pathname.endsWith("/runs") && request.method() === "POST") {
      return json(
        route,
        {
          handle: "cr_public",
          state: "succeeded",
          eventCount: 1,
          replayCount: 0,
          failureCode: null,
          deadLetterAvailable: false,
          revision: 2,
          startedAt: "2026-08-10T00:00:00Z",
          terminalAt: "2026-08-10T00:00:01Z",
        },
        202,
      );
    }
    return json(route, { items: [] });
  });
}

test("Connections supports install, enable, run, and ID-free public state", async ({ page }) => {
  await mockConnectorApi(page);
  await page.goto("/");
  await page.getByRole("button", { name: "Open project" }).click();
  await page.getByRole("button", { name: "Connections" }).click();
  await expect(page.getByRole("heading", { name: "Connections" })).toBeVisible();
  await Promise.all([
    page.waitForEvent("dialog").then((dialog) => dialog.accept()),
    page.getByRole("button", { name: "Install JSON/Mock" }).click(),
  ]);
  await expect(
    page.getByRole("row").filter({ hasText: "json-mock" }).getByText("Disabled"),
  ).toBeVisible();
  await Promise.all([
    page.waitForEvent("dialog").then((dialog) => dialog.accept()),
    page.getByRole("button", { name: "Enable" }).click(),
  ]);
  await page.getByRole("button", { name: "Run sync" }).click();
  await expect(page.getByRole("cell", { name: "Succeeded" })).toBeVisible();
  await expect(page.locator("body")).not.toContainText("ci_internal");
  await expect(page.locator("body")).not.toContainText("secretReference");
});
