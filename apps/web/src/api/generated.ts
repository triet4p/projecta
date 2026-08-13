/** Generated from docs/architecture/application-api.sprint7.openapi.json (Sprint 8 contract). */

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

export interface ConnectorCatalogItem {
  connectorType: "json-mock" | "teams" | "github-public-issues";
  contractVersion: "connector-contract.v1";
  displayName: string;
  capabilities: string[];
  limits: Record<string, number>;
  setupMode: "fixture" | "operator-setup";
  consentGuidance: string;
}

export interface ConnectorCatalogResponse {
  requestId: string;
  items: ConnectorCatalogItem[];
}

export interface ConnectorInstallation {
  requestId: string;
  handle: string;
  connectorType: "json-mock" | "teams" | "github-public-issues";
  capabilities: string[];
  enabled: boolean;
  revision: number;
  secretConfigured: boolean;
  fixtureConfigured: boolean;
  setupStatus: "ready" | "setup-required" | "unavailable";
  consentGuidance: string;
}

export interface ConnectorInstallationListResponse {
  requestId: string;
  items: ConnectorInstallation[];
  nextOffset: number | null;
}

export interface ConnectorRun {
  requestId: string;
  handle: string;
  state:
    | "running"
    | "succeeded"
    | "empty"
    | "replayed"
    | "failed"
    | "cancelled"
    | "truncated"
    | "unavailable";
  eventCount: number;
  replayCount: number;
  failureCode: string | null;
  deadLetterAvailable: boolean;
  revision: number;
  startedAt: string;
  terminalAt: string | null;
  cursorBeforeDigest?: string | null;
  cursorAfterDigest?: string | null;
}

export interface ConnectorRunListResponse {
  requestId: string;
  items: ConnectorRun[];
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
  title?: string;
  rawText: string;
  segments: TypedSegment[];
}

export interface StructuredNoteItemDraft {
  itemType: EntityType;
  content: string;
}

export type NoteDraftStatus = "draft" | "ready" | "committed" | "abstained";

export interface StructuredNoteDraftInput {
  title: string;
  items: StructuredNoteItemDraft[];
  draftStatus?: NoteDraftStatus;
  sourceMetadata?: {
    kind: "manual" | "text-import" | "connector";
    label?: string;
    reference?: string;
  };
}

export interface StructuredNoteItemProjection extends StructuredNoteItemDraft {
  startOffset: number;
  endOffset: number;
}

export interface StructuredNoteDraftResponse {
  requestId: string;
  draftHandle: string;
  revision: number;
  title: string;
  items: StructuredNoteItemProjection[];
  rawText: string;
  draftStatus: NoteDraftStatus;
  sourceMetadata?: StructuredNoteDraftInput["sourceMetadata"] | null;
  committedNoteHandle?: string | null;
}

export interface StructuredNoteListItem {
  handle: string;
  title: string;
  author?: string | null;
  recordedAt?: string | null;
  itemTypeSummary: EntityType[];
  candidateState?: string | null;
  evidenceCoverage?: number | null;
}

export interface StructuredNoteListResponse {
  requestId: string;
  drafts: StructuredNoteDraftResponse[];
  committed: StructuredNoteListItem[];
}

export interface StructuredNoteImportResponse {
  requestId: string;
  status: "proposed" | "abstained";
  title?: string | null;
  proposals: StructuredNoteItemDraft[];
  relations: Array<{ relation: string; sourceIndex: number; targetIndex: number }>;
  abstentionReason?: string | null;
}

export interface StructuredNoteDetail {
  noteHandle: string;
  title: string;
  rawText: string;
  author: string;
  recordedAt: string;
  items: StructuredNoteItemProjection[];
  evidenceCoverage: number;
  candidateState: string;
}

export interface StructuredCandidateEditRequest {
  entityType?: string;
  label?: string;
  relation?: string;
  entityLink?: string;
  date?: string;
  assignment?: string;
  expectedRevision?: number;
}

export interface CandidateEditOption {
  handle: string;
  label: string;
  type: string;
}

export interface CandidateEditOptionsResponse {
  requestId: string;
  entityLinks: CandidateEditOption[];
  assignments: CandidateEditOption[];
}

