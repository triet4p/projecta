import type {
  Answer,
  CaptureRequest,
  CaptureResponse,
  ConnectionCheckRequest,
  ConnectionCheckResponse,
  ConfirmationRequest,
  DecisionResponse,
  ExtractionRequest,
  ExtractionResult,
  InferenceRebuildResponse,
  CandidateHistoryResponse,
  EvidenceResponse,
  KnowledgeItemsResponse,
  LLMProfileRemove,
  LLMProfileWrite,
  LiveResponse,
  Problem,
  ProjectContextQuestion,
  ReadyResponse,
  RejectionRequest,
  ValidationResult,
  SettingsProfileResponse,
} from "./generated";

export class ApiError extends Error {
  readonly problem: Problem;

  constructor(problem: Problem) {
    super(problem.detail);
    this.name = "ApiError";
    this.problem = problem;
  }
}

export class ProjectaApiClient {
  constructor(private readonly baseUrl = "") {}

  async getLiveness(): Promise<LiveResponse> {
    return this.request<LiveResponse>("/health/live", { method: "GET" });
  }

  async getReadiness(): Promise<ReadyResponse> {
    return this.request<ReadyResponse>("/health/ready", { method: "GET" });
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
    const requestId = crypto.randomUUID();
    const headers = new Headers(options.headers);
    headers.set("Accept", "application/json");
    headers.set("X-Request-Id", requestId);
    if (options.body !== undefined) headers.set("Content-Type", "application/json");
    if (options.idempotencyKey !== undefined)
      headers.set("Idempotency-Key", options.idempotencyKey);
    const response = await fetch(`${this.baseUrl}${path}`, {
      method: options.method,
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    });
    const body: unknown = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new ApiError(
        normalizeProblem(body, response.status, response.headers.get("X-Request-Id") ?? requestId),
      );
    }
    return body as T;
  }
}

interface RequestOptions {
  method: "DELETE" | "GET" | "POST" | "PUT";
  body?: unknown;
  headers?: HeadersInit;
  idempotencyKey?: string;
}

function normalizeProblem(body: unknown, status: number, requestId: string): Problem {
  if (typeof body === "object" && body !== null && "code" in body && "detail" in body) {
    return body as Problem;
  }
  return {
    type: "about:blank",
    title: "Request failed",
    status,
    code: "HTTP_ERROR",
    detail: "The Application API returned an unexpected error.",
    requestId,
  };
}
