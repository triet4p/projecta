export const navigationGroups = [
  { label: "Workspace", items: ["Project Overview"] },
  { label: "Work", items: ["Notes", "Graph", "Review Queue", "Knowledge", "Q&A"] },
  { label: "System", items: ["Connections", "Settings", "Diagnostics"] },
] as const;

export type Screen = (typeof navigationGroups)[number]["items"][number];
