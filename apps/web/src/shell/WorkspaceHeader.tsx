import type { ReactElement } from "react";

import type { ProjectCatalogItem } from "../api/generated";
import { StatusBadge } from "../ui";

export function WorkspaceHeader({
  project,
  selectionRevision,
  onChangeProject,
}: {
  project: ProjectCatalogItem;
  selectionRevision: string;
  onChangeProject: () => void;
}): ReactElement {
  return (
    <div className="workspace-header" role="region" aria-label="Active project context">
      <div>
        <p className="eyebrow">Active project</p>
        <strong title={project.name}>{project.name}</strong>
        <span className="project-meta">
          {" "}
          · freshness {project.freshness.state} · selection {selectionRevision.slice(0, 16)}
        </span>
      </div>
      <div className="workspace-header-actions">
        <StatusBadge label={project.status} status={project.status} />
        <button className="secondary" onClick={onChangeProject} type="button">
          Change project
        </button>
      </div>
    </div>
  );
}
