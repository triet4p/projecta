import { expect, test } from "@playwright/test";

test("real Compose restart preserves connector, source, and run projections", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Open project" }).first().click();
  await expect(page.getByRole("heading", { name: "Project A", level: 2 })).toBeVisible();

  await page.getByRole("button", { name: "Connections" }).click();
  const row = page.getByRole("row").filter({ hasText: "json-mock" });
  await expect(row.getByText("Enabled")).toBeVisible();
  await expect(row.getByRole("cell", { name: "Succeeded" })).toBeVisible();
  await expect(row).toContainText("1 events");
  await expect(page.getByRole("button", { name: "Install JSON/Mock" })).toHaveCount(0);

  await page.getByRole("button", { name: "Graph" }).click();
  await expect(page.getByRole("table")).toContainText("JSON Mock import");
  await expect(page.getByRole("table")).toContainText("Review imported source");
  await page.getByRole("button", { name: "Review Queue" }).click();
  await expect(page.getByText("Review imported source")).toBeVisible();

  await expect(page.locator("body")).not.toContainText("secretReference");
  await expect(page.locator("body")).not.toContainText("https://w3id.org/projecta/");
  await expect(page.locator("body")).not.toContainText("ev_");
});
