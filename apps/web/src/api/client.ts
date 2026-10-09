import type {
  Answer,
  CaptureRequest,
  CaptureResponse,
  CandidateEditOptionsResponse,
  ConnectionCheckRequest,
  ConnectionCheckResponse,
  ConfirmationRequest,
  DecisionResponse,
  ExtractionRequest,
  ExtractionResult,
  InferenceRebuildResponse,
  CandidateHistoryResponse,
  CandidateQueueResponse,
  ReviewAbstainRequest,
  ReviewAbstainResponse,
  ReviewWorkbenchDetailResponse,
  ConnectorCatalogResponse,
  ConnectorInstallation,
  ConnectorInstallationListResponse,
  ConnectorRun,
  ConnectorRunListResponse,
  EvidenceResponse,
  GraphEvidenceResponse,
  GraphLifecycleResponse,
  GraphNodeDetail,
  GraphProjectionResponse,
  KnowledgeCollectionResponse,
  KnowledgeItemsResponse,
  LLMProfileRemove,
  LLMProfileWrite,
  LiveResponse,
  Problem,
  ProjectContextQuestion,
  ProjectCatalogResponse,
  PortableImportApplyResponse,
  PortableImportPreviewResponse,
  PortableImportResultResponse,
  ProjectDeletionPreviewResponse,
  ProjectDeletionResponse,
  ProjectOverviewResponse,
  ProjectReadResponse,
  ProjectSelectionRequest,
  ProjectSelectionResponse,
  ReadyResponse,
  RejectionRequest,
  ValidationResult,
  SettingsProfileResponse,
  StructuredCandidateEditRequest,
  StructuredCandidateEditResponse,
  StructuredNoteDetail,
  StructuredNoteDraftInput,
  StructuredNoteDraftResponse,
  StructuredNoteImportResponse,
  StructuredNoteListResponse,
} from "./generated";
import type {
  ControlledRelationDecisionRequest,
  ControlledRelationRequest,
  LocalSuggestionDecisionRequest,
  LocalSuggestionResponse,
  ManualCaptureApprovalRequest,
  ManualCaptureApprovalResponse,
  ManualCaptureRejectionRequest,
  ManualCaptureRejectionResponse,
  RelationSuggestionTargetsResponse,
} from "./manual-capture";

export class ApiError extends Error {
  readonly problem: Problem;

  constructor(problem: Problem) {
    super(problem.detail);
    this.name = "ApiError";
    this.problem = problem;
  }
}

export interface ProjectArchiveDownload {
  blob: Blob;
  filename: string;
  sha256: string;
  sizeBytes: number;
}

export interface AuthSession {
  requestId: string;
  authenticated: boolean;
  actorId?: string;
  expiresAt?: string;
  projects?: Array<{ projectId: string; roles: string[]; revision: number }>;
}

export class ProjectaApiClient {
  constructor(private readonly baseUrl = "") {}

  async getLiveness(): Promise<LiveResponse> {
    return this.request<LiveResponse>("/health/live", { method: "GET" });
  }

  async getReadiness(): Promise<ReadyResponse> {
    return this.request<ReadyResponse>("/health/ready", { method: "GET" });
  }

  async getAuthSession(): Promise<AuthSession> {
    return this.request<AuthSession>("/v1/auth/session", { method: "GET" });
  }

  async logout(): Promise<AuthSession> {
    return this.request<AuthSession>("/auth/logout", { method: "POST" });
  }

  async listProjects(limit = 50): Promise<ProjectCatalogResponse> {
    return this.request<ProjectCatalogResponse>(`/v1/projects?limit=${limit}`, { method: "GET" });
  }
  async previewPortableImport(file: Blob): Promise<PortableImportPreviewResponse> {
    return this.request<PortableImportPreviewResponse>("/v1/imports/previews", {
      method: "POST",
      rawBody: file,
      contentType: "application/octet-stream",
    });
  }

  async cancelPortableImport(importId: string): Promise<{ requestId: string }> {
    return this.request<{ requestId: string }>(
      `/v1/imports/previews/${encodeURIComponent(importId)}`,
      { method: "DELETE" },
    );
  }

  async applyPortableImport(
    importId: string,
    confirmed: boolean,
  ): Promise<PortableImportApplyResponse> {
    return this.request<PortableImportApplyResponse>(
      `/v1/imports/previews/${encodeURIComponent(importId)}/apply`,
      { method: "POST", body: { confirmed } },
    );
  }

  async previewProjectDeletion(
    projectId: string,
    projectName: string,
  ): Promise<ProjectDeletionPreviewResponse> {
    return this.request<ProjectDeletionPreviewResponse>("/v1/projects/deletion/preview", {
      method: "POST",
      body: { projectId, projectName },
    });
  }

  async deleteProject(
    projectId: string,
    projectName: string,
    typedIdentity: string,
  ): Promise<ProjectDeletionResponse> {
    return this.request<ProjectDeletionResponse>("/v1/projects/deletion/delete", {
      method: "POST",
      body: { projectId, projectName, typedIdentity, confirmed: true },
    });
  }

