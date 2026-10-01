import { expect, test, type Page, type Route } from "@playwright/test";

const project = {
  handle: "project-h-alpha",
  name: "Alpha workspace",
  summary: "Deterministic acceptance workspace",
  status: "active",
  counts: { requirements: 1, tasks: 1, questions: 0, risks: 0, notes: 0, candidates: 1 },
  lastActivityAt: "2026-08-10T00:00:00Z",
  health: "fresh",
  freshness: { state: "current", revision: "source-r1" },
} as const;

const betaProject = {
  handle: "project-h-beta",
  name: "Beta workspace",
  summary: "Isolated acceptance workspace",
  status: "active",
  counts: { requirements: 1, tasks: 0, questions: 0, risks: 0, notes: 0, candidates: 0 },
  lastActivityAt: "2026-08-10T00:00:00Z",
  health: "fresh",
  freshness: { state: "current", revision: "beta-r1" },
} as const;

const navigationProjects = [project, betaProject];

const noteDraft = {
  requestId: "req-note-draft",
  draftHandle: "draft-h-alpha",
  revision: 1,
  title: "Acceptance Note",
  items: [
    {
      itemType: "requirement",
      content: "Use bounded browser journeys.",
      startOffset: 0,
      endOffset: 30,
    },
  ],
  rawText: "Use bounded browser journeys.",
  draftStatus: "ready",
  sourceMetadata: { kind: "manual" },
  committedNoteHandle: null,
};

interface CandidateFixture {
  handle: string;
  label: string;
  sourceExcerpt: string;
  proposedType: string;
  proposedRelations: string[];
  validationState: string;
  confidence: number;
  age: string;
  lifecycleState: string;
  evidenceCount: number;
}

const reviewCandidate: CandidateFixture = {
  handle: "candidate-h-abcdef0123456789abcdef01",
  label: "Review browser journey",
  sourceExcerpt: "Acceptance source",
  proposedType: "Requirement",
  proposedRelations: [],
  validationState: "pending-review",
  confidence: 0.9,
  age: "today",
  lifecycleState: "pending-review",
  evidenceCount: 1,
};

const captureSourceText = "The project owner will review the export before it is shared.";
const capturedCandidate: CandidateFixture = {
  ...reviewCandidate,
  handle: "candidate-h-0123456789abcdef01234567",
  label: captureSourceText,
  sourceExcerpt: captureSourceText,
};

function reviewDetail(candidate: CandidateFixture, manualCapture = false) {
  return {
    detailVersion: "review-workbench.v1",
    requestId: "req-review-detail",
    projectHandle: project.handle,
    itemHandle: candidate.handle,
    projectScope: "selected",
    sourceVersion: {
      revision: 1,
      sourceVersionId: "source-version-h-1",
      canonicalizationVersion: "source-canonical.v1",
      coordinateSystemVersion: "unicode-code-point.v1",
      originalDigest: "source-original-digest",
      canonicalDigest: "source-canonical-digest",
    },
    candidateRevision: 1,
    label: candidate.label,
    semanticType: candidate.proposedType,
    lifecycleState: candidate.lifecycleState,
    validationState: candidate.validationState,
    constrainedContractVersion: "candidate-contract.v1",
    confidence: candidate.confidence,
    sourceText: candidate.sourceExcerpt,
    proposed: { label: candidate.label, semanticType: candidate.proposedType },
    edited: null,
    evidence: {
      status: "selected",
      digest: "evidence-digest",
      highlights: [
        {
          kind: "evidence",
          startOffset: 0,
          endOffset: candidate.sourceExcerpt.length,
          quote: candidate.sourceExcerpt,
          quoteDigest: "evidence-quote-digest",
        },
      ],
    },
    uncertaintyReasons: [],
    stale: false,
    quarantined: false,
    reviewReceipt: {
      state: "not-recorded",
      candidateRevision: 1,
      sourceVersionRevision: 1,
    },
    ...(manualCapture
      ? {
          manualCapture: {
            mode: "human-authored-zero-model",
            entityHandle: "entity-h-captured",
          },
        }
      : {}),
  };
}

function graphNodeDetail(handle: string, label: string) {
  return {
    handle,
    label,
    semanticType: "Requirement",
    lifecycleState: "current",
    verificationState: "asserted",
    provenanceState: "source-backed",
    evidenceCount: 1,
    projectScope: "selected",
    dates: {},
    availableActions: ["open-detail"],
    projectHandle: project.handle,
    projectLabel: project.name,
    freshness: "available",
    relations: [],
    evidence: ["source-backed evidence"],
    lifecycle: ["current"],
  };
}

async function json(route: Route, body: unknown, status = 200) {
  const requestId = route.request().headers()["x-request-id"] ?? "req-fixture";
  const payload =
    typeof body === "object" && body !== null && !Array.isArray(body)
      ? { ...body, requestId }
      : body;
  await route.fulfill({
    status,
    contentType: "application/json",
    headers: { "X-Request-Id": requestId },
    body: JSON.stringify(payload),
  });
}

type CatalogState = "projects" | "empty" | "error";

async function mockProjectNavigationApi(
  page: Page,
  catalogStates: CatalogState[] = ["projects"],
  failSelectionFor?: string,
) {
  let hasSelectedProject = false;
  let postSelectionCatalogRead = 0;
  let isAuthenticated = true;
  await page.route("**/health/live", (route) => void json(route, { status: "live" }));
  await page.route("**/health/ready", (route) => void json(route, { status: "ready" }));
  await page.route("**/auth/logout", async (route) => {
    isAuthenticated = false;
    await json(route, { authenticated: false });
  });
  await page.route("**/v1/**", async (route) => {
    const request = route.request();
    const { pathname } = new URL(request.url());
    if (pathname === "/v1/auth/session" && request.method() === "GET") {
      return json(route, { authenticated: isAuthenticated, subject: "subject-h-project-switch" });
    }
    if (pathname === "/v1/projects" && request.method() === "GET") {
      const state = hasSelectedProject
        ? catalogStates[Math.min(postSelectionCatalogRead, catalogStates.length - 1)] ?? "projects"
        : "projects";
      if (hasSelectedProject) postSelectionCatalogRead += 1;
      if (state === "error") {
        return json(
          route,
          {
            type: "about:blank",
            title: "Project catalog unavailable",
            status: 503,
            detail: "Project catalog is temporarily unavailable.",
            code: "PROJECT_CATALOG_UNAVAILABLE",
          },
          503,
        );
      }
      return json(route, {
        catalogRevision: "catalog-r1",
        projects: state === "empty" ? [] : navigationProjects,
      });
    }
    if (pathname === "/v1/projects/selection" && request.method() === "POST") {
      const { handle } = JSON.parse(request.postData() ?? "{}") as { handle: string };
      const selected = navigationProjects.find((candidate) => candidate.handle === handle);
      if (!selected) {
        return json(
          route,
          {
            type: "about:blank",
            title: "Project selection failed",
            status: 409,
            detail: "The selected project is no longer available.",
            code: "PROJECT_SELECTION_STALE",
          },
          409,
        );
      }
      if (handle === failSelectionFor) {
        return json(
          route,
          {
            type: "about:blank",
            title: "Project selection failed",
            status: 409,
            detail: "The selected project is no longer available.",
            code: "PROJECT_SELECTION_STALE",
          },
          409,
        );
      }
      hasSelectedProject = true;
      return json(route, {
        selectionRevision: `selection-${selected.handle}`,
        project: selected,
      });
    }
    const selected = navigationProjects.find((candidate) =>
      pathname.startsWith(`/v1/projects/${candidate.handle}/`),
    );
    if (selected && pathname.endsWith("/overview")) {
      return json(route, {
        ...selected,
        currentRequirements: [
          {
            handle: `requirement-${selected.handle}`,
            label: `${selected.name} requirement`,
          },
        ],
        openQuestions: [],
        tasks: [],
        blockers: [],
        risks: [],
        recentNotes: [],
        pendingCandidates: [],
        evidenceCoverage: { covered: 1, total: 1 },
      });
    }
    if (selected && pathname.endsWith("/graph")) {
      const label =
        selected.handle === project.handle ? "Alpha-only knowledge" : "Beta-only knowledge";
      return json(route, {
        projectionVersion: "s8.graph.v1",
        projectHandle: selected.handle,
        sourceRevision: `${selected.handle}-source`,
        materializationRevision: `${selected.handle}-materialized`,
        asOf: "2026-08-10T00:00:00Z",
        stale: false,
        partial: false,
        nodes: [
          {
            handle: `node-${selected.handle}`,
            label,
            semanticType: "Requirement",
            lifecycleState: "current",
            verificationState: "asserted",
            provenanceState: "source-backed",
            evidenceCount: 1,
            projectScope: "selected",
            dates: {},
            availableActions: ["open-detail"],
          },
        ],
        edges: [],
        page: {
          nodeLimit: 50,
          edgeLimit: 100,
          hasMore: false,
          continuation: null,
          expansionAvailable: false,
        },
        filters: {
          semanticTypes: [],
          verificationStates: [],
          lifecycleStates: [],
          provenanceStates: [],
          relationTypes: [],
          evidence: "any",
        },
      });
    }
    return json(route, {});
  });
}

