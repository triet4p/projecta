import type { LLMProfile, LLMProfileWrite, ValidationResult } from "./api/generated";

export function settingsCanSave(
  profile: LLMProfile | null,
  values: Pick<LLMProfileWrite, "baseUrl" | "model" | "credential">,
): boolean {
  return Boolean(
    values.baseUrl.trim() && values.model.trim() && (profile !== null || values.credential?.trim()),
  );
}

export function clearCredential(): string {
  return "";
}

export function canConfirmRequirement(validation: ValidationResult | null, label: string): boolean {
  return Boolean(validation?.conforms && label.trim());
}

export function canCapture(rawText: string, segmentCount: number): boolean {
  return Boolean(rawText.trim() && segmentCount > 0);
}