  async getPortableImportResult(importId: string): Promise<PortableImportResultResponse> {
    return this.request<PortableImportResultResponse>(
      `/v1/imports/${encodeURIComponent(importId)}`,
      { method: "GET" },
    );
  }

  async getConnectorCatalog(): Promise<ConnectorCatalogResponse> {
    return this.request<ConnectorCatalogResponse>("/v1/connectors/catalog", { method: "GET" });
  }

  async listConnectorInstallations(
    projectHandle: string,
    limit = 50,
    offset = 0,
  ): Promise<ConnectorInstallationListResponse> {
    return this.request<ConnectorInstallationListResponse>(
      `/v1/projects/${encodeURIComponent(projectHandle)}/connectors/installations?limit=${limit}&offset=${offset}`,
      { method: "GET" },
    );
  }

  async createConnectorInstallation(
    projectHandle: string,
    payload:
      | { connectorType?: "json-mock"; fixtureReference: string; capabilities: string[] }
      | { connectorType: "teams"; teamsSetupHandle: string; capabilities: string[] }
      | {
          connectorType: "github-public-issues";
          githubSetupHandle: string;
          capabilities: string[];
        },
  ): Promise<ConnectorInstallation> {
    return this.request<ConnectorInstallation>(
      `/v1/projects/${encodeURIComponent(projectHandle)}/connectors/installations`,
      { method: "POST", body: payload },
    );
  }

  async updateConnectorInstallation(
    projectHandle: string,
    installationHandle: string,
    payload: {
      expectedRevision: number;
      fixtureReference?: string;
      teamsSetupHandle?: string;
      githubSetupHandle?: string;
      capabilities?: string[];
    },
  ): Promise<ConnectorInstallation> {
    return this.request<ConnectorInstallation>(
      `/v1/projects/${encodeURIComponent(projectHandle)}/connectors/installations/${encodeURIComponent(installationHandle)}`,
      { method: "PUT", body: payload },
    );
  }

  async setConnectorInstallationEnabled(
    projectHandle: string,
    installationHandle: string,
    enabled: boolean,
    expectedRevision: number,
  ): Promise<ConnectorInstallation> {
    return this.request<ConnectorInstallation>(
      `/v1/projects/${encodeURIComponent(projectHandle)}/connectors/installations/${encodeURIComponent(installationHandle)}/${enabled ? "enable" : "disable"}`,
      { method: "POST", body: { expectedInstallationRevision: expectedRevision } },
    );
  }

  async runConnector(
    projectHandle: string,
    installationHandle: string,
    expectedInstallationRevision: number,
    idempotencyKey: string,
  ): Promise<ConnectorRun> {
    return this.request<ConnectorRun>(
      `/v1/projects/${encodeURIComponent(projectHandle)}/connectors/installations/${encodeURIComponent(installationHandle)}/runs`,
      {
        method: "POST",
        body: { expectedInstallationRevision },
        idempotencyKey,
      },
    );
  }

  async listConnectorRuns(
    projectHandle: string,
    installationHandle: string,
    limit = 50,
  ): Promise<ConnectorRunListResponse> {
    return this.request<ConnectorRunListResponse>(
      `/v1/projects/${encodeURIComponent(projectHandle)}/connectors/installations/${encodeURIComponent(installationHandle)}/runs?limit=${limit}`,
      { method: "GET" },
    );
  }

  async retryConnectorRun(
    projectHandle: string,
    installationHandle: string,
    runHandle: string,
    expectedInstallationRevision: number,
    expectedRunRevision: number,
  ): Promise<ConnectorRun> {
    return this.request<ConnectorRun>(
      `/v1/projects/${encodeURIComponent(projectHandle)}/connectors/installations/${encodeURIComponent(installationHandle)}/runs/${encodeURIComponent(runHandle)}/retry`,
      {
        method: "POST",
        body: { expectedInstallationRevision, expectedRunRevision },
        idempotencyKey: crypto.randomUUID(),
      },
    );
  }

  async readProject(handle: string): Promise<ProjectReadResponse> {
    return this.request<ProjectReadResponse>(`/v1/projects/${encodeURIComponent(handle)}`, {
      method: "GET",
    });
  }

  async selectProject(payload: ProjectSelectionRequest): Promise<ProjectSelectionResponse> {
    return this.request<ProjectSelectionResponse>("/v1/projects/selection", {
      method: "POST",
      body: payload,
    });
  }

  async getProjectOverview(handle: string): Promise<ProjectOverviewResponse> {
    return this.request<ProjectOverviewResponse>(
      `/v1/projects/${encodeURIComponent(handle)}/overview`,
      { method: "GET" },
    );
  }