export interface StructuredCandidateEditResponse {
  requestId: string;
  candidateHandle: string;
  editHandle: string;
  revision: number;
  corrections: StructuredCandidateEditRequest;
  provenance: { actor: string; requestId: string; recordedAt: string };
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
  correctionRevision?: number;
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
  correctionRevision?: number;
  correctionsValidated?: boolean;
  corrections?: StructuredCandidateEditRequest;
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

export interface ProjectCounts {
  requirements: number;
  tasks: number;
  questions: number;
  risks: number;
  notes: number;
  candidates: number;
}

export interface ProjectFreshness {
  state: "current" | "stale" | "unavailable";
  revision?: string | null;
}

export interface ProjectCatalogItem {
  handle: string;
  name: string;
  summary?: string | null;
  status: "active" | "paused" | "archived";
  counts: ProjectCounts;
  lastActivityAt?: string | null;
  health: "fresh" | "attention" | "unavailable";
  freshness: ProjectFreshness;
}

export interface ProjectCatalogResponse {
  requestId: string;
  catalogRevision: string;
  projects: ProjectCatalogItem[];
  nextCursor?: string | null;
}

export interface ProjectReadResponse {
  requestId: string;
  project: ProjectCatalogItem;
}

export interface ProjectSelectionRequest {
  handle: string;
  catalogRevision: string;
}

export interface ProjectSelectionResponse {
  requestId: string;
  selectionRevision: string;
  project: ProjectCatalogItem;
}

export interface ProjectOverviewResponse extends ProjectCatalogItem {
  requestId: string;
  currentRequirements: Record<string, string>[];
  openQuestions: Record<string, string>[];
  tasks: Record<string, string>[];
  blockers: Record<string, string>[];
  risks: Record<string, string>[];
  recentNotes: Record<string, string>[];
  pendingCandidates: Record<string, string>[];
  evidenceCoverage: Record<string, number>;
}

export type GraphNodeType =
  | "Project"
  | "Note"
  | "NoteItem"
  | "Requirement"
  | "Decision"
  | "Question"
  | "Task"
  | "Risk"
  | "Assumption"
  | "Constraint"
  | "ProgressClaim"
  | "ResearchFinding"
  | "Person"
  | "Candidate"
  | "SourceArtifact";
export type GraphRelationType =
  | "implements"
  | "blocks"
  | "dependsOn"
  | "supports"
  | "answers"
  | "resolves"
  | "constrainedBy"
  | "supersedes"
  | "derivedFrom"
  | "hasNoteItem"
  | "belongsToProject"
  | "evidenceFor"
  | "provenanceFor";
export type GraphVerificationState = "candidate" | "asserted" | "inferred" | "unverified";
export type GraphLifecycleState =
  | "current"
  | "pending-review"
  | "confirmed"
  | "rejected"
  | "superseded"
  | "retracted"
  | "stale";
export type GraphProvenanceState =
  | "source-backed"
  | "human-confirmed"
  | "rule-derived"
  | "candidate-proposed";

export interface GraphNode {
  handle: string;
  label: string;
  semanticType: GraphNodeType;
  lifecycleState: GraphLifecycleState;
  verificationState: GraphVerificationState;
  provenanceState: GraphProvenanceState;
  direction?: "source-to-target" | "target-to-source";
  evidenceCount: number;
  projectScope: "selected";
  dates: { validFrom?: string | null; validTo?: string | null; recordedAt?: string | null };
  availableActions: string[];
}
export interface GraphEdge {
  handle: string;
  sourceHandle: string;
  targetHandle: string;
  relationType: GraphRelationType;
  direction: "source-to-target" | "target-to-source";
  verificationState: GraphVerificationState;
  provenanceState: GraphProvenanceState;
  evidenceCount: number;
}
export interface GraphProjectionResponse {
  projectionVersion: "s8.graph.v1";
  requestId: string;
  projectHandle: string;
  sourceRevision: string;
  materializationRevision: string;
  asOf: string;
  stale: boolean;
  partial: boolean;
  nodes: GraphNode[];
  edges: GraphEdge[];
  page: {
    nodeLimit: number;
    edgeLimit: number;
    hasMore: boolean;
    continuation?: string | null;
    expansionAvailable: boolean;
  };
  filters: {
    semanticTypes: string[];
    verificationStates: GraphVerificationState[];
    lifecycleStates: GraphLifecycleState[];
    provenanceStates: GraphProvenanceState[];
    relationTypes: GraphRelationType[];
    evidence: "any" | "with-evidence" | "without-evidence";
  };
}
export interface GraphNodeDetail extends GraphNode {
  requestId?: string;
  projectHandle?: string;
  projectLabel: string;
  summary?: string | null;
  sourceSummary?: string | null;
  freshness: "available" | "unavailable" | "stale";
  relations: {
    relationType: GraphRelationType;
    direction: "source-to-target" | "target-to-source";
    peerHandle: string;
    peerLabel: string;
  }[];
  evidence: string[];
  lifecycle: string[];
}
export interface GraphEvidenceResponse {
  projectionVersion: "s8.graph.v1";
  requestId: string;
  projectHandle: string;
  nodeHandle: string;
  stale: boolean;
  items: Record<string, string | number | null>[];
}
export interface GraphLifecycleResponse {
  projectionVersion: "s8.graph.v1";
  requestId: string;
  projectHandle: string;
  nodeHandle: string;
  stale: boolean;
  items: Record<string, string | null>[];
}
export interface CandidateQueueItem {
  handle: string;
  label: string;
  sourceExcerpt?: string | null;
  proposedType: string;
  proposedRelations: string[];
  validationState: string;
  confidence?: number | null;
  age?: string | null;
  lifecycleState: GraphLifecycleState;
  evidenceCount: number;
}
export interface CandidateQueueResponse {
  requestId: string;
  projectHandle: string;
  sourceRevision: string;
  stale: boolean;
  candidates: CandidateQueueItem[];
  hasMore: boolean;
}
export interface KnowledgeCollectionItem {
  handle: string;
  label: string;
  semanticType: GraphNodeType;
  lifecycleState: GraphLifecycleState;
  verificationState: GraphVerificationState;
  provenanceState: GraphProvenanceState;
  validFrom?: string | null;
  evidenceCount: number;
}
export interface KnowledgeCollectionResponse {
  requestId: string;
  projectHandle: string;
  sourceRevision: string;
  stale: boolean;
  items: KnowledgeCollectionItem[];
  hasMore: boolean;
}

export interface Paths {
  "/v1/projects": { get: { response: ProjectCatalogResponse } };
  "/v1/projects/{handle}": { get: { response: ProjectReadResponse } };
  "/v1/projects/selection": {
    post: { body: ProjectSelectionRequest; response: ProjectSelectionResponse };
  };
  "/v1/projects/{handle}/overview": { get: { response: ProjectOverviewResponse } };
  "/v1/projects/{handle}/graph": { get: { response: GraphProjectionResponse } };
  "/v1/projects/{handle}/graph/neighborhood/{nodeHandle}": {
    get: { response: GraphProjectionResponse };
  };
  "/v1/projects/{handle}/graph/nodes/{nodeHandle}": { get: { response: GraphNodeDetail } };
  "/v1/projects/{handle}/graph/nodes/{nodeHandle}/evidence": {
    get: { response: GraphEvidenceResponse };
  };
  "/v1/projects/{handle}/graph/nodes/{nodeHandle}/lifecycle": {
    get: { response: GraphLifecycleResponse };
  };
  "/v1/projects/{handle}/candidates": { get: { response: CandidateQueueResponse } };
  "/v1/projects/{handle}/candidates/{candidateHandle}/validations": {
    post: { response: ValidationResult };
  };
  "/v1/projects/{handle}/candidates/{candidateHandle}/confirmations": {
    post: { body: ConfirmationRequest; response: DecisionResponse };
  };
  "/v1/projects/{handle}/candidates/{candidateHandle}/rejections": {
    post: { body: RejectionRequest; response: DecisionResponse };
  };
  "/v1/projects/{handle}/knowledge": { get: { response: KnowledgeCollectionResponse } };
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
