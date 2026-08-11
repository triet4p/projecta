import { expect, test, type Page } from "@playwright/test";

async function acceptNextDialog(page: Page) {
  return page.waitForEvent("dialog").then((dialog) => dialog.accept());
}

test("real Compose JSON/Mock import stays bounded and public-ID free", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Projecta" })).toBeVisible();
  await page.getByRole("button", { name: "Open project" }).first().click();
  await expect(page.getByRole("heading", { name: "Project A", level: 2 })).toBeVisible();
  await page.getByRole("button", { name: "Connections" }).click();
  await expect(page.getByRole("heading", { name: "Connections" })).toBeVisible();
  await expect(page.getByText("JSON/Mock")).toBeVisible();

  await Promise.all([
    acceptNextDialog(page),
    page.getByRole("button", { name: "Install JSON/Mock" }).click(),
  ]);
  await expect(page.getByText("Connector installation created disabled.")).toBeVisible();

  const row = page.getByRole("row").filter({ hasText: "json-mock" });
  await expect(row.getByText("Disabled")).toBeVisible();
  await Promise.all([acceptNextDialog(page), row.getByRole("button", { name: "Enable" }).click()]);
  await expect(row.getByText("Enabled")).toBeVisible();

  const syncRequestPromise = page.waitForRequest(
    (request) => request.method() === "POST" && request.url().endsWith("/runs"),
  );
  await row.getByRole("button", { name: "Run sync" }).click();
  const syncRequest = await syncRequestPromise;
  await expect(row.getByRole("cell", { name: "Succeeded" })).toBeVisible({ timeout: 30_000 });
  const syncHeaders = syncRequest.headers();
  const replayResponse = await page.request.post(syncRequest.url(), {
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": syncHeaders["idempotency-key"],
      "X-Projecta-Selection-Handle": syncHeaders["x-projecta-selection-handle"],
      "X-Request-Id": "s10-real-replay-request",
    },
    data: syncRequest.postDataJSON(),
  });
  expect(replayResponse.status()).toBe(200);
  const replay = (await replayResponse.json()) as {
    state: string;
    eventCount: number;
    replayCount: number;
  };
  expect(replay.state).toBe("replayed");
  expect(replay.eventCount).toBe(1);

  await page.getByRole("button", { name: "Graph" }).click();
  await expect(page.getByRole("table")).toContainText("JSON Mock import");
  await expect(page.getByRole("table")).toContainText("Review imported source");
  await page.getByRole("button", { name: "Review Queue" }).click();
  await expect(page.getByText("Review imported source")).toBeVisible();

  await page.getByRole("button", { name: "Connections" }).click();
  const activeRow = page.getByRole("row").filter({ hasText: "json-mock" });
  await Promise.all([
    acceptNextDialog(page),
    activeRow.getByRole("button", { name: "Disable" }).click(),
  ]);
  await expect(activeRow.getByText("Disabled")).toBeVisible();
  const disabledResponse = await page.request.post(syncRequest.url(), {
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": "s10-disabled-run-key",
      "X-Projecta-Selection-Handle": syncHeaders["x-projecta-selection-handle"],
      "X-Request-Id": "s10-real-disabled-request",
    },
    data: { expectedInstallationRevision: 3 },
  });
  expect(disabledResponse.status()).toBe(409);
  expect((await disabledResponse.json()).code).toBe("CONNECTOR_DISABLED");
  await Promise.all([
    acceptNextDialog(page),
    activeRow.getByRole("button", { name: "Enable" }).click(),
  ]);
  await expect(activeRow.getByText("Enabled")).toBeVisible();

  await page.setViewportSize({ width: 390, height: 844 });
  await expect(activeRow.getByRole("button", { name: "Run sync" })).toBeVisible();
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1),
  ).toBeTruthy();

  await page.getByRole("button", { name: "Projects" }).click();
  const projectB = page.getByRole("article").filter({ hasText: "Project B" });
  await projectB.getByRole("button", { name: "Open project" }).click();
  await expect(page.getByRole("heading", { name: "Project B", level: 2 })).toBeVisible();
  await page.getByRole("button", { name: "Connections" }).click();
  await expect(
    page.getByText("No connector installations exist for this project yet."),
  ).toBeVisible();
  await expect(page.getByRole("row").filter({ hasText: "json-mock" })).toHaveCount(0);
  await expect(page.locator("body")).not.toContainText("secretReference");
  await expect(page.locator("body")).not.toContainText("https://w3id.org/projecta/");
  await expect(page.locator("body")).not.toContainText("ev_");
});