  async exportProject(handle: string): Promise<ProjectArchiveDownload> {
    const path = `/v1/projects/${encodeURIComponent(handle)}/exports`;
    const { headers, requestId } = makeRequestHeaders("POST", "application/zip");
    headers.set("Content-Type", "application/json");
    const response = await fetch(`${this.baseUrl}${path}`, {
      method: "POST",
      headers,
      body: JSON.stringify({ confirmed: true }),
      credentials: "same-origin",
    });
    const responseRequestId = response.headers.get("X-Request-Id");
    if (!responseRequestId) {
      throw contractError(requestId, "The API response did not include a request ID.");
    }
    const contentType = response.headers.get("content-type") ?? "";
    if (!response.ok) {
      if (
        !contentType.includes("application/json") &&
        !contentType.includes("application/problem+json")
      ) {
        throw contractError(responseRequestId, "The API error response content type is invalid.");
      }
      let body: unknown;
      try {
        body = await response.json();
      } catch {
        throw contractError(responseRequestId, "The API error response was not valid JSON.");
      }
      throw new ApiError(normalizeProblem(body, response.status, responseRequestId));
    }
    if (!contentType.toLowerCase().startsWith("application/zip")) {
      throw contractError(responseRequestId, "The export response content type is invalid.");
    }
    const filenameMatch =
      /^attachment;\s*filename="([a-z0-9][a-z0-9-]{0,62}-export-[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\.projecta)"$/.exec(
        response.headers.get("Content-Disposition") ?? "",
      );
    const filename = filenameMatch?.[1];
    const sha256 = response.headers.get("X-Projecta-Export-SHA256") ?? "";
    const sizeHeader = response.headers.get("X-Projecta-Export-Size-Bytes") ?? "";
    const sizeBytes = Number(sizeHeader);
    if (
      !filename ||
      !/^[0-9a-f]{64}$/.test(sha256) ||
      !/^(0|[1-9][0-9]*)$/.test(sizeHeader) ||
      !Number.isSafeInteger(sizeBytes) ||
      sizeBytes < 1
    ) {
      throw contractError(responseRequestId, "The export response metadata is invalid.");
    }
    const blob = await response.blob();
    if (blob.size !== sizeBytes) {
      throw contractError(
        responseRequestId,
        "The export size did not match its response metadata.",
      );
    }
    return { blob, filename, sha256, sizeBytes };
  }

  async getProjectGraph(
    handle: string,
    filters: {
      nodeLimit?: number;
      edgeLimit?: number;
      semanticTypes?: string[];
      verificationStates?: string[];
      lifecycleStates?: string[];
      provenanceStates?: string[];
      relationTypes?: string[];
      evidence?: "any" | "with-evidence" | "without-evidence";
      projectionRevision?: string;
    } = {},
    signal?: AbortSignal,
  ): Promise<GraphProjectionResponse> {
    const query = new URLSearchParams();
    query.set("nodeLimit", String(filters.nodeLimit ?? 50));
    query.set("edgeLimit", String(filters.edgeLimit ?? 100));
    for (const key of [
      "semanticTypes",
      "verificationStates",
      "lifecycleStates",
      "provenanceStates",
      "relationTypes",
    ] as const) {
      if (filters[key]?.length) query.set(key, filters[key]!.join(","));
    }
    if (filters.evidence) query.set("evidence", filters.evidence);
    if (filters.projectionRevision) query.set("projectionRevision", filters.projectionRevision);
    return this.request<GraphProjectionResponse>(
      `/v1/projects/${encodeURIComponent(handle)}/graph?${query.toString()}`,
      { method: "GET", signal },
    );
  }

  async expandGraphNode(
    handle: string,
    nodeHandle: string,
    projectionRevision?: string,
  ): Promise<GraphProjectionResponse> {
    const query = projectionRevision
      ? `?projectionRevision=${encodeURIComponent(projectionRevision)}`
      : "";
    return this.request<GraphProjectionResponse>(
      `/v1/projects/${encodeURIComponent(handle)}/graph/neighborhood/${encodeURIComponent(nodeHandle)}${query}`,
      { method: "GET" },
    );
  }

  async getGraphNodeDetail(handle: string, nodeHandle: string): Promise<GraphNodeDetail> {
    return this.request<GraphNodeDetail>(
      `/v1/projects/${encodeURIComponent(handle)}/graph/nodes/${encodeURIComponent(nodeHandle)}`,
      { method: "GET" },
    );
  }

  async getGraphEvidence(handle: string, nodeHandle: string): Promise<GraphEvidenceResponse> {
    return this.request<GraphEvidenceResponse>(
      `/v1/projects/${encodeURIComponent(handle)}/graph/nodes/${encodeURIComponent(nodeHandle)}/evidence`,
      { method: "GET" },
    );
  }

  async getGraphLifecycle(handle: string, nodeHandle: string): Promise<GraphLifecycleResponse> {
    return this.request<GraphLifecycleResponse>(
      `/v1/projects/${encodeURIComponent(handle)}/graph/nodes/${encodeURIComponent(nodeHandle)}/lifecycle`,
      { method: "GET" },
    );
  }

  async listCandidateQueue(handle: string, limit = 50): Promise<CandidateQueueResponse> {
    return this.request<CandidateQueueResponse>(
      `/v1/projects/${encodeURIComponent(handle)}/candidates?status=pending-review&limit=${limit}`,
      { method: "GET" },
    );
  }