async function openAlphaWorkspace(page: Page) {
  await page.goto("/");
  await page
    .getByRole("article")
    .filter({ hasText: "Alpha workspace" })
    .getByRole("button", { name: "Open project" })
    .click();
  await expect(page.getByRole("heading", { name: "Alpha workspace", level: 2 })).toBeVisible();
}

async function mockOverviewRecentNote(page: Page, handle: string, label: string) {
  await page.route(
    `**/v1/projects/${project.handle}/overview`,
    async (route) =>
      json(route, {
        ...project,
        currentRequirements: [],
        openQuestions: [],
        tasks: [],
        blockers: [],
        risks: [],
        recentNotes: [{ handle, label }],
        pendingCandidates: [],
        evidenceCoverage: { covered: 1, total: 1 },
      }),
  );
}

async function mockApi(
  page: Page,
  failGraph = false,
  candidateForQueue: CandidateFixture = reviewCandidate,
) {
  let noteSaved = false;
  let noteCommitted = false;
  await page.route("**/health/live", (route) => void json(route, { status: "live" }));
  await page.route(
    "**/health/ready",
    (route) => void json(route, { status: "ready", semanticCore: "injected" }),
  );
  await page.route("**/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const { pathname } = url;
    if (pathname === "/v1/auth/session" && request.method() === "GET") {
      return json(route, { authenticated: true, subject: "subject-h-browser" });
    }
    if (pathname === "/v1/projects" && request.method() === "GET") {
      return json(route, {
        requestId: "req-catalog",
        catalogRevision: "catalog-r1",
        projects: [project],
      });
    }
    if (pathname === "/v1/projects/selection" && request.method() === "POST") {
      return json(route, { requestId: "req-select", selectionRevision: "selection-r1", project });
    }
    if (pathname === `/v1/projects/${project.handle}/overview`) {
      return json(route, {
        requestId: "req-overview",
        ...project,
        currentRequirements: [{ handle: "node-h-0123456789abcdef01234567", label: "Bounded journey" }],
        openQuestions: [],
        tasks: [],
        blockers: [],
        risks: [],
        recentNotes: [],
        pendingCandidates: [],
        evidenceCoverage: { covered: 1, total: 1 },
      });
    }
    if (pathname === `/v1/projects/${project.handle}/notes` && request.method() === "GET") {
      return json(route, {
        requestId: "req-notes",
        drafts: noteSaved && !noteCommitted ? [noteDraft] : [],
        committed: noteCommitted
          ? [
              {
                handle: "note-h-89abcdef0123456789abcdef",
                title: noteDraft.title,
                author: "Local reviewer",
                recordedAt: "2026-09-29T00:00:00Z",
                itemTypeSummary: ["requirement"],
                evidenceCoverage: 1,
              },
            ]
          : [],
      });
    }
    if (pathname === `/v1/projects/${project.handle}/notes/drafts` && request.method() === "POST") {
      noteSaved = true;
      return json(route, noteDraft, 201);
    }
    if (pathname.includes("/notes/drafts/draft-h-alpha/commit")) {
      noteCommitted = true;
      return json(route, {
        ...noteDraft,
        draftStatus: "committed",
        committedNoteHandle: "note-h-89abcdef0123456789abcdef",
      });
    }
    if (pathname.includes("/notes/drafts/draft-h-alpha")) return json(route, noteDraft);
    if (pathname === `/v1/projects/${project.handle}/notes/note-h-89abcdef0123456789abcdef`) {
      return json(route, {
        noteHandle: "note-h-89abcdef0123456789abcdef",
        title: noteDraft.title,
        rawText: noteDraft.rawText,
        author: "Local reviewer",
        recordedAt: "2026-09-29T00:00:00Z",
        items: noteDraft.items,
        evidenceCoverage: 1,
        candidateState: "not-reviewed",
      });
    }
    if (pathname === `/v1/projects/${project.handle}/notes/import`) {
      return json(route, {
        requestId: "req-import",
        status: "proposed",
        title: "Imported acceptance note",
        proposals: [{ itemType: "task", content: "Review the imported proposal." }],
        relations: [],
        abstentionReason: null,
      });
    }
    if (pathname === `/v1/projects/${project.handle}/graph`) {
      if (failGraph) {
        return json(
          route,
          {
            type: "about:blank",
            title: "Graph unavailable",
            status: 503,
            code: "SEMANTIC_CONTRACT_UNAVAILABLE",
            detail: "The bounded graph projection is temporarily unavailable.",
            requestId: "req-graph-failure",
          },
          503,
        );
      }
      return json(route, {
        projectionVersion: "s8.graph.v1",
        requestId: "req-graph",
        projectHandle: project.handle,
        sourceRevision: "source-r1",
        materializationRevision: "materialized-r1",
        asOf: "2026-08-10T00:00:00Z",
        stale: false,
        partial: false,
        nodes: [
          {
            handle: "node-h-0123456789abcdef01234567",
            label: "Bounded journey",
            semanticType: "Requirement",
            lifecycleState: "current",
            verificationState: "asserted",
            provenanceState: "source-backed",
            evidenceCount: 1,
            projectScope: "selected",
            dates: {},
            availableActions: ["open-detail"],
          },
          {
            handle: "node-h-1123456789abcdef01234567",
            label: "Review acceptance",
            semanticType: "Task",
            lifecycleState: "pending-review",
            verificationState: "candidate",
            provenanceState: "candidate-proposed",
            evidenceCount: 0,
            projectScope: "selected",
            dates: {},
            availableActions: ["open-detail"],
          },
        ],
        edges: [
          {
            handle: "edge-h-1123456789abcdef01234567",
            sourceHandle: "node-h-0123456789abcdef01234567",
            targetHandle: "node-h-1123456789abcdef01234567",
            relationType: "supports",
            direction: "source-to-target",
            verificationState: "asserted",
            provenanceState: "source-backed",
            evidenceCount: 1,
          },
        ],
        page: {
          nodeLimit: 50,
          edgeLimit: 100,
          hasMore: false,
          continuation: null,
          expansionAvailable: false,
        },
        filters: {
          semanticTypes: [],
          verificationStates: [],
          lifecycleStates: [],
          provenanceStates: [],
          relationTypes: [],
          evidence: "any",
        },
      });
    }
    const graphNodeMatch = pathname.match(
      new RegExp(`^/v1/projects/${project.handle}/graph/nodes/([^/]+)$`),
    );
    if (graphNodeMatch) {
      if (graphNodeMatch[1] !== "node-h-0123456789abcdef01234567") {
        return json(
          route,
          {
            type: "about:blank",
            title: "Graph detail unavailable",
            status: 404,
            code: "GRAPH_NODE_NOT_FOUND",
            detail: "The selected item is not available in this project graph.",
            requestId: "req-graph-detail-missing",
          },
          404,
        );
      }
      return json(route, graphNodeDetail("node-h-0123456789abcdef01234567", "Bounded journey"));
    }
    if (pathname === `/v1/projects/${project.handle}/candidates`) {
      return json(route, {
        requestId: "req-candidates",
        projectHandle: project.handle,
        sourceRevision: "source-r1",
        stale: false,
        candidates: [candidateForQueue],
        hasMore: false,
      });
    }
    const reviewDetailMatch = pathname.match(
      new RegExp(`^/v1/projects/${project.handle}/candidates/([^/]+)/review-detail$`),
    );
    if (reviewDetailMatch) {
      const candidate =
        reviewDetailMatch[1] === candidateForQueue.handle ? candidateForQueue : reviewCandidate;
      return json(route, reviewDetail(candidate, candidate.handle === capturedCandidate.handle));
    }
    if (pathname === `/v1/projects/${project.handle}/candidate-edit-options`) {
      return json(route, {
        entityLinks: [
          { handle: "node-h-0123456789abcdef01234567", label: "Bounded journey", type: "Requirement" },
        ],
        assignments: [{ handle: "actor-h-reviewer", label: "Current reviewer" }],
      });
    }
    if (pathname.includes("/candidates/candidate-h-abcdef0123456789abcdef01/edits")) {
      return json(route, {
        candidateHandle: "candidate-h-abcdef0123456789abcdef01",
        revision: 1,
        status: "recorded",
        corrections: JSON.parse(request.postData() ?? "{}"),
      });
    }
    if (pathname.includes("/validations"))
      return json(route, {
        conforms: true,
        validatedAt: "2026-08-10T00:00:00Z",
        violations: [],
        correctionRevision: 1,
        correctionsValidated: true,
        corrections: { type: "Requirement", label: "Review bounded browser journey" },
      });
    if (pathname.includes("/confirmations"))
      return json(route, { decision: "confirmed", candidateHandle: "candidate-h-abcdef0123456789abcdef01" });
    if (pathname.endsWith("/manual-approvals"))
      return json(
        route,
        {
          contractVersion: "manual-capture-approval.v1",
          outcome: "accepted",
          receipt: {
            contractVersion: "review-receipt.v1",
            outcome: "accepted",
            receiptId: "receipt-h-manual-approval",
            projectDigest: "project-digest",
            actorDigest: "actor-digest",
            authorizationDigest: "authorization-digest",
            itemKind: "entity",
            itemHandleDigest: "candidate-digest",
            decision: "confirm",
            candidateRevision: 1,
            sourceVersionDigest: "source-version-digest",
            sourceVersionRevision: 1,
            constrainedContractVersion: "candidate-contract.v1",
            evidenceDigest: "evidence-digest",
            idempotencyDigest: "idempotency-digest",
            sequence: 1,
            occurredAt: "2026-09-29T00:00:00Z",
            receiptDigest: "receipt-digest",
          },
          materializationState: "blocked",
          reasonCode: "MATERIALIZATION_NOT_AUTHORIZED",
        },
        201,
      );
    if (pathname === "/v1/project-context/answers")
      return json(route, {
        text: "The project uses bounded journeys.",
        complete: true,
        abstained: false,
        facts: [],
        citations: [],
        derivation: [],
        warnings: [],
        meta: {},
      });
    return json(route, { requestId: "req-default" });
  });
}

