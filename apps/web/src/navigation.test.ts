import { describe, expect, it } from "vitest";

import { navigationGroups } from "./shell/navigation";

describe("project and workspace information architecture", () => {
  it("keeps project selection outside in-workspace navigation", () => {
    expect(navigationGroups).toEqual([
      { label: "Workspace", items: ["Project Overview"] },
      { label: "Work", items: ["Notes", "Graph", "Review Queue", "Knowledge", "Q&A"] },
      { label: "System", items: ["Connections", "Settings", "Diagnostics"] },
    ]);
  });

  it("does not expose identifiers or legacy shortcut screens", () => {
    const labels = navigationGroups.flatMap((group) => group.items);
    expect(labels.join(" ")).not.toMatch(/Capture|Extract|candidate-|proj-/i);
  });
});