  async getReviewCandidateDetail(
    projectHandle: string,
    candidateHandle: string,
  ): Promise<ReviewWorkbenchDetailResponse> {
    return this.request<ReviewWorkbenchDetailResponse>(
      `/v1/projects/${encodeURIComponent(projectHandle)}/candidates/${encodeURIComponent(candidateHandle)}/review-detail`,
      { method: "GET" },
    );
  }

  async approveManualCandidate(
    projectHandle: string,
    candidateHandle: string,
    payload: ManualCaptureApprovalRequest,
    idempotencyKey: string,
  ): Promise<ManualCaptureApprovalResponse> {
    return this.request<ManualCaptureApprovalResponse>(
      `/v1/projects/${encodeURIComponent(projectHandle)}/candidates/${encodeURIComponent(candidateHandle)}/manual-approvals`,
      { method: "POST", body: payload, idempotencyKey },
    );
  }

  async rejectManualCandidate(
    projectHandle: string,
    candidateHandle: string,
    payload: ManualCaptureRejectionRequest,
    idempotencyKey: string,
  ): Promise<ManualCaptureRejectionResponse> {
    return this.request<ManualCaptureRejectionResponse>(
      `/v1/projects/${encodeURIComponent(projectHandle)}/candidates/${encodeURIComponent(candidateHandle)}/manual-rejections`,
      { method: "POST", body: payload, idempotencyKey },
    );
  }

  async getLocalSuggestion(
    projectHandle: string,
    candidateHandle: string,
  ): Promise<LocalSuggestionResponse> {
    return this.request<LocalSuggestionResponse>(
      `/v1/projects/${encodeURIComponent(projectHandle)}/candidates/${encodeURIComponent(candidateHandle)}/local-suggestions`,
      { method: "GET" },
    );
  }

  async requestLocalSuggestion(
    projectHandle: string,
    candidateHandle: string,
    retry: boolean,
    idempotencyKey: string,
  ): Promise<LocalSuggestionResponse> {
    return this.request<LocalSuggestionResponse>(
      `/v1/projects/${encodeURIComponent(projectHandle)}/candidates/${encodeURIComponent(candidateHandle)}/local-suggestions`,
      { method: "POST", body: { retry }, idempotencyKey },
    );
  }

  async decideLocalSuggestion(
    projectHandle: string,
    candidateHandle: string,
    suggestionId: string,
    payload: LocalSuggestionDecisionRequest,
    idempotencyKey: string,
  ): Promise<LocalSuggestionResponse> {
    return this.request<LocalSuggestionResponse>(
      `/v1/projects/${encodeURIComponent(projectHandle)}/candidates/${encodeURIComponent(candidateHandle)}/local-suggestions/${encodeURIComponent(suggestionId)}/decisions`,
      { method: "POST", body: payload, idempotencyKey },
    );
  }

  async getRelationSuggestionTargets(
    projectHandle: string,
    candidateHandle: string,
  ): Promise<RelationSuggestionTargetsResponse> {
    return this.request<RelationSuggestionTargetsResponse>(
      `/v1/projects/${encodeURIComponent(projectHandle)}/candidates/${encodeURIComponent(candidateHandle)}/relation-suggestion-targets`,
      { method: "GET" },
    );
  }

  async getControlledRelationSuggestionState(
    projectHandle: string,
    candidateHandle: string,
    payload: ControlledRelationRequest,
  ): Promise<LocalSuggestionResponse> {
    const query = new URLSearchParams({
      targetCandidateHandle: payload.targetCandidateHandle,
      direction: payload.direction,
      mode: payload.mode,
    });
    if (payload.predicate) query.set("predicate", payload.predicate);
    return this.request<LocalSuggestionResponse>(
      `/v1/projects/${encodeURIComponent(projectHandle)}/candidates/${encodeURIComponent(candidateHandle)}/relation-suggestions?${query.toString()}`,
      { method: "GET" },
    );
  }

  async requestControlledRelationSuggestion(
    projectHandle: string,
    candidateHandle: string,
    payload: ControlledRelationRequest,
    idempotencyKey: string,
  ): Promise<LocalSuggestionResponse> {
    return this.request<LocalSuggestionResponse>(
      `/v1/projects/${encodeURIComponent(projectHandle)}/candidates/${encodeURIComponent(candidateHandle)}/relation-suggestions`,
      { method: "POST", body: payload, idempotencyKey },
    );
  }

  async getControlledRelationSuggestion(
    projectHandle: string,
    candidateHandle: string,
    suggestionId: string,
  ): Promise<LocalSuggestionResponse> {
    return this.request<LocalSuggestionResponse>(
      `/v1/projects/${encodeURIComponent(projectHandle)}/candidates/${encodeURIComponent(candidateHandle)}/relation-suggestions/${encodeURIComponent(suggestionId)}`,
      { method: "GET" },
    );
  }

