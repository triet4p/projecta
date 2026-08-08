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
  const requirementLabel = `Real browser requirement ${journeyToken}`;
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Projecta" })).toBeVisible();
  await expect(page.getByText("API live")).toBeVisible();

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

  await page.getByRole("button", { name: "Capture" }).click();
  const captureNote = page.getByLabel("Capture note");
  await captureNote.fill(evidenceText);
  await captureNote.press("Control+A");
  const addSpan = page.getByRole("button", { name: "Add selected span" });
  await expect(addSpan).toBeEnabled();
  await addSpan.click();
  const captureResponsePromise = page.waitForResponse(
    (response) =>
      response.url().includes("/v1/quick-notes") && response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Capture note" }).click();
  const captureResponse = await captureResponsePromise;
  const capturePayload = (await captureResponse.json()) as {
    candidates: Array<{ id: string }>;
  };
  const candidateId = capturePayload.candidates[0]?.id ?? "";
  expect(candidateId).toBeTruthy();
  const reviewButton = page.locator("button.candidate-chip");
  await expect(reviewButton).toHaveCount(1);
  await reviewButton.click();
  await page.getByLabel("Opaque candidate ID").fill(candidateId);

  await page.getByRole("button", { name: "Validate candidate" }).click();
  await expect(page.getByText("Conforms")).toBeVisible();
  await page.getByLabel("Requirement label").fill(requirementLabel);
  await page.getByRole("button", { name: "Confirm Requirement" }).click();
  await expect(page.getByText(/Decision recorded: confirmed/)).toBeVisible();

  await page.getByRole("button", { name: "Knowledge" }).click();
  const requirementItem = page.locator(".knowledge-item").filter({ hasText: requirementLabel });
  await expect(requirementItem).toHaveCount(1);
  await requirementItem.getByRole("button", { name: "View evidence" }).click();
  await expect(page.getByText(evidenceText)).toHaveCount(1);
  await page.getByLabel("Candidate ID").fill(candidateId);
  await page.getByRole("button", { name: "Load history" }).click();
  await expect(page.getByText(`Candidate ${candidateId}`)).toBeVisible();
  await assertNoRdfIri(page);

  await page.getByRole("button", { name: "Q&A" }).click();
  await page.getByLabel("Project question").fill("What requirement was confirmed?");
  await page.getByRole("button", { name: "Ask question" }).click();
  await assertNoRdfIri(page);
  expect(await page.locator("body").innerText()).not.toContain(browserCredential);
});
