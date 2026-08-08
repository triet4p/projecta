import { describe, expect, it } from "vitest";

import type { ValidationResult } from "./api/generated";
import { canCapture, canConfirmRequirement, clearCredential, settingsCanSave } from "./form-state";

const conforming: ValidationResult = {
  requestId: "request-1",
  candidateId: "candidate-1",
  conforms: true,
  validatedAt: "2026-08-05T00:00:00Z",
  violations: [],
};

describe("Sprint 7 form and capability state", () => {
  it("requires a credential only for a first profile", () => {
    expect(
      settingsCanSave(null, {
        baseUrl: "https://provider.example",
        model: "model-1",
        credential: "secret",
      }),
    ).toBe(true);
    expect(
      settingsCanSave(null, {
        baseUrl: "https://provider.example",
        model: "model-1",
        credential: "",
      }),
    ).toBe(false);
  });

  it("clears credential state after a successful write", () => {
    expect(clearCredential()).toBe("");
  });

  it("gates Requirement confirmation on validation and a label", () => {
    expect(canConfirmRequirement(null, "Requirement")).toBe(false);
    expect(canConfirmRequirement(conforming, "")).toBe(false);
    expect(canConfirmRequirement(conforming, "Requirement")).toBe(true);
  });

  it("requires exact capture content and at least one segment", () => {
    expect(canCapture("", 1)).toBe(false);
    expect(canCapture("Note", 0)).toBe(false);
    expect(canCapture("Note", 1)).toBe(true);
  });
});