  async decideControlledRelationSuggestion(
    projectHandle: string,
    candidateHandle: string,
    suggestionId: string,
    payload: ControlledRelationDecisionRequest,
    idempotencyKey: string,
  ): Promise<LocalSuggestionResponse> {
    return this.request<LocalSuggestionResponse>(
      `/v1/projects/${encodeURIComponent(projectHandle)}/candidates/${encodeURIComponent(candidateHandle)}/relation-suggestions/${encodeURIComponent(suggestionId)}/decisions`,
      { method: "POST", body: payload, idempotencyKey },
    );
  }

  async abstainSelectedCandidate(
    projectHandle: string,
    candidateHandle: string,
    payload: ReviewAbstainRequest,
    idempotencyKey: string,
  ): Promise<ReviewAbstainResponse> {
    return this.request<ReviewAbstainResponse>(
      `/v1/projects/${encodeURIComponent(projectHandle)}/candidates/${encodeURIComponent(candidateHandle)}/abstentions`,
      { method: "POST", body: payload, idempotencyKey },
    );
  }

  async validateSelectedCandidate(
    projectHandle: string,
    candidateHandle: string,
  ): Promise<ValidationResult> {
    return this.request<ValidationResult>(
      `/v1/projects/${encodeURIComponent(projectHandle)}/candidates/${encodeURIComponent(candidateHandle)}/validations`,
      { method: "POST" },
    );
  }

  async confirmSelectedCandidate(
    projectHandle: string,
    candidateHandle: string,
    payload: ConfirmationRequest,
    idempotencyKey: string,
  ): Promise<DecisionResponse> {
    return this.request<DecisionResponse>(
      `/v1/projects/${encodeURIComponent(projectHandle)}/candidates/${encodeURIComponent(candidateHandle)}/confirmations`,
      { method: "POST", body: payload, idempotencyKey },
    );
  }

  async rejectSelectedCandidate(
    projectHandle: string,
    candidateHandle: string,
    payload: RejectionRequest,
    idempotencyKey: string,
  ): Promise<DecisionResponse> {
    return this.request<DecisionResponse>(
      `/v1/projects/${encodeURIComponent(projectHandle)}/candidates/${encodeURIComponent(candidateHandle)}/rejections`,
      { method: "POST", body: payload, idempotencyKey },
    );
  }

  async listKnowledgeCollection(handle: string, limit = 50): Promise<KnowledgeCollectionResponse> {
    return this.request<KnowledgeCollectionResponse>(
      `/v1/projects/${encodeURIComponent(handle)}/knowledge?type=Requirement&limit=${limit}`,
      { method: "GET" },
    );
  }

  async readLlmProfile(): Promise<SettingsProfileResponse> {
    return this.request<SettingsProfileResponse>("/v1/settings/llm", { method: "GET" });
  }

  async writeLlmProfile(payload: LLMProfileWrite): Promise<SettingsProfileResponse> {
    return this.request<SettingsProfileResponse>("/v1/settings/llm", {
      method: "PUT",
      body: payload,
    });
  }

  async rotateLlmCredential(payload: LLMProfileWrite): Promise<SettingsProfileResponse> {
    return this.request<SettingsProfileResponse>("/v1/settings/llm/rotate", {
      method: "POST",
      body: payload,
    });
  }

  async removeLlmProfile(
    payload: LLMProfileRemove = { confirm: true },
  ): Promise<SettingsProfileResponse> {
    return this.request<SettingsProfileResponse>("/v1/settings/llm", {
      method: "DELETE",
      body: payload,
    });
  }

  async checkLlmConnection(payload: ConnectionCheckRequest = {}): Promise<ConnectionCheckResponse> {
    return this.request<ConnectionCheckResponse>("/v1/settings/llm/connection-check", {
      method: "POST",
      body: payload,
    });
  }

  async extractQuickNote(
    payload: ExtractionRequest,
    idempotencyKey: string,
  ): Promise<ExtractionResult> {
    return this.request<ExtractionResult>("/v1/quick-notes/extractions", {
      method: "POST",
      body: payload,
      idempotencyKey,
    });
  }

  async captureQuickNote(
    payload: CaptureRequest,
    idempotencyKey: string,
  ): Promise<CaptureResponse> {
    return this.request<CaptureResponse>("/v1/quick-notes", {
      method: "POST",
      body: payload,
      idempotencyKey,
    });
  }

  async createNoteDraft(
    projectHandle: string,
    payload: StructuredNoteDraftInput,
    idempotencyKey: string,
  ): Promise<StructuredNoteDraftResponse> {
    return this.request<StructuredNoteDraftResponse>(
      `/v1/projects/${encodeURIComponent(projectHandle)}/notes/drafts`,
      { method: "POST", body: payload, idempotencyKey },
    );
  }

  async updateNoteDraft(
    projectHandle: string,
    draftHandle: string,
    payload: StructuredNoteDraftInput,
    revision: number,
  ): Promise<StructuredNoteDraftResponse> {
    return this.request<StructuredNoteDraftResponse>(
      `/v1/projects/${encodeURIComponent(projectHandle)}/notes/drafts/${encodeURIComponent(draftHandle)}`,
      { method: "PUT", body: payload, headers: { "If-Match": String(revision) } },
    );
  }

