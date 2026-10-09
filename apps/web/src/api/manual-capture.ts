import type { ReviewReceiptRecord } from "./generated";

export interface ManualCaptureApprovalRequest {
  candidateRevision: number;
  expectedCandidateRevision: number;
  sourceVersionId: string;
  sourceVersionRevision: number;
  anchorQuoteDigest: string;
}

export interface ManualCaptureApprovalResponse {
  contractVersion: "manual-capture-approval.v1";
  requestId: string;
  outcome: "accepted" | "replayed";
  receipt: ReviewReceiptRecord;
  materializationState: "blocked";
  reasonCode: "MATERIALIZATION_NOT_AUTHORIZED";
}

export interface ManualCaptureRejectionRequest extends ManualCaptureApprovalRequest {
  reason: string;
}

export interface ManualCaptureRejectionResponse {
  contractVersion: "manual-capture-decision.v1";
  requestId: string;
  decision: "rejected";
  outcome: "accepted" | "replayed";
  receipt: ReviewReceiptRecord;
}

export type RelationDirection = "source-to-target" | "target-to-source";
export type ControlledRelationMode = "manual" | "local";

export interface RelationSuggestionTarget {
  candidateHandle: string;
  label: string;
  entityType: string;
  allowedPredicates: Record<RelationDirection, string[]>;
}

export interface RelationSuggestionTargetsResponse {
  requestId: string;
  targets: RelationSuggestionTarget[];
}

export interface ControlledRelationRequest {
  targetCandidateHandle: string;
  direction: RelationDirection;
  mode: ControlledRelationMode;
  predicate?: string;
  retry?: boolean;
}

export interface ControlledRelationDecisionRequest {
  expectedProposalRevision: number;
  decision: "confirm" | "reject";
  reason?: string;
}

export interface RelationEvidenceView {
  contractVersion: "relation-evidence.v1";
  outcome: "selected" | "review-required" | "abstained" | "quarantined";
  reason: string;
  materializable: boolean;
  relationId: string;
  sourceVersionId: string;
  sourceHandle: string;
  targetHandle: string;
  predicate: string;
  block: {
    contractVersion: "source-block.v1";
    blockId: string;
    sourceVersionId: string;
    kind: "sentence" | "clause";
    startOffset: number;
    endOffset: number;
    contentDigest: string;
  } | null;
  sourceAnchorDigest: string | null;
  targetAnchorDigest: string | null;
  triggerAnchorDigest: string | null;
}

export type LocalSuggestionState =
  | "ready"
  | "unavailable"
  | "proposed"
  | "edited"
  | "confirmed"
  | "rejected"
  | "abstained"
  | "in-progress"
  | "failed"
  | "budget-exhausted";

export interface LocalSuggestionBudget {
  userDailyLimit: number;
  userRemaining: number;
  projectDailyLimit: number;
  projectRemaining: number;
  resetsAt: string;
}

export interface LocalSuggestionView {
  suggestionId: string;
  revision: number;
  kind: "item" | "type" | "link" | "relation" | "abstain";
  itemText: string | null;
  entityType: string | null;
  targetHandle: string | null;
  targetLabel: string | null;
  abstentionCode: string | null;
  selectedCandidateHandle: string | null;
  targetCandidateHandle: string | null;
  relationId: string | null;
  sourceHandle: string | null;
  predicate: string | null;
  direction: RelationDirection | null;
  relationMode: ControlledRelationMode | null;
  relationEvidenceDigest: string | null;
  relationEvidence: RelationEvidenceView | null;
  sourceVersionRevision: number;
  evidenceDigest: string;
  receiptDigest: string | null;
  materializationState: "blocked";
}

export interface LocalSuggestionLinkOption {
  handle: string;
  label: string;
}

export interface LocalSuggestionResponse {
  requestId: string;
  state: LocalSuggestionState;
  modelAvailable: boolean;
  availabilityReason: "local_model_not_configured" | "production_disabled" | null;
  budget: LocalSuggestionBudget;
  suggestion: LocalSuggestionView | null;
  linkOptions: LocalSuggestionLinkOption[];
  failureCode:
    | "local_runtime_unavailable"
    | "local_output_invalid"
    | "source_too_large"
    | "suggestion_budget_exhausted"
    | null;
  receipt: ReviewReceiptRecord | null;
}

export interface LocalSuggestionEdit {
  itemText?: string;
  entityType?: string;
  targetHandle?: string;
}

export interface LocalSuggestionDecisionRequest {
  expectedProposalRevision: number;
  decision: "confirm" | "edit" | "reject";
  edit?: LocalSuggestionEdit;
  reason?: string;
}
