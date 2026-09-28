import type { ReviewWorkbenchDetailResponse } from "../api/generated";

export type ReviewDecision = "confirm" | "edit" | "reject" | "abstain";

export function reviewDecisionDisabled(
  detail: ReviewWorkbenchDetailResponse | null,
  decision: ReviewDecision,
  busy: boolean,
): boolean {
  if (busy || !detail) return true;
  if (detail.stale || detail.quarantined) return true;
  if (detail.reviewReceipt.state !== "not-recorded") return true;
  if (
    detail.manualCapture &&
    (!detail.sourceVersion.sourceVersionId ||
      detail.sourceVersion.revision < 1 ||
      detail.candidateRevision < 1 ||
      detail.evidence.highlights.length === 0)
  ) {
    return true;
  }
  if (decision === "confirm") return detail.evidence.status !== "selected";
  if (decision === "abstain") {
    return (
      detail.sourceVersion.revision < 1 ||
      detail.candidateRevision < 1 ||
      !detail.sourceVersion.sourceVersionId
    );
  }
  return false;
}

export function reviewStatusLabel(detail: ReviewWorkbenchDetailResponse): string {
  if (detail.stale) return "Stale source — refresh required";
  if (detail.quarantined)
    return `Quarantined${detail.abstainReason ? `: ${detail.abstainReason}` : ""}`;
  if (detail.reviewReceipt.state !== "not-recorded") {
    return `Receipt: ${detail.reviewReceipt.state}`;
  }
  if (detail.evidence.status === "unavailable") return "Evidence unavailable";
  if (detail.evidence.status === "review-required") return "Evidence requires review";
  return "Ready for explicit review";
}
