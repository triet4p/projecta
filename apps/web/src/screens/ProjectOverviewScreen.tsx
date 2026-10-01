import { useEffect, useState, type ReactElement } from "react";

import type { ProjectaApiClient } from "../api/client";
import type { ProjectCatalogItem, ProjectOverviewResponse } from "../api/generated";
import { Breadcrumbs, Card, EmptyState, ErrorMessage, Skeleton } from "../ui";
import type { Screen } from "../shell/navigation";

const collections = [
  ["currentRequirements", "Current requirements"],
  ["openQuestions", "Open questions"],
  ["tasks", "Tasks"],
  ["blockers", "Blockers"],
  ["risks", "Risks"],
  ["recentNotes", "Recent notes"],
  ["pendingCandidates", "Pending candidates"],
] as const;

const collectionDestinations: Record<(typeof collections)[number][0], Screen> = {
  currentRequirements: "Graph",
  openQuestions: "Graph",
  tasks: "Graph",
  blockers: "Graph",
  risks: "Graph",
  recentNotes: "Notes",
  pendingCandidates: "Review Queue",
};

type OverviewNavigationItem = { handle: string; label: string };

export function ProjectOverviewScreen({
  api,
  project,
  onChangeProject,
  onNavigate,
}: {
  api: ProjectaApiClient;
  project: ProjectCatalogItem;
  onChangeProject: () => void;
  onNavigate: (screen: Screen, item?: OverviewNavigationItem) => void;
}): ReactElement {
  const [overview, setOverview] = useState<ProjectOverviewResponse | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    let active = true;
    setOverview(null);
    setError(null);
    void api
      .getProjectOverview(project.handle)
      .then((result) => {
        if (active) setOverview(result);
      })
      .catch((nextError: unknown) => {
        if (active) setError(nextError);
      });
    return () => {
      active = false;
    };
  }, [api, project.handle]);

  if (error !== null)
    return (
      <>
        <ErrorMessage error={error} />
        <button className="secondary" onClick={onChangeProject} type="button">
          Return to Projects
        </button>
      </>
    );
  if (overview === null) return <Skeleton count={5} />;

  return (
    <div className="workspace-page">
      <Breadcrumbs>Projects / {overview.name}</Breadcrumbs>
      <header className="workspace-header">
        <div>
          <p className="eyebrow">Project overview</p>
          <h2>{overview.name}</h2>
          {overview.summary && <p className="muted">{overview.summary}</p>}
        </div>
      </header>
      <Card>
        <div className="metric-grid">
          {Object.entries(overview.counts).map(([label, value]) => (
            <div className="metric" key={label}>
              <span className="metric-value">{value}</span>
              <span className="metric-label">{label}</span>
            </div>
          ))}
        </div>
        <p className="project-meta">
          Freshness: {overview.freshness.state} · Last activity:{" "}
          {overview.lastActivityAt ?? "No activity recorded"}
        </p>
      </Card>
      <div className="collection-grid">
        {collections.map(([key, label]) => {
          const items = overview[key] as Record<string, string>[];
          return (
            <Card className="collection-card" key={key}>
              <h3>{label}</h3>
              {items.length === 0 ? (
                <EmptyState title="Nothing here">No items are currently reported.</EmptyState>
              ) : (
                <ul className="collection-list">
                  {items.map((item) => (
                    <li key={item.handle}>
                      <button
                        className="link-button"
                        onClick={() =>
                          onNavigate(collectionDestinations[key], {
                            handle: item.handle,
                            label: item.label,
                          })
                        }
                        type="button"
                      >
                        {item.label}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          );
        })}
      </div>
      <Card>
        <h3>Evidence coverage</h3>
        <p className="project-meta">
          {overview.evidenceCoverage.covered ?? 0} covered of {overview.evidenceCoverage.total ?? 0}{" "}
          scoped knowledge items.
        </p>
      </Card>
    </div>
  );
}