test("project selection, Note lifecycle, graph, review, and Q&A stay ID-free", async ({
  page,
}, testInfo) => {
  await mockApi(page);
  await page.goto("/");
  await page.getByRole("button", { name: "Open project" }).click();
  await expect(page.getByRole("heading", { name: "Alpha workspace" })).toBeVisible();
  const screenshotName =
    testInfo.project.name === "chromium-narrow"
      ? "s8-project-overview-narrow.png"
      : "s8-project-overview-desktop.png";
  await page.screenshot({
    path: testInfo.outputPath(screenshotName),
    fullPage: true,
  });

  await page.getByRole("button", { name: "Bounded journey" }).click();
  await expect(page.getByRole("heading", { name: "Finite knowledge projection" })).toBeVisible();

  await page.locator("button.nav-item").filter({ hasText: "Notes" }).click();
  await page.getByRole("button", { name: "Add typed item" }).click();
  await page.getByLabel("Item 1 content").fill("Use bounded browser journeys.");
  await page.getByRole("button", { name: "Save draft" }).click();
  await expect(page.getByText(/Draft saved/)).toBeVisible();
  await page.getByLabel("Source text").fill("Review the imported proposal.");
  await page.getByRole("button", { name: "Propose items" }).click();
  await expect(page.getByText(/editable proposals loaded/)).toBeVisible();
  await page.getByRole("button", { name: "Commit Note" }).click();
  await expect(page.getByText(/Note committed/)).toBeVisible();

  await page.locator("button.nav-item").filter({ hasText: "Graph" }).click();
  await expect(page.getByRole("heading", { name: "Finite knowledge projection" })).toBeVisible();
  await expect(page.getByRole("table")).toContainText("Bounded journey");
  await page.locator("button.nav-item").filter({ hasText: "Review Queue" }).click();
  await page.getByRole("button", { name: "Review browser journey" }).click();
  await page.getByLabel("Type").selectOption("Requirement");
  await page.getByLabel("Label").fill("Review bounded browser journey");
  await page.getByLabel("Entity link").selectOption("node-h-0123456789abcdef01234567");
  await page.getByLabel("Assignment").selectOption("actor-h-reviewer");
  await page.getByRole("button", { name: "Save correction" }).click();
  await expect(page.getByText(/Correction recorded with provenance/)).toBeVisible();
  await page.getByRole("button", { name: "Validate selected candidate" }).click();
  await expect(page.getByText("Validation passed")).toBeVisible();
  await page.getByRole("button", { name: "Confirm Requirement" }).click();
  await expect(page.getByText(/confirmed/i)).toBeVisible();

  await page.locator("button.nav-item").filter({ hasText: "Q&A" }).click();
  await page.getByLabel("Project question").fill("What does the project use?");
  await page.getByRole("button", { name: "Ask question" }).click();
  await expect(page.getByText("The project uses bounded journeys.")).toBeVisible();
  await expect(page.locator("body")).not.toContainText("node-h-");
  await expect(page.locator("body")).not.toContainText("candidate-h-");
});

