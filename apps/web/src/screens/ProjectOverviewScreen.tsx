import { useEffect, useRef, useState, type ReactElement } from "react";

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

  const [authorizationConfirmed, setAuthorizationConfirmed] = useState(false);
  const [exportError, setExportError] = useState<unknown>(null);
  const [exporting, setExporting] = useState(false);
  const [exportResult, setExportResult] = useState<{
    filename: string;
    sizeBytes: number;
    sha256: string;
  } | null>(null);
  const exportDialog = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    let active = true;
    setOverview(null);
    setError(null);
    setAuthorizationConfirmed(false);
    setExportError(null);
    setExportResult(null);
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

  async function handleExport() {
    if (!overview?.portableExportEnabled || !authorizationConfirmed || exporting) return;
    setExporting(true);
    setExportError(null);
    setExportResult(null);
    try {
      const artifact = await api.exportProject(project.handle);
      const objectUrl = URL.createObjectURL(artifact.blob);
      const anchor = document.createElement("a");
      anchor.href = objectUrl;
      anchor.download = artifact.filename;
      anchor.hidden = true;
      document.body.append(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
      setExportResult({
        filename: artifact.filename,
        sizeBytes: artifact.sizeBytes,
        sha256: artifact.sha256,
      });
      exportDialog.current?.close();
    } catch (nextError: unknown) {
      setExportError(nextError);
    } finally {
      setExporting(false);
    }
  }
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
        <div className="workspace-header-actions">
          {overview.portableExportEnabled ? (
            <button
              onClick={() => {
                setAuthorizationConfirmed(false);
                setExportError(null);
                exportDialog.current?.showModal();
              }}
              type="button"
            >
              Export project
            </button>
          ) : (
            <p className="export-disabled" role="status">
              Portable export is available only from the supported native launcher.
            </p>
          )}
        </div>
      </header>

      <dialog
        aria-labelledby="portable-export-title"
        className="export-dialog"
        onClose={() => setAuthorizationConfirmed(false)}
        ref={exportDialog}
      >
        <h2 id="portable-export-title">Export this project?</h2>
        <div className="export-warning">
          <p>
            The archive contains sensitive project data, including stored graph, workflow,
            connector, receipt, and evidence content. It is plaintext: it is not encrypted, and
            its integrity hashes are not a signature.
          </p>
          <p>
            You are responsible for choosing a private destination and transport. Export only
            when you are authorized to move all included project data.
          </p>
        </div>
        {exportError !== null && (
          <p className="state-message error" role="alert">
            {exportError instanceof Error ? exportError.message : "The project export failed."}
          </p>
        )}
        <label className="export-authorization">
          <input
            checked={authorizationConfirmed}
            disabled={exporting}
            onChange={(event) => setAuthorizationConfirmed(event.currentTarget.checked)}
            type="checkbox"
          />
          <span>
            I am authorized to export and privately transport all sensitive project data in this
            archive.
          </span>
        </label>
        <div className="export-dialog-actions">
          <button
            className="secondary"
            disabled={exporting}
            onClick={() => exportDialog.current?.close()}
            type="button"
          >
            Cancel
          </button>
          <button
            disabled={!authorizationConfirmed || exporting}
            onClick={() => void handleExport()}
            type="button"
          >
            {exporting ? "Preparing export…" : "Download archive"}
          </button>
        </div>
      </dialog>
      {exportResult && (
        <div className="state-message success export-result" role="status">
          <strong>Export downloaded:</strong> {exportResult.filename} · {exportResult.sizeBytes}{" "}
          bytes · SHA-256 {exportResult.sha256}. Integrity only; not a signature.
        </div>
      )}

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
