import { describe, expect, it } from "vitest";

import { navigationGroups } from "./shell/navigation";

describe("Sprint 8 information architecture", () => {
  it("exposes only the approved workspace navigation", () => {
    expect(navigationGroups.flatMap((group) => group.items)).toEqual([
      "Projects",
      "Project Overview",
      "Notes",
      "Graph",
      "Review Queue",
      "Q&A",
      "Settings",
      "Diagnostics",
    ]);
  });

  it("does not expose identifiers or legacy shortcut screens", () => {
    const labels = navigationGroups.flatMap((group) => group.items);
    expect(labels.join(" ")).not.toMatch(/Capture|Extract|Knowledge|candidate-|proj-/i);
  });
});
