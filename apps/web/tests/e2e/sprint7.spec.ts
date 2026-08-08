import { expect, test, type Page } from "@playwright/test";

const profile = {
  profile: {
    profileId: "profile-1",
    providerType: "openai-response",
    baseUrl: "https://provider.example/",
    model: "model-1",
    active: true,
    revision: 1,
    credentialConfigured: true,
    health: "healthy",
  },
};

async function mockApi(page: Page) {
  await page.route("**/health/live", (route) => route.fulfill({ json: { status: "live" } }));
  await page.route("**/health/ready", (route) =>
    route.fulfill({ json: { status: "ready", semanticCore: "ready" } }),
  );
  await page.route("**/v1/settings/llm", (route) => {
    if (route.request().method() === "GET") return route.fulfill({ json: profile });
    return route.fulfill({ json: profile });
  });
  await page.route("**/v1/settings/llm/connection-check", (route) =>
    route.fulfill({
      json: {
        requestId: "req-connection-check",
        status: "unhealthy",
        credentialConfigured: true,
        detail: "Provider rejected the bounded check.",
        checkedAt: "2026-08-09T00:00:00Z",
      },
    }),
  );
  await page.route("**/v1/quick-notes/extractions", (route) =>
    route.fulfill({
      json: {
        requestId: "req-extract",
        candidates: [{ id: "candidate-1", status: "proposed" }],
        note: { id: "note-1" },
        entities: [],
        relations: [],
        links: [],
        abstentionReason: null,
      },
    }),
  );
  await page.route("**/v1/quick-notes", (route) =>
    route.fulfill({
      status: 201,
      json: {
        requestId: "req-capture",
        note: { id: "note-capture" },
        candidates: [{ id: "candidate-capture", status: "pending-review" }],
      },
    }),
  );
  await page.route("**/v1/candidates/candidate-1/validations", (route) =>
    route.fulfill({
      json: { conforms: true, validatedAt: "2026-08-05T00:00:00Z", violations: [] },
    }),
  );
  await page.route("**/v1/candidates/candidate-1/confirmations", (route) =>
    route.fulfill({ json: { decision: "confirmed", candidateId: "candidate-1" } }),
  );
  await page.route("**/v1/knowledge-items/current*", (route) =>
    route.fulfill({ json: { items: [{ id: "item-1", label: "Use deterministic fixtures" }] } }),
  );
  await page.route("**/v1/project-context/answers", (route) =>
    route.fulfill({
      json: {
        text: "The project uses deterministic fixtures.",
        complete: true,
        abstained: false,
        facts: [],
        citations: [],
        derivation: [],
        warnings: [],
      },
    }),
  );
}

test("desktop critical journey reaches settings, extraction, review, knowledge, and Q&A", async ({
  page,
}) => {
  const testCredential = ["browser", "secret", "must-clear"].join("-");
  const responseBodies: string[] = [];
  page.on("response", async (response) => {
    if (!response.url().includes("/v1/")) return;
    try {
      responseBodies.push(await response.text());
    } catch {
      // Ignore responses that are intentionally not readable by the runner.
    }
  });
  await mockApi(page);
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Projecta" })).toBeVisible();

  await page.getByRole("button", { name: "Settings" }).click();
  await expect(page.getByRole("heading", { name: "LLM settings" })).toBeVisible();
  await page.getByLabel("Credential").fill(testCredential);
  await expect(page.getByRole("button", { name: "Save profile" })).toBeEnabled();
  await page.getByRole("button", { name: "Save profile" }).click();
  await expect(page.getByLabel("Credential")).toHaveValue("");
  await page.getByRole("button", { name: "Test connection" }).click();
  await expect(page.locator(".section-heading .health-pill")).toHaveText("unhealthy");
  expect(await page.evaluate(() => [localStorage.length, sessionStorage.length])).toEqual([0, 0]);

  await page.getByRole("button", { name: "Extract" }).click();
  await page.getByLabel("Raw note").fill("The project needs deterministic fixtures.");
  await page.getByRole("button", { name: "Extract note" }).click();
  await page.getByRole("button", { name: /Review candidate candidate-1/ }).click();
  await page.getByRole("button", { name: "Validate candidate" }).click();
  await expect(page.getByText("Conforms")).toBeVisible();

  await page.getByRole("button", { name: "Knowledge" }).click();
  await expect(page.getByText("Use deterministic fixtures")).toBeVisible();
  await page.getByRole("button", { name: "Q&A" }).click();
  await page.getByLabel("Project question").fill("What does the project use?");
  await page.getByRole("button", { name: "Ask question" }).click();
  await expect(page.getByText("The project uses deterministic fixtures.")).toBeVisible();
  await expect(page.locator("body")).not.toContainText(testCredential);
  expect(responseBodies.join("\n")).not.toContain(testCredential);
});

test("narrow viewport keeps the navigation keyboard reachable", async ({ page }) => {
  await mockApi(page);
  await page.goto("/");
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Skip to main content" })).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("main")).toBeFocused();
  await page.getByRole("button", { name: "Capture" }).click();
  await expect(page.getByRole("heading", { name: "Capture exact evidence" })).toBeVisible();
  const captureNote = page.getByLabel("Capture note");
  await captureNote.fill("The project needs a typed requirement.");
  await captureNote.press("Control+A");
  const addSpan = page.getByRole("button", { name: "Add selected span" });
  await expect(addSpan).toBeEnabled();
  await addSpan.click();
  await expect(page.locator(".segment strong")).toHaveText(
    "The project needs a typed requirement.",
  );
});
