import { useEffect, useMemo, useState, type ReactElement } from "react";

import type { ProjectaApiClient } from "../api/client";
import type { ProjectCatalogItem } from "../api/generated";
import { EmptyState, ErrorMessage, Skeleton, StatusBadge, Toolbar } from "../ui";

export function ProjectsScreen({
  api,
  onSelected,
}: {
  api: ProjectaApiClient;
  onSelected: (project: ProjectCatalogItem, selectionRevision: string) => void;
}): ReactElement {
  const [projects, setProjects] = useState<ProjectCatalogItem[]>([]);
  const [catalogRevision, setCatalogRevision] = useState("");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [selecting, setSelecting] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);

  const load = async () => {
    setLoading(true);
    try {
      const result = await api.listProjects();
      setProjects(result.projects);
      setCatalogRevision(result.catalogRevision);
      setError(null);
    } catch (nextError) {
      setError(nextError);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const visible = useMemo(() => filterProjects(projects, search), [projects, search]);

  const select = async (project: ProjectCatalogItem) => {
    setSelecting(project.handle);
    try {
      const result = await api.selectProject({ handle: project.handle, catalogRevision });
      onSelected(result.project, result.selectionRevision);
    } catch (nextError) {
      setError(nextError);
    } finally {
      setSelecting(null);
    }
  };

  return (
    <div className="workspace-page">
      <header className="workspace-header">
        <div>
          <p className="eyebrow">Workspace explorer</p>
          <h2>Projects</h2>
          <p className="muted">Choose an authorized project to open its scoped workspace.</p>
        </div>
      </header>
      <Toolbar>
        <label className="toolbar-search">
          <span className="sr-only">Search projects</span>
          <input
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search projects"
            value={search}
          />
        </label>
        <button className="secondary" onClick={() => void load()} type="button">
          Refresh
        </button>
      </Toolbar>
      {loading && <Skeleton count={4} />}
      {!loading && error !== null && (
        <>
          <ErrorMessage error={error} />
          <button className="secondary" onClick={() => void load()} type="button">
            Retry catalog
          </button>
        </>
      )}
      {!loading && error === null && projects.length === 0 && (
        <EmptyState title="No authorized projects">
          The catalog is healthy, but this actor has no visible projects.
        </EmptyState>
      )}
      {!loading && error === null && projects.length > 0 && visible.length === 0 && (
        <EmptyState title="No matching projects">
          Try another project name or clear the search.
        </EmptyState>
      )}
      {!loading && error === null && visible.length > 0 && (
        <div aria-label="Authorized projects" className="project-grid">
          {visible.map((project) => (
            <article className="project-card" key={project.handle}>
              <div className="project-card-header">
                <h3 title={project.name}>{project.name}</h3>
                <StatusBadge label={project.status} status={project.status} />
              </div>
              <p className="project-summary">
                {project.summary ?? "No project summary has been provided."}
              </p>
              <div className="project-meta">
                {project.counts.requirements} requirements · {project.counts.notes} notes ·{" "}
                {project.counts.candidates} candidates
              </div>
              <div className="project-meta">
                Last activity: {project.lastActivityAt ?? "No activity recorded"} ·{" "}
                {project.freshness.state}
              </div>
              <button
                disabled={selecting !== null}
                onClick={() => void select(project)}
                type="button"
              >
                {selecting === project.handle ? "Opening…" : "Open project"}
              </button>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}

export function filterProjects(
  projects: ProjectCatalogItem[],
  search: string,
): ProjectCatalogItem[] {
  const needle = search.trim().toLocaleLowerCase();
  if (!needle) return projects;
  return projects.filter((project) =>
    `${project.name} ${project.summary ?? ""}`.toLocaleLowerCase().includes(needle),
  );
}
