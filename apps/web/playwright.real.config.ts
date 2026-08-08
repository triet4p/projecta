import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  testMatch: "sprint7.real.spec.ts",
  fullyParallel: false,
  forbidOnly: true,
  retries: 0,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: "http://127.0.0.1:3000",
    trace: "on-first-retry",
  },
  projects: [{ name: "chromium-real", use: { ...devices["Desktop Chrome"] } }],
});