  async commitNoteDraft(
    projectHandle: string,
    draftHandle: string,
    idempotencyKey: string,
  ): Promise<StructuredNoteDraftResponse> {
    return this.request<StructuredNoteDraftResponse>(
      `/v1/projects/${encodeURIComponent(projectHandle)}/notes/drafts/${encodeURIComponent(draftHandle)}/commit`,
      { method: "POST", idempotencyKey },
    );
  }

  async listStructuredNotes(
    projectHandle: string,
    limit = 50,
  ): Promise<StructuredNoteListResponse> {
    return this.request<StructuredNoteListResponse>(
      `/v1/projects/${encodeURIComponent(projectHandle)}/notes?limit=${limit}`,
      { method: "GET" },
    );
  }

  async readStructuredNote(
    projectHandle: string,
    noteHandle: string,
  ): Promise<StructuredNoteDetail> {
    return this.request<StructuredNoteDetail>(
      `/v1/projects/${encodeURIComponent(projectHandle)}/notes/${encodeURIComponent(noteHandle)}`,
      { method: "GET" },
    );
  }

  async importNoteText(
    projectHandle: string,
    rawText: string,
    title?: string,
  ): Promise<StructuredNoteImportResponse> {
    return this.request<StructuredNoteImportResponse>(
      `/v1/projects/${encodeURIComponent(projectHandle)}/notes/import`,
      { method: "POST", body: { rawText, ...(title ? { title } : {}) } },
    );
  }

  async editStructuredCandidate(
    projectHandle: string,
    candidateHandle: string,
    payload: StructuredCandidateEditRequest,
  ): Promise<StructuredCandidateEditResponse> {
    return this.request<StructuredCandidateEditResponse>(
      `/v1/projects/${encodeURIComponent(projectHandle)}/candidates/${encodeURIComponent(candidateHandle)}/edits`,
      { method: "POST", body: payload },
    );
  }

  async getCandidateEditOptions(projectHandle: string): Promise<CandidateEditOptionsResponse> {
    return this.request<CandidateEditOptionsResponse>(
      `/v1/projects/${encodeURIComponent(projectHandle)}/candidate-edit-options`,
      { method: "GET" },
    );
  }

  async validateCandidate(candidateId: string): Promise<ValidationResult> {
    return this.request<ValidationResult>(
      `/v1/candidates/${encodeURIComponent(candidateId)}/validations`,
      {
        method: "POST",
      },
    );
  }

  async confirmCandidate(
    candidateId: string,
    payload: ConfirmationRequest,
    idempotencyKey: string,
  ): Promise<DecisionResponse> {
    return this.request<DecisionResponse>(
      `/v1/candidates/${encodeURIComponent(candidateId)}/confirmations`,
      {
        method: "POST",
        body: payload,
        idempotencyKey,
      },
    );
  }

  async rejectCandidate(
    candidateId: string,
    payload: RejectionRequest,
    idempotencyKey: string,
  ): Promise<DecisionResponse> {
    return this.request<DecisionResponse>(
      `/v1/candidates/${encodeURIComponent(candidateId)}/rejections`,
      {
        method: "POST",
        body: payload,
        idempotencyKey,
      },
    );
  }

  async listCurrentKnowledge(type = "Requirement"): Promise<KnowledgeItemsResponse> {
    return this.request<KnowledgeItemsResponse>(
      `/v1/knowledge-items/current?type=${encodeURIComponent(type)}`,
      {
        method: "GET",
      },
    );
  }

  async getCandidateHistory(candidateId: string): Promise<CandidateHistoryResponse> {
    return this.request<CandidateHistoryResponse>(
      `/v1/candidates/${encodeURIComponent(candidateId)}/history`,
      {
        method: "GET",
      },
    );
  }

  async getEvidence(itemId: string): Promise<EvidenceResponse> {
    return this.request<EvidenceResponse>(
      `/v1/knowledge-items/${encodeURIComponent(itemId)}/evidence`,
      {
        method: "GET",
      },
    );
  }

  async answerProjectContext(payload: ProjectContextQuestion): Promise<Answer> {
    return this.request<Answer>("/v1/project-context/answers", { method: "POST", body: payload });
  }

  async rebuildInference(): Promise<InferenceRebuildResponse> {
    return this.request<InferenceRebuildResponse>("/v1/project-context/inference/rebuild", {
      method: "POST",
    });
  }