test("Graph arrowheads end at target frames across directions and self-relations", async ({ page }) => {
  const nodes = Array.from({ length: 6 }, (_, index) => ({
    handle: `node-h-${String(index + 1).padStart(24, "0")}`,
    label: `Geometry node ${index}`,
    semanticType: "Requirement",
    lifecycleState: "current",
    verificationState: "asserted",
    provenanceState: "source-backed",
    evidenceCount: 1,
    projectScope: "selected",
    dates: {},
    availableActions: ["open-detail"],
  }));
  const connections = [
    [0, 1, "supports"],
    [1, 0, "blocks"],
    [0, 4, "dependsOn"],
    [0, 5, "implements"],
    [2, 2, "derivedFrom"],
    [4, 0, "answers"],
    [5, 0, "resolves"],
    [4, 1, "supersedes"],
    [1, 4, "constrainedBy"],
  ] as const;
  const edges = connections.map(([sourceIndex, targetIndex, relationType], index) => ({
    handle: `edge-h-${String(index + 1).padStart(24, "0")}`,
    sourceHandle: nodes[sourceIndex]!.handle,
    targetHandle: nodes[targetIndex]!.handle,
    relationType,
    direction: "source-to-target",
    verificationState: "asserted",
    provenanceState: "source-backed",
    evidenceCount: 1,
  }));

  await mockApi(page);
  await page.route(/\/v1\/projects\/project-h-alpha\/graph(?:\?.*)?$/, async (route) =>
    json(route, {
      projectionVersion: "s8.graph.v1",
      requestId: "req-graph-arrow-geometry",
      projectHandle: project.handle,
      sourceRevision: "source-r1",
      materializationRevision: "materialized-r1",
      asOf: "2026-08-10T00:00:00Z",
      stale: false,
      partial: false,
      nodes,
      edges,
      page: {
        nodeLimit: 50,
        edgeLimit: 100,
        hasMore: false,
        continuation: null,
        expansionAvailable: false,
      },
      filters: {
        semanticTypes: [],
        verificationStates: [],
        lifecycleStates: [],
        provenanceStates: [],
        relationTypes: [],
        evidence: "any",
      },
    }),
  );
  await openAlphaWorkspace(page);
  await page.locator("button.nav-item").filter({ hasText: "Graph" }).click();
  await expect(page.locator(".graph-edge-label")).toHaveText([
    "supports",
    "blocks",
    "dependsOn",
    "implements",
    "derivedFrom",
    "answers",
    "resolves",
    "supersedes",
    "constrainedBy",
  ]);

  for (const [edgeIndex, targetIndex] of [1, 0, 4, 5, 2, 0, 0, 1, 4].entries()) {
    const geometry = await page
      .locator(".graph-edge-group")
      .nth(edgeIndex)
      .evaluate((group, nodeIndex) => {
        const arrowhead = group.querySelector(".graph-edge-arrowhead");
        const targetFrame = document.querySelectorAll<SVGGraphicsElement>(".graph-node-frame")[
          nodeIndex
        ];
        if (!(arrowhead instanceof SVGPolygonElement) || !targetFrame) return null;

        const bounds = targetFrame.getBBox();
        const points = Array.from(
          { length: arrowhead.points.numberOfItems },
          (_, index) => {
            const point = arrowhead.points.getItem(index);
            return { x: point.x, y: point.y };
          },
        );
        const [tip, ...base] = points;
        const tolerance = 0.1;
        const tipOnTargetBoundary =
          (Math.abs(tip!.x - bounds.x) <= tolerance &&
            tip!.y >= bounds.y - tolerance &&
            tip!.y <= bounds.y + bounds.height + tolerance) ||
          (Math.abs(tip!.x - bounds.x - bounds.width) <= tolerance &&
            tip!.y >= bounds.y - tolerance &&
            tip!.y <= bounds.y + bounds.height + tolerance) ||
          (Math.abs(tip!.y - bounds.y) <= tolerance &&
            tip!.x >= bounds.x - tolerance &&
            tip!.x <= bounds.x + bounds.width + tolerance) ||
          (Math.abs(tip!.y - bounds.y - bounds.height) <= tolerance &&
            tip!.x >= bounds.x - tolerance &&
            tip!.x <= bounds.x + bounds.width + tolerance);
        const baseOutsideTarget = base.length === 2 && base.every((point) =>
          point.x < bounds.x - tolerance ||
          point.x > bounds.x + bounds.width + tolerance ||
          point.y < bounds.y - tolerance ||
          point.y > bounds.y + bounds.height + tolerance,
        );
        const style = getComputedStyle(arrowhead);
        const paintBounds = arrowhead.getBoundingClientRect();
        return {
          tipOnTargetBoundary,
          baseOutsideTarget,
          visible:
            style.visibility === "visible" &&
            style.display !== "none" &&
            style.fill !== "none" &&
            paintBounds.width > 0 &&
            paintBounds.height > 0,
        };
      }, targetIndex);
    expect(geometry).toMatchObject({
      tipOnTargetBoundary: true,
      baseOutsideTarget: true,
      visible: true,
    });
  }
});

