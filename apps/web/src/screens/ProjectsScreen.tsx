import { useEffect, useMemo, useRef, useState, type ReactElement } from "react";

import { ApiError } from "../api/client";
import type { ProjectaApiClient } from "../api/client";
import type {
  PortableImportApplyResponse,
  PortableImportPreviewResponse,
  ProjectCatalogItem,
  PortableImportResultResponse,
  ProjectDeletionPreviewResponse,
  ProjectDeletionResponse,
} from "../api/generated";
import { EmptyState, ErrorMessage, Skeleton, StatusBadge, Toolbar } from "../ui";

const PENDING_IMPORT_SESSION_KEY = "projecta.portableImport.pendingId";

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
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importPreview, setImportPreview] = useState<PortableImportPreviewResponse | null>(null);
  const [importResult, setImportResult] = useState<
    PortableImportApplyResponse | PortableImportResultResponse | null
  >(null);
  const [importError, setImportError] = useState<unknown>(null);
  const [importWorking, setImportWorking] = useState(false);
  const [importConfirmed, setImportConfirmed] = useState(false);
  const [fileInputKey, setFileInputKey] = useState(0);
  const [pendingImportId, setPendingImportId] = useState<string | null>(() =>
    window.sessionStorage.getItem(PENDING_IMPORT_SESSION_KEY),
  );
  const [deletionTarget, setDeletionTarget] = useState<ProjectCatalogItem | null>(null);
  const [deletionPreview, setDeletionPreview] = useState<ProjectDeletionPreviewResponse | null>(null);
  const [deletionResult, setDeletionResult] = useState<ProjectDeletionResponse | null>(null);
  const [deletionError, setDeletionError] = useState<unknown>(null);
  const [deletionWorking, setDeletionWorking] = useState(false);
  const [deletionIdentity, setDeletionIdentity] = useState("");
  const deletionDialogRef = useRef<HTMLDialogElement | null>(null);
  const deletionIdentityRef = useRef<HTMLInputElement | null>(null);

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

  useEffect(() => {
    if (!pendingImportId) return;
    let active = true;
    let timer: number | undefined;
    const poll = async () => {
      try {
        const result = await api.getPortableImportResult(pendingImportId);
        if (!active) return;
        setImportResult(result);
        if (result.status === "staging") {
          timer = window.setTimeout(() => void poll(), 1_500);
        } else {
          window.sessionStorage.removeItem(PENDING_IMPORT_SESSION_KEY);
          setPendingImportId(null);
          if (result.status === "complete") {
            try {
              const catalog = await api.listProjects();
              if (active) {
                setProjects(catalog.projects);
                setCatalogRevision(catalog.catalogRevision);
                setError(null);
              }
            } catch (nextError) {
              if (active) setError(nextError);
            }
          }
        }
      } catch (nextError) {
        if (nextError instanceof ApiError && nextError.problem.status === 404) {
          window.sessionStorage.removeItem(PENDING_IMPORT_SESSION_KEY);
          setPendingImportId(null);
          setImportError(nextError);
          return;
        }
        if (active) timer = window.setTimeout(() => void poll(), 1_500);
      }
    };
    void poll();
    return () => {
      active = false;
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, [api, pendingImportId]);

  const visible = useMemo(() => filterProjects(projects, search), [projects, search]);
  const importStatus = importResult && "status" in importResult ? importResult.status : null;
  const importAlreadyImported = importResult && "alreadyImported" in importResult && importResult.alreadyImported;
  const importFailureCode = importResult && "failureCode" in importResult ? importResult.failureCode : undefined;
  const importNextAction = importResult && "nextAction" in importResult ? importResult.nextAction : undefined;

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
  const reviewImport = async () => {
    if (!importFile) return;
    setImportWorking(true);
    setImportError(null);
    setImportResult(null);
    try {
      const result = await api.previewPortableImport(importFile);
      setImportPreview(result);
      setImportConfirmed(false);
    } catch (nextError) {
      setImportError(nextError);
    } finally {
      setImportWorking(false);
    }
  };

  const cancelImport = async () => {
    setImportWorking(true);
    setImportError(null);
    try {
      if (importPreview) await api.cancelPortableImport(importPreview.importId);
      setImportPreview(null);
      setImportResult(null);
      setImportFile(null);
      setImportConfirmed(false);
      setFileInputKey((value) => value + 1);
    } catch (nextError) {
      setImportError(nextError);
    } finally {
      setImportWorking(false);
    }
  };

  const applyImport = async () => {
    if (
      !importPreview ||
      !importConfirmed ||
      !["add-project", "adopt-placeholder"].includes(importPreview.destinationAction)
    ) {
      return;
    }
    setImportWorking(true);
    setImportError(null);
    try {
      const result = await api.applyPortableImport(importPreview.importId, true);
      if (result.restartRequired && result.importId) {
        window.sessionStorage.setItem(PENDING_IMPORT_SESSION_KEY, result.importId);
        setPendingImportId(result.importId);
      }
      setImportResult(result);
      setImportPreview(null);
      setImportFile(null);
      setImportConfirmed(false);
      setFileInputKey((value) => value + 1);
    } catch (nextError) {
      setImportError(nextError);
    } finally {
      setImportWorking(false);
    }
  };

  const openDeletion = async (project: ProjectCatalogItem) => {
    setDeletionTarget(project);
    setDeletionPreview(null);
    setDeletionResult(null);
    setDeletionError(null);
    setDeletionIdentity("");
    setDeletionWorking(true);
    try {
      const preview = await api.previewProjectDeletion(project.handle, project.name);
      setDeletionPreview(preview);
    } catch (nextError) {
      setDeletionError(nextError);
    } finally {
      setDeletionWorking(false);
    }
  };

  const closeDeletion = () => {
    if (deletionWorking) return;
    if (deletionDialogRef.current?.open) deletionDialogRef.current.close();
    setDeletionTarget(null);
    setDeletionPreview(null);
    setDeletionError(null);
    setDeletionIdentity("");
  };
  useEffect(() => {
    if (deletionTarget && deletionDialogRef.current && !deletionDialogRef.current.open) {
      deletionDialogRef.current.showModal();
    }
  }, [deletionTarget]);
  useEffect(() => {
    if (deletionPreview && deletionDialogRef.current?.open) {
      deletionIdentityRef.current?.focus({ preventScroll: true });
      deletionIdentityRef.current?.scrollIntoView({ block: "nearest" });
    }
  }, [deletionPreview]);

  const confirmDeletion = async () => {
    if (!deletionTarget || !deletionPreview) return;
    const typed = deletionIdentity.trim();
    if (typed !== deletionPreview.projectId && typed !== deletionPreview.projectName) return;
    setDeletionWorking(true);
    setDeletionError(null);
    try {
      const result = await api.deleteProject(
        deletionPreview.projectId,
        deletionPreview.projectName,
        typed,
      );
      setDeletionResult(result);
      if (deletionDialogRef.current?.open) deletionDialogRef.current.close();
      setDeletionTarget(null);
      setDeletionPreview(null);
      setDeletionIdentity("");
      await load();
    } catch (nextError) {
      setDeletionError(nextError);
    } finally {
      setDeletionWorking(false);
    }
  };
  return (
    <div className="workspace-page">
      <header className="workspace-header">
        <div>
          <p className="eyebrow">Project selection</p>
          <h2>Projects</h2>
          <p className="muted">
            Choose an authorized project to enter its workspace. Use Change project from the active
            project bar to switch later.
          </p>
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
      <section aria-labelledby="portable-import-title" className="project-card portable-import-card">
        <div>
          <p className="eyebrow">Manual transfer</p>
          <h3 id="portable-import-title">Import a project package</h3>
          <p className="muted">
            Choose a Projecta <code>.projecta</code> file to validate its contents and destination
            before you decide whether to import it.
          </p>
        </div>
        <label className="import-file-field">
          <span>Project package</span>
          <input
            key={fileInputKey}
            accept=".projecta"
            disabled={importWorking || importPreview !== null || pendingImportId !== null}
            onChange={(event) => {
              setImportFile(event.currentTarget.files?.[0] ?? null);
              setImportError(null);
              setImportResult(null);
            }}
            type="file"
          />
        </label>
        {importFile && (
          <p className="project-meta">
            Selected: {importFile.name} · {formatBytes(importFile.size)}
          </p>
        )}
        <div className="workspace-header-actions">
          {!importPreview && (
            <button
              disabled={!importFile || importWorking}
              onClick={() => void reviewImport()}
              type="button"
            >
              {importWorking ? "Validating package…" : "Review package"}
            </button>
          )}
          {(importFile || importPreview) && (
            <button
              className="secondary"
              disabled={importWorking}
              onClick={() => void cancelImport()}
              type="button"
            >
              {importPreview ? "Cancel preview" : "Clear file"}
            </button>
          )}
        </div>
        {importError !== null && <ErrorMessage error={importError} />}
        {importPreview && (
          <div aria-live="polite" className="import-review">
            <h4>Review before importing</h4>
            <dl className="import-details">
              <div><dt>Project</dt><dd>{importPreview.projectName}</dd></div>
              <div><dt>Project ID</dt><dd><code>{importPreview.projectId}</code></dd></div>
              <div><dt>Exported</dt><dd>{importPreview.exportedAt}</dd></div>
              <div><dt>Package size</dt><dd>{formatBytes(importPreview.sizeBytes)}</dd></div>
              <div><dt>Archive SHA-256</dt><dd><code>{importPreview.archiveSha256}</code></dd></div>
              <div>
                <dt>Destination</dt>
                <dd>{destinationLabel(importPreview.destinationAction)}</dd>
              </div>
            </dl>
            <p className="project-meta">
              Package contents:{" "}
              {Object.entries(importPreview.counts)
                .map(([name, count]) => `${name}: ${count}`)
                .join(" · ")}
            </p>
            <p className="import-warning" role="note">{importPreview.plaintextWarning}</p>
            {importPreview.destinationAction === "conflict" && (
              <p className="import-conflict" role="alert">
                The destination conflicts with existing local state. No project data was changed.
                Cancel this preview to continue.
              </p>
            )}
            {importPreview.destinationAction === "already-imported" && (
              <p className="project-meta" role="status">
                This exact export is already recorded locally. Importing it again is a no-op.
              </p>
            )}
            {["add-project", "adopt-placeholder"].includes(importPreview.destinationAction) && (
              <>
                <label className="import-confirmation">
                  <input
                    checked={importConfirmed}
                    disabled={importWorking}
                    onChange={(event) => setImportConfirmed(event.currentTarget.checked)}
                    type="checkbox"
                  />
                  <span>
                    I am authorized to import this package and understand that existing destination
                    state will not be overwritten.
                  </span>
                </label>
                <div className="workspace-header-actions">
                  <button
                    disabled={!importConfirmed || importWorking}
                    onClick={() => void applyImport()}
                    type="button"
                  >
                    {importWorking ? "Importing…" : "Apply import"}
                  </button>
                  <button
                    className="secondary"
                    disabled={importWorking}
                    onClick={() => void cancelImport()}
                    type="button"
                  >
                    Cancel
                  </button>
                </div>
              </>
            )}
          </div>
        )}
        {pendingImportId && !importResult && (
          <div aria-live="polite" className="import-result" role="status">
            <h4>Project import in progress</h4>
            <p>Projecta Local is preparing the project privately before making it available.</p>
          </div>
        )}
        {importResult && (
          <div aria-live="polite" className="import-result" role={importStatus === "failed" ? "alert" : "status"}>
            <h4>
              {importAlreadyImported
                ? "Project already imported"
                : importStatus === "staging"
                  ? "Project import in progress"
                  : importStatus === "failed"
                    ? "Project import failed"
                    : "Project import complete"}
            </h4>
            <p>
              {importStatus === "staging"
                ? "Projecta Local is preparing the project privately. It will appear in the project list only after the complete staged state is published."
                : importStatus === "failed"
                  ? `The staged import was not published. Existing local project data was retained.${importFailureCode ? ` (${importFailureCode})` : ""}`
                  : importNextAction ??
                    (importAlreadyImported
                      ? "This exact archive was already imported; no local data was changed."
                      : "The project is available from the Projects list. It was not selected automatically.")}
            </p>
          </div>
        )}
      </section>
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
                disabled={selecting !== null || importWorking || importPreview !== null}
                onClick={() => void select(project)}
                type="button"
              >
                {selecting === project.handle ? "Opening…" : "Open project"}
              </button>
              <button
                className="secondary danger"
                disabled={selecting !== null || importWorking || importPreview !== null || deletionWorking}
                onClick={() => void openDeletion(project)}
                type="button"
              >
                Delete project
              </button>
            </article>
          ))}
        </div>
      )}
      {deletionResult && (
        <div aria-live="polite" className="state-message success" role="status">
          <strong>Project deleted:</strong> {deletionResult.projectName} (
          <code>{deletionResult.projectId}</code>). Removed {deletionResult.graphTriplesRemoved}{" "}
          graph triples, {deletionResult.evidenceObjectsRemoved} evidence objects,{" "}
          {deletionResult.sqliteRowsRemoved} workspace rows, {deletionResult.postgresRowsRemoved}{" "}
          connector and history rows, and forgot {deletionResult.ledgerEntriesForgotten} import
          ledger entries. {deletionResult.retained.join("; ")}.{" "}
          {deletionResult.nextAction ?? "Projecta Local is restarting to serve the new project catalog."}
        </div>
      )}
      {deletionTarget && (
        <dialog
          aria-labelledby="project-deletion-title"
          className="export-dialog"
          onCancel={(event) => {
            if (deletionWorking) event.preventDefault();
          }}
          onClose={closeDeletion}
          ref={deletionDialogRef}
        >
          <h2 id="project-deletion-title">Delete {deletionTarget.name}?</h2>
          <div className="export-warning" role="note">
            <p>
              This permanently deletes ALL data for <strong>{deletionTarget.name}</strong> (
              <code>{deletionPreview?.projectId ?? deletionTarget.handle}</code>), including semantic graphs, evidence objects,
              drafts and workflow history, connector state, review receipts, correction and cost
              history, configuration audit rows, and this scope&apos;s import ledger entries. There
              is no undo. Active exports or imports must be idle first.
            </p>
            <p>
              Not deleted: other projects, installation secrets and configuration, exported{" "}
              <code>.projecta</code> files, and whole-installation backups. Logical removal only;
              copies in backups or exported files remain wherever you kept them.
            </p>
          </div>
          {deletionWorking && !deletionPreview && deletionError === null && (
            <p className="project-meta" role="status">Loading project scope…</p>
          )}
          {deletionError !== null && <ErrorMessage error={deletionError} />}
          {deletionPreview && (
            <>
              <dl className="import-details">
                <div>
                  <dt>Project ID</dt>
                  <dd>
                    <code>{deletionPreview.projectId}</code>
                  </dd>
                </div>
                <div>
                  <dt>Graph triples</dt>
                  <dd>{deletionPreview.graphTriples.total}</dd>
                </div>
                <div>
                  <dt>Evidence objects</dt>
                  <dd>{deletionPreview.evidenceObjects}</dd>
                </div>
                <div>
                  <dt>Ledger entries</dt>
                  <dd>{deletionPreview.ledgerEntries}</dd>
                </div>
              </dl>
              {deletionPreview.warnings.map((warning) => (
                <p className="import-warning" key={warning} role="note">
                  {warning}
                </p>
              ))}
              <label className="stacked-label" htmlFor="project-deletion-identity">
                Type the project name or project ID to confirm
                <input
                  autoComplete="off"
                  disabled={deletionWorking}
                  id="project-deletion-identity"
                  onChange={(event) => setDeletionIdentity(event.currentTarget.value)}
                  placeholder={deletionPreview.projectName}
                  ref={deletionIdentityRef}
                  value={deletionIdentity}
                />
              </label>
            </>
          )}
          <div className="export-dialog-actions">
            <button className="secondary" disabled={deletionWorking} onClick={closeDeletion} type="button">
              Cancel
            </button>
            <button
              className="danger"
              disabled={
                deletionWorking ||
                !deletionPreview ||
                (deletionIdentity.trim() !== deletionPreview.projectId &&
                  deletionIdentity.trim() !== deletionPreview.projectName)
              }
              onClick={() => void confirmDeletion()}
              type="button"
            >
              {deletionWorking ? "Deleting…" : "Delete permanently"}
            </button>
          </div>
        </dialog>
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
function formatBytes(size: number): string {
  if (size < 1024) return `${size} bytes`;
  const units = ["KB", "MB", "GB"];
  let value = size / 1024;
  let unit = units[0];
  for (let index = 1; value >= 1024 && index < units.length; index += 1) {
    value /= 1024;
    unit = units[index];
  }
  return `${value.toFixed(value < 10 ? 1 : 0)} ${unit}`;
}

function destinationLabel(action: PortableImportPreviewResponse["destinationAction"]): string {
  switch (action) {
    case "add-project":
      return "Add as a separate project";
    case "adopt-placeholder":
      return "Use the empty first-run project";
    case "already-imported":
      return "This exact package was already imported";
    case "conflict":
      return "Conflicts with existing destination state";
  }
}
