import { expect, test, type Page } from "@playwright/test";

async function assertNoRdfIri(page: Page) {
  const body = await page.locator("body").innerText();
  expect(body).not.toContain("https://w3id.org/projecta/");
  expect(body).not.toContain("http://www.w3.org/");
}

test("real Compose journey keeps credentials and RDF internals out of the browser", async ({
  page,
}) => {
  const browserCredential = ["real", "browser", "credential"].join("-");
  const journeyToken = `real-browser-${Date.now()}`;
  const evidenceText = `The project requires ${journeyToken} acceptance.`;
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Projecta" })).toBeVisible();
  await expect(page.getByText("API live")).toBeVisible();
  await page.getByRole("button", { name: "Open project" }).first().click();
  await expect(page.getByRole("heading", { name: "Project A", level: 2 })).toBeVisible();

  await page.getByRole("button", { name: "Settings" }).click();
  await page.getByLabel("Base URL").fill("https://provider.example");
  await page.getByLabel("Model").fill("replay:typed-capture");
  await page.getByLabel("Credential").fill(browserCredential);
  await page.getByRole("button", { name: "Save profile" }).click();
  await expect(page.getByLabel("Credential")).toHaveValue("");
  const connectionResponsePromise = page.waitForResponse(
    (response) =>
      response.url().includes("/v1/settings/llm/connection-check") &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Test connection" }).click();
  const connectionResponse = await connectionResponsePromise;
  expect(connectionResponse.ok()).toBeTruthy();
  const connectionResult = (await connectionResponse.json()) as { status: string };
  await expect(page.locator(".section-heading .health-pill")).toHaveText(connectionResult.status, {
    timeout: 30000,
  });
  expect(await page.evaluate(() => [localStorage.length, sessionStorage.length])).toEqual([0, 0]);
  await assertNoRdfIri(page);

  await page.getByRole("button", { name: "Notes" }).click();
  await expect(page.getByRole("heading", { name: "Notes" })).toBeVisible();
  await page.getByRole("button", { name: "Add typed item" }).click();
  await page.getByLabel("Item 1 content").fill(evidenceText);
  await page.getByRole("button", { name: "Save draft" }).click();
  await expect(page.getByText(/Draft saved at revision/)).toBeVisible();
  await assertNoRdfIri(page);
  expect(await page.locator("body").innerText()).not.toContain(browserCredential);
});