test("a Project Overview item opens Graph detail and returns within the same project", async ({
  page,
}) => {
  const graphMutations: string[] = [];
  await mockApi(page);
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.pathname.includes("/graph") && request.method() !== "GET") {
      graphMutations.push(`${request.method()} ${url.pathname}`);
    }
  });
  await openAlphaWorkspace(page);

  await page.getByRole("button", { name: "Bounded journey" }).click();
  await expect(page.getByRole("heading", { name: "Finite knowledge projection" })).toBeVisible();
  await expect(
    page.locator(".graph-selection-context").getByRole("heading", { name: "Bounded journey" }),
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: "Bounded journey" })).toHaveCount(2);
  await expect(page.locator(".graph-screen .detail-grid")).toContainText("Alpha workspace");
  const selectedGraphNode = page.getByRole("button", {
    name: "Bounded journey. Requirement; asserted; current.",
  });
  await expect(selectedGraphNode).toHaveAttribute("aria-pressed", "true");
  await expect(selectedGraphNode.locator(".graph-node-state")).toHaveText("asserted · current");
  await expect(page.locator(".graph-edge-label")).toHaveText("supports");
  await expect(page.locator(".graph-legend")).toContainText("Inferred (dashed outline)");
  await expect(page.locator(".graph-legend")).toContainText("Keyboard focus (dotted outer ring)");
  const graphNodeFrame = selectedGraphNode.locator(".graph-node-frame");
  await selectedGraphNode.hover();
  await expect(graphNodeFrame).toHaveCSS("stroke-width", "4px");
  await selectedGraphNode.focus();
  await page.keyboard.press("Enter");
  await expect(selectedGraphNode.locator(".graph-node-focus-ring")).toHaveCSS("opacity", "1");
  for (const theme of ["light", "dark"] as const) {
    await page.locator("html").evaluate((element, nextTheme) => {
      element.setAttribute("data-theme", nextTheme);
    }, theme);
    await page.waitForTimeout(150);
    const contrast = await page.locator(".graph-screen").evaluate((screen) => {
      const channels = (color: string) => color.match(/[\d.]+/g)?.map(Number) ?? [];
      const blend = (foreground: string, background: number[]) => {
        const [red, green, blue, alpha = 1] = channels(foreground);
        return [
          red * alpha + background[0] * (1 - alpha),
          green * alpha + background[1] * (1 - alpha),
          blue * alpha + background[2] * (1 - alpha),
        ];
      };
      const luminance = (color: number[]) => {
        const linear = color.map((channel) => {
          const value = channel / 255;
          return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
        });
        return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2];
      };
      const ratio = (foreground: string, background: number[]) => {
        const foregroundLuminance = luminance(channels(foreground));
        const backgroundLuminance = luminance(background);
        return (
          (Math.max(foregroundLuminance, backgroundLuminance) + 0.05) /
          (Math.min(foregroundLuminance, backgroundLuminance) + 0.05)
        );
      };
      const wrap = screen.querySelector(".graph-canvas-wrap")!;
      const wrapBackground = channels(getComputedStyle(wrap).backgroundColor);
      const nodeTextRatios = [...screen.querySelectorAll(".graph-node")].flatMap((node) => {
        const frame = node.querySelector(".graph-node-frame")!;
        const nodeBackground = blend(getComputedStyle(frame).fill, wrapBackground);
        return [".graph-node-label", ".graph-node-type", ".graph-node-state"].map((selector) =>
          ratio(getComputedStyle(node.querySelector(selector)!).fill, nodeBackground),
        );
      });
      const edge = screen.querySelector(".graph-edge")!;
      const edgeLabel = screen.querySelector(".graph-edge-label")!;
      const legend = screen.querySelector(".graph-legend")!;
      const pageBackground = channels(getComputedStyle(document.documentElement).backgroundColor);
      const main = document.querySelector(".main-content")!;
      const canvas = screen.querySelector(".graph-canvas-wrap")!;
      return {
        nodeTextRatios,
        edgeContrast: ratio(getComputedStyle(edge).stroke, wrapBackground),
        relationTextContrast: ratio(
          getComputedStyle(edgeLabel).fill,
          channels(getComputedStyle(edgeLabel).stroke),
        ),
        legendTextContrast: ratio(getComputedStyle(legend).color, pageBackground),
        pageWidth: document.documentElement.scrollWidth,
        viewportWidth: innerWidth,
        mainContentWidth: main.clientWidth,
        mainContentScrollWidth: main.scrollWidth,
        canvasWidth: canvas.clientWidth,
        canvasScrollWidth: canvas.scrollWidth,
      };
    });
    expect(contrast.nodeTextRatios.every((value) => value >= 4.5)).toBeTruthy();
    expect(contrast.edgeContrast).toBeGreaterThanOrEqual(3);
    expect(contrast.relationTextContrast).toBeGreaterThanOrEqual(4.5);
    expect(contrast.legendTextContrast).toBeGreaterThanOrEqual(4.5);
    expect(contrast.pageWidth).toBeLessThanOrEqual(contrast.viewportWidth);
    expect(contrast.mainContentScrollWidth).toBeLessThanOrEqual(contrast.mainContentWidth);
    if (contrast.viewportWidth <= 520) {
      expect(contrast.canvasScrollWidth).toBeGreaterThan(contrast.canvasWidth);
    }
  }
  await page.getByRole("button", { name: "Close", exact: true }).click();
  await expect(page.locator(".graph-selection-context")).toHaveCount(0);
  await expect(page.locator(".graph-screen .detail-grid")).toHaveCount(0);

  await page.getByRole("button", { name: "Back to Project Overview", exact: true }).click();
  await expect(
    page.getByRole("navigation", { name: "Primary navigation" }).getByRole("button", {
      name: "Project Overview",
    }),
  ).toHaveAttribute("aria-current", "page");
  await expect(page.getByRole("region", { name: "Active project context" })).toContainText(
    "Alpha workspace",
  );
  expect(graphMutations).toEqual([]);
});

test("an unavailable overview item leaves Graph recovery and project return available", async ({
  page,
}) => {
  await mockApi(page);
  await page.route(`**/v1/projects/${project.handle}/overview`, async (route) => {
    await json(route, {
      ...project,
      currentRequirements: [{ handle: "node-h-aaaaaaaaaaaaaaaaaaaaaaaa", label: "Unavailable overview item" }],
      openQuestions: [],
      tasks: [],
      blockers: [],
      risks: [],
      recentNotes: [],
      pendingCandidates: [],
      evidenceCoverage: { covered: 0, total: 0 },
    });
  });
  await openAlphaWorkspace(page);

  await page.getByRole("button", { name: "Unavailable overview item" }).click();
  await expect(page.getByRole("alert")).toContainText("Request ID:");
  await expect(
    page.locator(".graph-selection-context").getByRole("heading", {
      name: "Unavailable overview item",
    }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Browse Graph" }).click();
  await expect(page.locator(".graph-selection-context")).toHaveCount(0);
  await page.getByRole("button", { name: "Back to Project Overview", exact: true }).click();
  await expect(
    page.getByRole("navigation", { name: "Primary navigation" }).getByRole("button", {
      name: "Project Overview",
    }),
  ).toHaveAttribute("aria-current", "page");
  await expect(page.getByRole("region", { name: "Active project context" })).toContainText(
    "Alpha workspace",
  );
});

test("an unavailable Graph projection supports return to Project Overview", async ({ page }) => {
  await mockApi(page, true);
  await page.goto("/");
  await page.getByRole("button", { name: "Open project" }).click();
  await page.locator("button.nav-item").filter({ hasText: "Graph" }).click();
  await expect(page.getByRole("alert")).toContainText("Request ID:");
  await page.getByRole("button", { name: "Back to Project Overview", exact: true }).click();
  await expect(
    page.getByRole("navigation", { name: "Primary navigation" }).getByRole("button", {
      name: "Project Overview",
    }),
  ).toHaveAttribute("aria-current", "page");
  await expect(page.getByRole("region", { name: "Active project context" })).toContainText(
    "Alpha workspace",
  );
});

test("project selection stays outside workspace navigation and switching preserves isolation", async ({
  page,
}) => {
  await mockProjectNavigationApi(page);
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Projects", level: 2 })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Primary navigation" })).toHaveCount(0);
  await page
    .getByRole("article")
    .filter({ hasText: "Alpha workspace" })
    .getByRole("button", { name: "Open project" })
    .click();
  const activeProject = page.getByRole("region", { name: "Active project context" });
  const navigation = page.getByRole("navigation", { name: "Primary navigation" });
  await expect(activeProject).toContainText("Alpha workspace");
  await expect(navigation.getByRole("button", { name: "Projects", exact: true })).toHaveCount(0);
  await navigation.getByRole("button", { name: "Graph", exact: true }).click();
  await expect(page.locator(".graph-node-label")).toHaveText("Alpha-only knowledge");
  await expect(activeProject).toContainText("Alpha workspace");

  await page.getByRole("button", { name: "Change project" }).click();
  await expect(page.getByRole("heading", { name: "Projects", level: 2 })).toBeVisible();
  await expect(navigation).toHaveCount(0);
  await expect(activeProject).toHaveCount(0);
  await expect(page.locator(".graph-node-label")).toHaveCount(0);

  await page
    .getByRole("article")
    .filter({ hasText: "Beta workspace" })
    .getByRole("button", { name: "Open project" })
    .click();
  await expect(activeProject).toContainText("Beta workspace");
  await navigation.getByRole("button", { name: "Graph", exact: true }).click();
  await expect(page.locator(".graph-node-label")).toHaveText("Beta-only knowledge");
  await expect(page.locator("body")).not.toContainText("Alpha-only knowledge");
});