  private async request<T>(path: string, options: RequestOptions): Promise<T> {
    const { headers, requestId } = makeRequestHeaders(
      options.method,
      "application/json",
      options.headers,
    );
    if (options.rawBody !== undefined) {
      headers.set("Content-Type", options.contentType ?? "application/octet-stream");
    } else if (options.body !== undefined) {
      headers.set("Content-Type", "application/json");
    }
    if (options.idempotencyKey !== undefined)
      headers.set("Idempotency-Key", options.idempotencyKey);
    const response = await fetch(`${this.baseUrl}${path}`, {
      method: options.method,
      headers,
      body:
        options.rawBody ?? (options.body === undefined ? undefined : JSON.stringify(options.body)),
      signal: options.signal,
      credentials: "same-origin",
    });
    const responseRequestId = response.headers.get("X-Request-Id");
    if (!responseRequestId) {
      throw contractError(requestId, "The API response did not include a request ID.");
    }
    const contentType = response.headers.get("content-type") ?? "";
    if (
      !contentType.includes("application/json") &&
      !contentType.includes("application/problem+json")
    ) {
      throw contractError(responseRequestId, "The API response content type is invalid.");
    }
    let body: unknown;
    try {
      body = await response.json();
    } catch {
      throw contractError(responseRequestId, "The API response was not valid JSON.");
    }
    if (!response.ok) {
      throw new ApiError(normalizeProblem(body, response.status, responseRequestId));
    }
    validateSuccess(path, body, responseRequestId);
    return body as T;
  }
}

interface RequestOptions {
  method: "DELETE" | "GET" | "POST" | "PUT";
  body?: unknown;
  headers?: HeadersInit;
  idempotencyKey?: string;
  rawBody?: BodyInit;
  contentType?: string;
  signal?: AbortSignal;
}

function makeRequestHeaders(
  method: RequestOptions["method"],
  accept: string,
  provided?: HeadersInit,
): { headers: Headers; requestId: string } {
  const requestId = crypto.randomUUID();
  const headers = new Headers(provided);
  headers.set("Accept", accept);
  headers.set("X-Request-Id", requestId);
  headers.set("X-Operation-Id", crypto.randomUUID());
  if (method !== "GET" && typeof document !== "undefined") {
    const csrf = document.cookie
      .split(";")
      .map((item) => item.trim())
      .find((item) => item.startsWith("projecta_csrf="))
      ?.slice("projecta_csrf=".length);
    if (csrf) headers.set("X-CSRF-Token", decodeURIComponent(csrf));
  }
  return { headers, requestId };
}

function normalizeProblem(body: unknown, status: number, requestId: string): Problem {
  if (
    typeof body === "object" &&
    body !== null &&
    "type" in body &&
    "title" in body &&
    "status" in body &&
    "code" in body &&
    "detail" in body &&
    "requestId" in body &&
    typeof body.type === "string" &&
    typeof body.title === "string" &&
    body.status === status &&
    typeof body.code === "string" &&
    typeof body.detail === "string" &&
    body.requestId === requestId
  ) {
    return body as Problem;
  }
  throw contractError(
    requestId,
    "The API error response did not match the published problem contract.",
  );
}

function hasProjectCandidateHandles(candidates: unknown): boolean {
  if (!Array.isArray(candidates)) return false;
  return candidates.every((candidate) => {
    if (typeof candidate !== "object" || candidate === null || Array.isArray(candidate)) {
      return false;
    }
    const handle = (candidate as Record<string, unknown>).handle;
    return typeof handle === "string" && /^candidate-h-[0-9a-f]{24}$/.test(handle);
  });
}

