import { describe, expect, it } from "vitest";

import type { ReviewWorkbenchDetailResponse } from "./api/generated";
import { reviewDecisionDisabled, reviewStatusLabel } from "./screens/review-workbench";
import type { ManualReviewWorkbenchDetailResponse } from "./api/manual-capture";

const detail = (
  overrides: Partial<ReviewWorkbenchDetailResponse> = {},
): ReviewWorkbenchDetailResponse => ({
  detailVersion: "review-workbench.v1",
  requestId: "req-1",
  projectHandle: "project-h-1",
  itemHandle: "candidate-h-1",
  projectScope: "selected",
  sourceVersion: { revision: 4, sourceVersionId: "sv_" + "a".repeat(64) },
  candidateRevision: 2,
  label: "A requirement",
  semanticType: "Requirement",
  lifecycleState: "pending-review",
  validationState: "validated",
  constrainedContractVersion: "constrained-relation.v1",
  confidence: 0.9,
  sourceText: "A requirement is recorded.",
  proposed: { label: "A requirement", semanticType: "Requirement" },
  edited: null,
  evidence: { status: "selected", highlights: [] },
  uncertaintyReasons: [],
  stale: false,
  quarantined: false,
  abstainReason: null,
  reviewReceipt: {
    state: "not-recorded",
    candidateRevision: 2,
    sourceVersionRevision: 4,
  },
  ...overrides,
});
const manualDetail = (
  overrides: Partial<ManualReviewWorkbenchDetailResponse> = {},
): ManualReviewWorkbenchDetailResponse =>
  ({
    ...detail({
      sourceVersion: { revision: 1, sourceVersionId: "sv_" + "b".repeat(64) },
      candidateRevision: 1,
      evidence: {
        status: "selected",
        highlights: [
          {
            kind: "evidence",
            startOffset: 0,
            endOffset: 4,
            quoteDigest: "sha256:" + "c".repeat(64),
          },
        ],
      },
      reviewReceipt: {
        state: "not-recorded",
        candidateRevision: 1,
        sourceVersionRevision: 1,
      },
    }),
    manualCapture: {
      mode: "human-authored-zero-model",
      entityHandle: "eh1_" + "d".repeat(64),
    },
    ...overrides,
  }) as ManualReviewWorkbenchDetailResponse;


describe("review workbench decision guard", () => {
  it("requires selected evidence for confirmation and keeps other actions explicit", () => {
    expect(
      reviewDecisionDisabled(
        detail({ evidence: { status: "unavailable", highlights: [] } }),
        "confirm",
        false,
      ),
    ).toBe(true);
    expect(
      reviewDecisionDisabled(
        detail({ evidence: { status: "unavailable", highlights: [] } }),
        "reject",
        false,
      ),
    ).toBe(false);
    expect(reviewDecisionDisabled(detail(), "abstain", false)).toBe(false);
  });
  it("requires a current source revision and exact anchor for manual decisions", () => {
    expect(reviewDecisionDisabled(manualDetail(), "confirm", false)).toBe(false);
    expect(reviewDecisionDisabled(manualDetail(), "reject", false)).toBe(false);
    expect(reviewDecisionDisabled(manualDetail(), "abstain", false)).toBe(false);
    expect(
      reviewDecisionDisabled(
        manualDetail({ sourceVersion: { revision: 1, sourceVersionId: null } }),
        "reject",
        false,
      ),
    ).toBe(true);
    expect(reviewDecisionDisabled(manualDetail({ candidateRevision: 0 }), "abstain", false)).toBe(
      true,
    );
    expect(
      reviewDecisionDisabled(
        manualDetail({ evidence: { status: "selected", highlights: [] } }),
        "reject",
        false,
      ),
    ).toBe(true);
  });


  it("fails closed for stale, quarantined, and already receipted items", () => {
    expect(reviewDecisionDisabled(detail({ stale: true }), "reject", false)).toBe(true);
    expect(reviewDecisionDisabled(detail({ quarantined: true }), "abstain", false)).toBe(true);
    expect(
      reviewDecisionDisabled(
        detail({
          reviewReceipt: { state: "accepted", candidateRevision: 2, sourceVersionRevision: 4 },
        }),
        "edit",
        false,
      ),
    ).toBe(true);
    expect(reviewStatusLabel(detail({ stale: true }))).toContain("Stale");
  });
});