test("session chrome stays available throughout project switching", async ({ page }) => {
  await mockProjectNavigationApi(page);
  const sessionStatus = page.getByRole("status").filter({ hasText: "Signed in" });
  const signOut = page.getByRole("button", { name: "Sign out" });

  await page.goto("/");
  await expect(sessionStatus).toBeVisible();
  await expect(signOut).toBeVisible();
  await openAlphaWorkspace(page);
  await expect(sessionStatus).toBeVisible();
  await expect(signOut).toBeVisible();

  await page.getByRole("button", { name: "Change project" }).click();
  await expect(page.getByRole("heading", { name: "Projects", level: 2 })).toBeVisible();
  await expect(sessionStatus).toBeVisible();
  await expect(signOut).toBeVisible();
  await page
    .getByRole("article")
    .filter({ hasText: "Beta workspace" })
    .getByRole("button", { name: "Open project" })
    .click();
  await expect(page.getByRole("region", { name: "Active project context" })).toContainText(
    "Beta workspace",
  );
  await expect(sessionStatus).toBeVisible();
  await expect(signOut).toBeVisible();

  const viewport = await page.evaluate(() => ({
    documentWidth: document.documentElement.scrollWidth,
    viewportWidth: window.innerWidth,
  }));
  expect(viewport.documentWidth).toBeLessThanOrEqual(viewport.viewportWidth);
});