function validateSuccess(path: string, body: unknown, requestId: string): void {
  if (typeof body !== "object" || body === null || Array.isArray(body)) {
    throw contractError(requestId, "The API success body is malformed.");
  }
  const value = body as Record<string, unknown>;
  if (path === "/health/live") {
    if (value.status !== "live")
      throw contractError(requestId, "The liveness response is malformed.");
    return;
  }
  if (path === "/health/ready") {
    if (!(["ready", "not-ready"] as unknown[]).includes(value.status)) {
      throw contractError(requestId, "The readiness response is malformed.");
    }
    return;
  }
  if (value.requestId !== requestId) {
    throw contractError(requestId, "The API success response correlation is invalid.");
  }
  if (path === "/v1/projects/" || path.startsWith("/v1/projects?") || path === "/v1/projects") {
    if (!Array.isArray(value.projects) || typeof value.catalogRevision !== "string") {
      throw contractError(requestId, "The project catalog response is malformed.");
    }
  }
  if (path === "/v1/imports/previews") {
    if (
      typeof value.importId !== "string" ||
      typeof value.projectId !== "string" ||
      typeof value.projectName !== "string" ||
      typeof value.exportId !== "string" ||
      typeof value.exportedAt !== "string" ||
      typeof value.archiveSha256 !== "string" ||
      !/^[0-9a-f]{64}$/.test(value.archiveSha256) ||
      typeof value.sizeBytes !== "number" ||
      !Number.isSafeInteger(value.sizeBytes) ||
      !["add-project", "adopt-placeholder", "already-imported", "conflict"].includes(
        String(value.destinationAction),
      ) ||
      typeof value.counts !== "object" ||
      value.counts === null ||
      typeof value.plaintextWarning !== "string"
    ) {
      throw contractError(requestId, "The portable import preview response is malformed.");
    }
  }
  if (path.endsWith("/apply")) {
    if (
      typeof value.projectId !== "string" ||
      typeof value.projectName !== "string" ||
      typeof value.alreadyImported !== "boolean" ||
      typeof value.restartRequired !== "boolean" ||
      (value.importId !== undefined && typeof value.importId !== "string") ||
      (value.status !== undefined && value.status !== "staging") ||
      (value.restartRequired &&
        (typeof value.importId !== "string" || value.status !== "staging")) ||
      (value.nextAction !== undefined && typeof value.nextAction !== "string")
    ) {
      throw contractError(requestId, "The portable import response is malformed.");
    }
  }
  if (path !== "/v1/imports/previews" && /^\/v1\/imports\/[^/]+$/.test(path)) {
    if (
      typeof value.importId !== "string" ||
      !["staging", "complete", "failed"].includes(String(value.status)) ||
      typeof value.projectId !== "string" ||
      typeof value.projectName !== "string" ||
      (value.failureCode !== undefined && typeof value.failureCode !== "string")
    ) {
      throw contractError(requestId, "The portable import result response is malformed.");
    }
  }
  if (path === "/v1/projects/deletion/preview") {
    if (
      typeof value.projectId !== "string" ||
      typeof value.projectName !== "string" ||
      typeof value.graphTriples !== "object" ||
      value.graphTriples === null ||
      typeof value.evidenceObjects !== "number" ||
      !Number.isSafeInteger(value.evidenceObjects) ||
      typeof value.sqliteRows !== "object" ||
      value.sqliteRows === null ||
      typeof value.postgresRows !== "object" ||
      value.postgresRows === null ||
      typeof value.ledgerEntries !== "number" ||
      !Number.isSafeInteger(value.ledgerEntries) ||
      !Array.isArray(value.warnings)
    ) {
      throw contractError(requestId, "The project deletion preview response is malformed.");
    }
  }
  if (path === "/v1/projects/deletion/delete") {
    if (
      typeof value.projectId !== "string" ||
      typeof value.projectName !== "string" ||
      value.outcome !== "deleted" ||
      typeof value.restartRequired !== "boolean" ||
      (value.nextAction !== undefined && typeof value.nextAction !== "string") ||
      typeof value.graphTriplesRemoved !== "number" ||
      typeof value.evidenceObjectsRemoved !== "number" ||
      typeof value.sqliteRowsRemoved !== "number" ||
      typeof value.postgresRowsRemoved !== "number" ||
      typeof value.ledgerEntriesForgotten !== "number" ||
      typeof value.membershipsRemoved !== "number" ||
      !Array.isArray(value.retained)
    ) {
      throw contractError(requestId, "The project deletion response is malformed.");
    }
  }
  if (path.includes("/overview")) {
    if (typeof value.handle !== "string" || !Array.isArray(value.currentRequirements)) {
      throw contractError(requestId, "The project overview response is malformed.");
    }
  }
  if (path === "/v1/projects/selection") {
    if (typeof value.selectionRevision !== "string" || typeof value.project !== "object") {
      throw contractError(requestId, "The project selection response is malformed.");
    }
  }
  if (path.includes("/graph")) {
    if (path.includes("/evidence") || path.includes("/lifecycle")) {
      if (!Array.isArray(value.items))
        throw contractError(requestId, "The graph link response is malformed.");
    } else if (path.includes("/nodes/") && !path.includes("neighborhood")) {
      if (typeof value.handle !== "string" || !Array.isArray(value.relations)) {
        throw contractError(requestId, "The graph detail response is malformed.");
      }
    } else if (
      !Array.isArray(value.nodes) ||
      !Array.isArray(value.edges) ||
      typeof value.stale !== "boolean"
    ) {
      throw contractError(requestId, "The graph projection response is malformed.");
    }
  }
  if (
    path.includes("/candidates?") &&
    (!Array.isArray(value.candidates) || typeof value.stale !== "boolean")
  ) {
    throw contractError(requestId, "The candidate queue response is malformed.");
  }
  if (
    path.includes("/knowledge?") &&
    (!Array.isArray(value.items) || typeof value.stale !== "boolean")
  ) {
    throw contractError(requestId, "The knowledge collection response is malformed.");
  }
  const arrayRoutes = ["/v1/knowledge-items/current", "/v1/candidates/", "/v1/knowledge-items/"];
  if (
    (arrayRoutes.some((prefix) => path.startsWith(prefix)) && path.includes("history")) ||
    path.includes("/evidence") ||
    path.includes("/current")
  ) {
    if (!Array.isArray(value.items))
      throw contractError(requestId, "The API collection response is malformed.");
  }
  if (path.includes("quick-notes")) {
    if (typeof value.note !== "object" || !Array.isArray(value.candidates)) {
      throw contractError(requestId, "The API note response is malformed.");
    }
  }
  if (path === "/v1/quick-notes" && !hasProjectCandidateHandles(value.candidates)) {
    throw contractError(requestId, "The captured candidates do not have project review handles.");
  }
}

function contractError(requestId: string, detail: string): ApiError {
  return new ApiError({
    type: "https://w3id.org/projecta/problems/client-response-invalid",
    title: "Client response contract invalid",
    status: 502,
    code: "CLIENT_RESPONSE_INVALID",
    detail,
    requestId,
  });
}
