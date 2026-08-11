export const navigationGroups = [
  { label: "Workspace", items: ["Projects", "Project Overview"] },
  { label: "Work", items: ["Notes", "Graph", "Review Queue", "Q&A"] },
  { label: "System", items: ["Connections", "Settings", "Diagnostics"] },
] as const;

export type Screen = (typeof navigationGroups)[number]["items"][number];
