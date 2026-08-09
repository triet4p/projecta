import { describe, expect, it } from "vitest";

import { filterProjects } from "./screens/ProjectsScreen";

const projects = [
  {
    handle: "project-h-9c2f",
    name: "Alpha workspace",
    summary: "Payment requirements",
    status: "active" as const,
    counts: { requirements: 1, tasks: 2, questions: 0, risks: 0, notes: 3, candidates: 0 },
    lastActivityAt: null,
    health: "fresh" as const,
    freshness: { state: "current" as const, revision: "r1" },
  },
  {
    handle: "project-h-7a1d",
    name: "Beta workspace",
    summary: "Address risks",
    status: "paused" as const,
    counts: { requirements: 0, tasks: 0, questions: 1, risks: 2, notes: 0, candidates: 1 },
    lastActivityAt: null,
    health: "attention" as const,
    freshness: { state: "stale" as const, revision: "r2" },
  },
];

describe("project workspace UI contracts", () => {
  it("searches only returned display fields and preserves opaque handles", () => {
    expect(filterProjects(projects, "payment").map((project) => project.handle)).toEqual([
      "project-h-9c2f",
    ]);
    expect(filterProjects(projects, "")).toHaveLength(2);
    expect(projects[0].handle).not.toContain("alpha");
  });
});
