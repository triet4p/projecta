/** Generated from docs/architecture/application-api.sprint7.openapi.json. */

export type EntityType =
  | "requirement"
  | "decision"
  | "question"
  | "task"
  | "risk"
  | "assumption"
  | "constraint"
  | "progress-update"
  | "research-need";

export interface LiveResponse {
  status: "live";
}

export interface ReadyResponse {
  status: "ready" | "not-ready";
  semanticCore: "ready" | "unavailable" | "injected";
}

export interface Problem {
  type: string;
  title: string;
  status: number;
  code: string;
  detail: string;
  requestId: string;
}

export type LlmHealth = "unknown" | "healthy" | "unhealthy" | "unavailable";

export interface LLMProfile {
  profileId: string;
  providerType: "openai-response" | "openai";
  baseUrl: string;
  model: string;
  active: boolean;
  revision: number;
  credentialConfigured: boolean;
  health: LlmHealth;
  lastCheckedAt?: string | null;
  createdAt?: string | null;
  updatedAt?: string | null;
}

export interface LLMProfileWrite {
  providerType: LLMProfile["providerType"];
  baseUrl: string;
  model: string;
  credential?: string;
  expectedRevision?: number;
}

export interface LLMProfileRemove {
  confirm: true;
  expectedRevision?: number;
}

export interface SettingsProfileResponse {
  requestId: string;
  profile: LLMProfile | null;
}

export interface ConnectionCheckRequest {
  timeoutSeconds?: number;
}

export interface ConnectionCheckResponse {
  requestId: string;
  status: "healthy" | "unhealthy" | "unavailable";
  credentialConfigured: boolean;
  detail: string;
  checkedAt: string;
}

export interface ExtractionRequest {
  rawText: string;
  extractionVersion?: "m3.v1";
}

export interface TypedSegment {
  type: EntityType;
  startOffset: number;
  endOffset: number;
  text: string;
}

export interface CaptureRequest {
  rawText: string;
  segments: TypedSegment[];
}

export interface Note {
  id: string;
  recordedAt?: string;
}

export type CandidateStatus =
  | "extracted"
  | "validated"
  | "pending-review"
  | "confirmed"
  | "rejected"
  | "asserted";

export interface Candidate {
  id: string;
  sourceItemId?: string;
  status: CandidateStatus;
}

export interface CaptureResponse {
  requestId: string;
  note: Note;
  candidates: Candidate[];
}

export interface EvidenceSpan {
  startOffset: number;
  endOffset: number;
  text: string;
}

export interface ExtractedEntity {
  type: string;
  label: string;
  evidence: EvidenceSpan;
  confidence: number;
}

export interface ExtractedRelation {
  predicate: string;
  sourceEntityId: string;
  targetEntityId: string;
  evidence: EvidenceSpan;
  confidence: number;
}

export interface ExtractedLink {
  mention: string;
  targetEntityId: string;
  evidence: EvidenceSpan;
  confidence: number;
}

export interface ExtractionResult extends CaptureResponse {
  abstentionReason?: string | null;
  entities?: ExtractedEntity[];
  relations?: ExtractedRelation[];
  links?: ExtractedLink[];
}

export interface ConfirmationRequest {
  assertion: {
    type: "Requirement";
    label: string;
    validFrom: string;
  };
}

export interface RejectionRequest {
  reason: string;
}

export interface ValidationResult {
  requestId: string;
  candidateId: string;
  conforms: boolean;
  violations: Record<string, unknown>[];
  validatedAt: string;
}

export interface DecisionResponse {
  requestId: string;
  candidateId: string;
  decision: "confirmed" | "rejected";
  assertedItemId?: string;
  reason?: string;
}

export interface KnowledgeItem {
  id: string;
  label: string;
  type: "Requirement";
  validFrom?: string | null;
}

export interface KnowledgeItemsResponse {
  requestId: string;
  items: KnowledgeItem[];
}

export interface CandidateHistoryActivity {
  id: string;
  decision?: string | null;
  reviewerId?: string | null;
  endedAt?: string | null;
}

export interface CandidateHistoryResponse {
  requestId: string;
  candidateId: string;
  items: CandidateHistoryActivity[];
}

export interface EvidenceRecord {
  candidateId?: string | null;
  sourceId?: string | null;
  noteId?: string | null;
  authorId?: string | null;
  reviewerId?: string | null;
  evidenceText?: string | null;
  startOffset?: number | null;
  endOffset?: number | null;
}

export interface EvidenceResponse {
  requestId: string;
  itemId: string;
  items: EvidenceRecord[];
}

export interface ProjectContextQuestion {
  question: string;
  limit?: number;
}

export interface Answer {
  answerVersion: "m4.v1";
  query: Record<string, unknown>;
  text: string;
  facts: Record<string, unknown>[];
  citations: Record<string, unknown>[];
  meta: Record<string, unknown>;
  complete: boolean;
  abstained: boolean;
  warnings: string[];
}

export interface InferenceRebuildResponse {
  sourceRevision: string;
  materializationRevision: string;
  materializedRuleIds: string[];
}

export interface Paths {
  "/v1/settings/llm": {
    get: { response: SettingsProfileResponse };
    put: { body: LLMProfileWrite; response: SettingsProfileResponse };
    delete: { body: LLMProfileRemove; response: SettingsProfileResponse };
  };
  "/v1/settings/llm/rotate": {
    post: { body: LLMProfileWrite; response: SettingsProfileResponse };
  };
  "/v1/settings/llm/connection-check": {
    post: { body: ConnectionCheckRequest; response: ConnectionCheckResponse };
  };
  "/health/live": { get: { response: LiveResponse } };
  "/health/ready": { get: { response: ReadyResponse } };
  "/v1/quick-notes/extractions": {
    post: { body: ExtractionRequest; response: ExtractionResult };
  };
  "/v1/quick-notes": { post: { body: CaptureRequest; response: CaptureResponse } };
  "/v1/candidates/{candidateId}/validations": {
    post: { response: ValidationResult };
  };
  "/v1/candidates/{candidateId}/confirmations": {
    post: { body: ConfirmationRequest; response: DecisionResponse };
  };
  "/v1/candidates/{candidateId}/rejections": {
    post: { body: RejectionRequest; response: DecisionResponse };
  };
  "/v1/knowledge-items/current": { get: { response: KnowledgeItemsResponse } };
  "/v1/candidates/{candidateId}/history": { get: { response: CandidateHistoryResponse } };
  "/v1/knowledge-items/{itemId}/evidence": { get: { response: EvidenceResponse } };
  "/v1/project-context/answers": {
    post: { body: ProjectContextQuestion; response: Answer };
  };
  "/v1/project-context/inference/rebuild": {
    post: { response: InferenceRebuildResponse };
  };
}