test("signing out from a workspace returns to sign-in without project content", async ({ page }) => {
  await mockProjectNavigationApi(page);
  await openAlphaWorkspace(page);
  await page.getByRole("button", { name: "Graph", exact: true }).click();
  await expect(page.locator(".graph-node-label")).toHaveText("Alpha-only knowledge");

  await page.getByRole("button", { name: "Sign out" }).click();

  await expect(page.getByRole("heading", { name: "Sign in to continue" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Active project context" })).toHaveCount(0);
  await expect(page.getByRole("navigation", { name: "Primary navigation" })).toHaveCount(0);
  await expect(page.getByText("Alpha-only knowledge", { exact: true })).toHaveCount(0);
});

test("an empty catalog after changing projects does not retain the previous workspace", async ({
  page,
}) => {
  await mockProjectNavigationApi(page, ["empty"]);
  await openAlphaWorkspace(page);
  await page.getByRole("button", { name: "Graph", exact: true }).click();
  await expect(page.locator(".graph-node-label")).toHaveText("Alpha-only knowledge");
  await page.getByRole("button", { name: "Change project" }).click();
  await expect(page.getByText("No authorized projects")).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Primary navigation" })).toHaveCount(0);
  await expect(page.getByRole("region", { name: "Active project context" })).toHaveCount(0);
});

test("a catalog error after changing projects offers retry without restoring the old project", async ({
  page,
}) => {
  await mockProjectNavigationApi(page, ["error"]);
  await openAlphaWorkspace(page);
  await page.getByRole("button", { name: "Graph", exact: true }).click();
  await expect(page.locator(".graph-node-label")).toHaveText("Alpha-only knowledge");
  await page.getByRole("button", { name: "Change project" }).click();
  await expect(page.getByRole("alert")).toContainText("Project catalog is temporarily unavailable.");
  await expect(page.getByRole("status").filter({ hasText: "Signed in" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Primary navigation" })).toHaveCount(0);
  await expect(page.getByRole("region", { name: "Active project context" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Retry catalog" })).toBeVisible();
});

test("a failed project switch leaves the chooser unselected", async ({ page }) => {
  await mockProjectNavigationApi(page, ["projects"], betaProject.handle);
  await openAlphaWorkspace(page);
  await page.getByRole("button", { name: "Graph", exact: true }).click();
  await expect(page.locator(".graph-node-label")).toHaveText("Alpha-only knowledge");
  await page.getByRole("button", { name: "Change project" }).click();
  await page
    .getByRole("article")
    .filter({ hasText: "Beta workspace" })
    .getByRole("button", { name: "Open project" })
    .click();
  await expect(page.getByRole("alert")).toContainText(
    "The selected project is no longer available.",
  );
  await expect(page.getByRole("heading", { name: "Projects", level: 2 })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Primary navigation" })).toHaveCount(0);
  await expect(page.getByRole("region", { name: "Active project context" })).toHaveCount(0);
  await expect(page.locator(".graph-node-label")).toHaveCount(0);
});

test("Notes exposes separate authoring, assisted, and exact-span actions", async ({ page }) => {
  await mockApi(page);
  await openAlphaWorkspace(page);
  await page.locator("button.nav-item").filter({ hasText: "Notes" }).click();
  await expect(page.getByRole("heading", { name: "Notes", level: 2 })).toBeVisible();

  const paths = page.getByRole("article");
  await expect(paths).toHaveCount(3);
  await expect(paths.nth(0).getByRole("link", { name: "Open Note Composer" })).toBeVisible();
  await expect(paths.nth(1).getByRole("link", { name: "Open Assisted import" })).toBeVisible();
  await expect(paths.nth(2).getByRole("button", { name: "Capture exact spans" })).toBeVisible();

  await page.getByRole("link", { name: "Open Note Composer" }).click();
  await expect(page.locator("#note-composer")).toBeInViewport();
  await page.getByRole("link", { name: "Open Assisted import" }).click();
  await expect(page.locator("#assisted-import")).toBeInViewport();
  await page.getByRole("button", { name: "Capture exact spans" }).click();
  await expect(page.getByRole("heading", { name: "Capture exact spans", level: 2 })).toBeVisible();
  await expect(page.getByRole("button", { name: "Back to Notes" })).toBeVisible();
});

test("authored Notes travel through save, commit, source detail, and workspace return", async ({
  page,
}) => {
  await mockApi(page);
  await openAlphaWorkspace(page);
  await page.locator("button.nav-item").filter({ hasText: "Notes" }).click();

  await page.getByLabel("Human title").fill("Acceptance Note");
  await page.getByRole("button", { name: "Add typed item" }).click();
  await page.getByLabel("Item 1 content").fill("Use bounded browser journeys.");
  await page.getByRole("button", { name: "Save draft" }).click();
  await expect(page.getByRole("button", { name: /Acceptance Note/ })).toBeVisible();

  await page.getByRole("button", { name: "Commit Note" }).click();
  const savedNote = page.getByRole("button", { name: /Acceptance Note/ });
  await expect(savedNote).toBeVisible();
  await savedNote.click();
  await expect(page.locator(".note-detail")).toContainText("Use bounded browser journeys.");
  await expect(page.locator(".evidence-row")).toContainText("0–30");
  await page.getByRole("button", { name: "Close detail" }).click();

  await page
    .getByRole("navigation", { name: "Primary navigation" })
    .getByRole("button", { name: "Project Overview" })
    .click();
  await expect(
    page.getByRole("navigation", { name: "Primary navigation" }).getByRole("button", {
      name: "Project Overview",
    }),
  ).toHaveAttribute("aria-current", "page");
  await expect(page.getByRole("region", { name: "Active project context" })).toContainText(
    "Alpha workspace",
  );
});

test("unfinished capture survives return to Notes and can be explicitly discarded", async ({
  page,
}) => {
  let captureRequests = 0;
  await mockApi(page);
  page.on("request", (request) => {
    if (new URL(request.url()).pathname === "/v1/quick-notes") captureRequests += 1;
  });
  await openAlphaWorkspace(page);
  await page.locator("button.nav-item").filter({ hasText: "Notes" }).click();
  await page.getByRole("button", { name: "Capture exact spans" }).click();

  const sourceField = page.getByLabel("Capture note");
  await sourceField.fill(captureSourceText);
  await sourceField.press("Control+A");
  await page.getByRole("button", { name: "Add selected span" }).click();
  await page.getByRole("button", { name: "Back to Notes" }).click();
  await expect(page.getByRole("button", { name: "Continue capture" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Discard unsubmitted capture" })).toBeVisible();

  await page.getByRole("button", { name: "Continue capture" }).click();
  await expect(page.getByLabel("Capture note")).toHaveValue(captureSourceText);
  await expect(page.locator(".segment")).toContainText(captureSourceText);
  await page.getByRole("button", { name: "Back to Notes" }).click();
  await page.getByRole("button", { name: "Discard unsubmitted capture" }).click();
  await expect(page.getByRole("button", { name: "Continue capture" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Discard unsubmitted capture" })).toHaveCount(0);

  await page.getByRole("button", { name: "Capture exact spans" }).click();
  await expect(page.getByLabel("Capture note")).toHaveValue("");
  await expect(page.locator(".segment")).toHaveCount(0);

  await sourceField.fill(captureSourceText);
  await sourceField.press("Control+A");
  await page.getByRole("button", { name: "Add selected span" }).click();
  await page.getByRole("button", { name: "Back to Notes" }).click();
  await page.getByRole("button", { name: "Change project" }).click();
  await expect(page.getByRole("heading", { name: "Projects", level: 2 })).toBeVisible();
  await page.getByRole("button", { name: "Open project" }).click();
  await page.locator("button.nav-item").filter({ hasText: "Notes" }).click();
  await expect(page.getByRole("button", { name: "Continue capture" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Discard unsubmitted capture" })).toHaveCount(0);
  await page.getByRole("button", { name: "Capture exact spans" }).click();
  await expect(sourceField).toHaveValue("");
  await expect(page.locator(".segment")).toHaveCount(0);
  expect(captureRequests).toBe(0);
});

test("capture opens the exact candidate for source-first review and explicit outcome", async ({
  page,
}) => {
  let submittedCapture: unknown = null;
  let approvalPayload: unknown = null;
  const graphMutations: string[] = [];
  await mockApi(page, false, capturedCandidate);
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.pathname.endsWith("/manual-approvals")) {
      approvalPayload = request.postDataJSON();
    }
    if (url.pathname.includes("/graph") && request.method() !== "GET") {
      graphMutations.push(`${request.method()} ${url.pathname}`);
    }
  });
  await page.route("**/v1/quick-notes", async (route) => {
    submittedCapture = route.request().postDataJSON();
    await json(
      route,
      {
        note: { id: "note-h-captured", recordedAt: "2026-09-29T00:00:00Z" },
        candidates: [
          {
            id: "capture-core-candidate-id",
            handle: capturedCandidate.handle,
            status: "pending-review",
          },
        ],
      },
      201,
    );
  });
  await openAlphaWorkspace(page);
  await page.locator("button.nav-item").filter({ hasText: "Notes" }).click();
  await page.getByRole("button", { name: "Capture exact spans" }).click();

  const sourceField = page.getByLabel("Capture note");
  await sourceField.fill(captureSourceText);
  await sourceField.press("Control+A");
  await expect(page.getByRole("button", { name: "Add selected span" })).toBeEnabled();
  await page.getByRole("button", { name: "Add selected span" }).click();
  await expect(page.locator(".segment")).toContainText(captureSourceText);
  await expect(page.locator(".segment")).toContainText(`0–${captureSourceText.length}`);
  await page.getByRole("button", { name: "Capture note" }).click();
  const openReview = page.getByRole("button", { name: "Open Review Queue · pending-review" });
  await expect(openReview).toBeVisible();
  expect(submittedCapture).toMatchObject({
    rawText: captureSourceText,
    segments: [
      {
        type: "requirement",
        startOffset: 0,
        endOffset: captureSourceText.length,
        text: captureSourceText,
      },
    ],
  });

  await openReview.click();
  const candidateRow = page.getByRole("button", { name: new RegExp(captureSourceText) });
  await expect(candidateRow).toHaveAttribute("aria-current", "true");
  await expect(page.locator(".source-quote")).toHaveText(captureSourceText);
  await expect(page.getByText("Source revision")).toBeVisible();
  await expect(page.getByRole("button", { name: "Record manual approval" })).toHaveCount(0);
  await page.getByRole("button", { name: "Validate selected candidate" }).click();
  await expect(page.getByText("Validation passed")).toBeVisible();
  await page.getByRole("button", { name: "Record manual approval" }).click();
  await expect(page.getByText(/receipt-digest/)).toBeVisible();
  expect(approvalPayload).toMatchObject({
    sourceVersionId: "source-version-h-1",
    sourceVersionRevision: 1,
    anchorQuoteDigest: "evidence-quote-digest",
  });
  expect(graphMutations).toEqual([]);
});

test("an unresolved captured candidate does not select a different review item", async ({
  page,
}) => {
  await mockApi(page);
  await page.route("**/v1/quick-notes", async (route) => {
    await json(
      route,
      {
        note: { id: "note-h-captured", recordedAt: "2026-09-29T00:00:00Z" },
        candidates: [
          {
            id: "capture-core-candidate-id-unlisted",
            handle: "candidate-h-aaaaaaaaaaaaaaaaaaaaaaaa",
            status: "pending-review",
          },
        ],
      },
      201,
    );
  });
  await openAlphaWorkspace(page);
  await page.locator("button.nav-item").filter({ hasText: "Notes" }).click();
  await page.getByRole("button", { name: "Capture exact spans" }).click();
  const sourceField = page.getByLabel("Capture note");
  await sourceField.fill(captureSourceText);
  await sourceField.press("Control+A");
  await page.getByRole("button", { name: "Add selected span" }).click();
  await page.getByRole("button", { name: "Capture note" }).click();
  await page.getByRole("button", { name: /Open Review Queue/ }).click();
  const missingCandidateAlert = page.getByText(
    /The candidate opened from Notes is not present in this project's pending queue/,
  );
  await expect(missingCandidateAlert).toBeVisible();
  await page.getByRole("button", { name: "Refresh" }).click();
  await expect(missingCandidateAlert).toBeVisible();

  const otherCandidate = page.getByRole("button", { name: "Review browser journey" });
  await expect(otherCandidate).not.toHaveAttribute("aria-current", "true");
  await otherCandidate.click();
  await expect(otherCandidate).toHaveAttribute("aria-current", "true");
  await expect(page.locator(".source-quote")).toHaveText("Acceptance source");
  await expect(missingCandidateAlert).toHaveCount(0);
});

test("review correction waits for the selected candidate source detail", async ({ page }) => {
  let releaseDetail!: () => void;
  let notifyDetailRequested!: () => void;
  const detailGate = new Promise<void>((resolve) => {
    releaseDetail = resolve;
  });
  const detailRequested = new Promise<void>((resolve) => {
    notifyDetailRequested = resolve;
  });
  await mockApi(page);
  await page.route(
    `**/v1/projects/${project.handle}/candidates/${reviewCandidate.handle}/review-detail`,
    async (route) => {
      notifyDetailRequested();
      await detailGate;
      await json(route, reviewDetail(reviewCandidate));
    },
  );
  await openAlphaWorkspace(page);
  await page.locator("button.nav-item").filter({ hasText: "Review Queue" }).click();
  await page.getByRole("button", { name: reviewCandidate.label }).click();
  await detailRequested;

  const saveCorrection = page.getByRole("button", { name: "Save correction" });
  await expect(saveCorrection).toBeDisabled();
  releaseDetail();
  await expect(saveCorrection).toBeEnabled();
  await expect(page.locator(".source-quote")).toHaveText(reviewCandidate.sourceExcerpt);
});

test("exact-span validation and capture request errors do not offer a review action", async ({
  page,
}) => {
  await mockApi(page);
  await page.route("**/v1/quick-notes", async (route) => {
    await json(
      route,
      {
        type: "about:blank",
        title: "Capture unavailable",
        status: 503,
        code: "SEMANTIC_CONTRACT_UNAVAILABLE",
        detail: "The capture service is temporarily unavailable.",
        requestId: "req-capture-failure",
      },
      503,
    );
  });
  await openAlphaWorkspace(page);
  await page.locator("button.nav-item").filter({ hasText: "Notes" }).click();
  await page.getByRole("button", { name: "Capture exact spans" }).click();

  const sourceText = "The project owner will review the export before it is shared.";
  const sourceField = page.getByLabel("Capture note");
  await sourceField.fill(sourceText);
  const selectSource = async () => {
    await sourceField.press("Control+A");
    await expect(page.getByRole("button", { name: "Add selected span" })).toBeEnabled();
  };
  await selectSource();
  await page.getByRole("button", { name: "Add selected span" }).click();
  await selectSource();
  await page.getByRole("button", { name: "Add selected span" }).click();
  await expect(page.getByRole("alert")).toBeVisible();
  await expect(page.locator(".segment")).toHaveCount(1);

  await page.getByRole("button", { name: "Capture note" }).click();
  await expect(page.getByRole("alert")).toBeVisible();
  await expect(page.getByRole("alert")).toContainText("Request ID:");
  await expect(page.getByRole("button", { name: /Open Review Queue/ })).toHaveCount(0);
  await expect(page.locator(".segment")).toContainText(sourceText);
});

test("Project Overview recent Note opens the exact source detail and returns", async ({ page }) => {
  await mockApi(page);
  await mockOverviewRecentNote(page, "note-h-89abcdef0123456789abcdef", noteDraft.title);
  await openAlphaWorkspace(page);

  await page.getByRole("button", { name: noteDraft.title }).click();
  const selectedNote = page.locator(".note-selection-context");
  await expect(selectedNote.locator(".note-detail")).toContainText(noteDraft.rawText);
  await expect(selectedNote.locator(".note-detail")).toContainText("Local reviewer");
  await expect(selectedNote.locator(".note-detail")).toContainText("0–30");

  await selectedNote.getByRole("button", { name: "Back to Project Overview" }).click();
  await expect(
    page.getByRole("navigation", { name: "Primary navigation" }).getByRole("button", {
      name: "Project Overview",
    }),
  ).toHaveAttribute("aria-current", "page");
  await expect(page.getByRole("heading", { name: "Alpha workspace", level: 2 })).toBeVisible();
});

test("a missing Overview Note stays explicit and can return to its project", async ({ page }) => {
  await mockApi(page);
  await mockOverviewRecentNote(page, "note-h-aaaaaaaaaaaaaaaaaaaaaaaa", "Recently listed Note");
  await page.route(
    `**/v1/projects/${project.handle}/notes/note-h-aaaaaaaaaaaaaaaaaaaaaaaa`,
    async (route) =>
      json(
        route,
        {
          type: "about:blank",
          title: "Note not found",
          status: 404,
          detail: "No committed Note with this handle is available in the selected project.",
          code: "STRUCTURED_NOTE_NOT_FOUND",
        },
        404,
      ),
  );
  await openAlphaWorkspace(page);

  await page.getByRole("button", { name: "Recently listed Note" }).click();
  const selectedNote = page.locator(".note-selection-context");
  await expect(selectedNote).toContainText("The selected Note could not be found in this project.");
  await expect(selectedNote.getByRole("alert")).toContainText("Request ID:");
  await selectedNote.getByRole("button", { name: "Retry selected Note" }).click();
  await expect(selectedNote).toContainText("The selected Note could not be found in this project.");
  await selectedNote.getByRole("button", { name: "Back to Project Overview" }).click();
  await expect(page.getByRole("heading", { name: "Alpha workspace", level: 2 })).toBeVisible();
});

test("an unavailable Overview Note reports its error without replacing it", async ({ page }) => {
  await mockApi(page);
  await mockOverviewRecentNote(page, "note-h-bbbbbbbbbbbbbbbbbbbbbbbb", "Temporarily unavailable Note");
  await page.route(
    `**/v1/projects/${project.handle}/notes/note-h-bbbbbbbbbbbbbbbbbbbbbbbb`,
    async (route) =>
      json(
        route,
        {
          type: "about:blank",
          title: "Note service unavailable",
          status: 503,
          detail: "The Note detail service is temporarily unavailable.",
          code: "SEMANTIC_CONTRACT_UNAVAILABLE",
        },
        503,
      ),
  );
  await openAlphaWorkspace(page);

  await page.getByRole("button", { name: "Temporarily unavailable Note" }).click();
  const selectedNote = page.locator(".note-selection-context");
  await expect(selectedNote).toContainText("The selected Note could not be loaded.");
  await expect(selectedNote.getByRole("alert")).toContainText("Request ID:");
  await selectedNote.getByRole("button", { name: "Back to Project Overview" }).click();
  await expect(page.getByRole("heading", { name: "Alpha workspace", level: 2 })).toBeVisible();
});
