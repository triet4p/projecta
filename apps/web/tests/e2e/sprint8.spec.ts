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

async function mockApi(page: Page, failGraph = false) {
  await page.route("**/health/live", (route) => void json(route, { status: "live" }));
  await page.route(
    "**/health/ready",
    (route) => void json(route, { status: "ready", semanticCore: "injected" }),
  );
  await page.route("**/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const { pathname } = url;
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
        currentRequirements: [{ handle: "node-h-requirement", label: "Bounded journey" }],
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
      return json(route, { requestId: "req-notes", drafts: [], committed: [] });
    }
    if (pathname === `/v1/projects/${project.handle}/notes/drafts` && request.method() === "POST") {
      return json(route, noteDraft, 201);
    }
    if (pathname.includes("/notes/drafts/draft-h-alpha/commit")) {
      return json(route, {
        ...noteDraft,
        draftStatus: "committed",
        committedNoteHandle: "note-h-alpha",
      });
    }
    if (pathname.includes("/notes/drafts/draft-h-alpha")) return json(route, noteDraft);
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
            handle: "node-h-requirement",
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
    if (pathname === `/v1/projects/${project.handle}/candidates`) {
      return json(route, {
        requestId: "req-candidates",
        projectHandle: project.handle,
        sourceRevision: "source-r1",
        stale: false,
        candidates: [
          {
            handle: "candidate-h-alpha",
            label: "Review browser journey",
            sourceExcerpt: "Acceptance source",
            proposedType: "Requirement",
            proposedRelations: [],
            validationState: "pending-review",
            confidence: 0.9,
            age: "today",
            lifecycleState: "pending-review",
            evidenceCount: 1,
          },
        ],
        hasMore: false,
      });
    }
    if (pathname === `/v1/projects/${project.handle}/candidate-edit-options`) {
      return json(route, {
        entityLinks: [
          { handle: "node-h-requirement", label: "Bounded journey", type: "Requirement" },
        ],
        assignments: [{ handle: "actor-h-reviewer", label: "Current reviewer" }],
      });
    }
    if (pathname.includes("/candidates/candidate-h-alpha/edits")) {
      return json(route, {
        candidateHandle: "candidate-h-alpha",
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
      return json(route, { decision: "confirmed", candidateHandle: "candidate-h-alpha" });
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
    path: `../../docs/sprint-plans/sprint-8/evidence/${screenshotName}`,
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
  await page.getByLabel("Entity link").selectOption("node-h-requirement");
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

test("injected graph failure is announced with a correlation ID", async ({ page }) => {
  await mockApi(page, true);
  await page.goto("/");
  await page.getByRole("button", { name: "Open project" }).click();
  await page.locator("button.nav-item").filter({ hasText: "Graph" }).click();
  await expect(page.getByRole("alert")).toContainText("Request ID:");
  await expect(page.getByRole("alert")).toContainText("temporarily unavailable");
});
