import { type ReactElement, useCallback, useEffect, useMemo, useState } from "react";

import { ProjectaApiClient } from "../api/client";
import type { LiveResponse, ProjectCatalogItem, ReadyResponse } from "../api/generated";
import { DiagnosticsScreen } from "../screens/DiagnosticsScreen";
import { ConnectionsScreen } from "../screens/ConnectionsScreen";
import { NotesScreen } from "../screens/NotesScreen";
import type { CaptureDraft } from "../screens/CaptureScreen";
import { GraphScreen } from "../screens/GraphScreen";
import { ProjectOverviewScreen } from "../screens/ProjectOverviewScreen";
import { ProjectsScreen } from "../screens/ProjectsScreen";
import { QuestionScreen } from "../screens/QuestionScreen";
import { ReviewScreen } from "../screens/ReviewScreen";
import { KnowledgeScreen } from "../screens/KnowledgeScreen";
import { SettingsScreen } from "../screens/SettingsScreen";
import { WorkspaceHeader } from "./WorkspaceHeader";
import { navigationGroups, type Screen } from "./navigation";
import { EmptyState, ErrorMessage } from "../ui";
import { AuthShell } from "./AuthShell";

export function App(): ReactElement {
  const api = useMemo(() => new ProjectaApiClient(), []);
  const [active, setActive] = useState<Screen | "Projects">("Projects");
  const [activeProject, setActiveProject] = useState<ProjectCatalogItem | null>(null);
  const [reviewCandidateHandle, setReviewCandidateHandle] = useState<string | null>(null);
  const [graphSelection, setGraphSelection] = useState<{ handle: string; label: string } | null>(
    null,
  );
  const [notesSelection, setNotesSelection] = useState<{ handle: string; label: string } | null>(
    null,
  );
  const [captureDraft, setCaptureDraft] = useState<CaptureDraft | null>(null);
  const [selectionRevision, setSelectionRevision] = useState("");
  const [health, setHealth] = useState<LiveResponse | null>(null);
  const [readiness, setReadiness] = useState<ReadyResponse | null>(null);
  const [healthError, setHealthError] = useState<unknown>(null);

  const loadHealth = useCallback(async () => {
    try {
      setHealth(await api.getLiveness());
      setHealthError(null);
    } catch (error) {
      setHealth(null);
      setHealthError(error);
    }
    try {
      setReadiness(await api.getReadiness());
    } catch {
      setReadiness(null);
    }
  }, [api]);

  useEffect(() => {
    void loadHealth();
  }, [loadHealth]);

  const changeProject = () => {
    setActiveProject(null);
    setSelectionRevision("");
    setReviewCandidateHandle(null);
    setGraphSelection(null);
    setNotesSelection(null);
    setCaptureDraft(null);
    setActive("Projects");
  };
  const selectProject = (project: ProjectCatalogItem, revision: string) => {
    setActiveProject(project);
    setSelectionRevision(revision);
    setReviewCandidateHandle(null);
    setGraphSelection(null);
    setNotesSelection(null);
    setCaptureDraft(null);
    setActive("Project Overview");
  };
  const navigateWorkspace = (screen: Screen) => {
    setReviewCandidateHandle(null);
    setGraphSelection(null);
    setNotesSelection(null);
    setActive(screen);
  };

  const screen = (() => {
    switch (active) {
      case "Projects":
        return <ProjectsScreen api={api} onSelected={selectProject} />;
      case "Project Overview":
        return activeProject ? (
          <ProjectOverviewScreen
            api={api}
            onChangeProject={changeProject}
            onNavigate={(screen, item) => {
              setReviewCandidateHandle(
                screen === "Review Queue" ? (item?.handle ?? null) : null,
              );
              setGraphSelection(
                screen === "Graph" && item
                  ? { handle: item.handle, label: item.label }
                  : null,
              );
              setNotesSelection(screen === "Notes" && item ? item : null);
              setActive(screen);
            }}
            project={activeProject}
          />
        ) : (
          <ProjectsScreen api={api} onSelected={selectProject} />
        );
      case "Notes":
        return activeProject ? (
          <NotesScreen
            api={api}
            captureDraft={captureDraft}
            selectedNote={notesSelection}
            onClearSelectedNote={() => setNotesSelection(null)}
            onReturnToOverview={() => navigateWorkspace("Project Overview")}
            onCandidate={(candidateHandle) => {
              setReviewCandidateHandle(candidateHandle);
              setGraphSelection(null);
              setNotesSelection(null);
              setActive("Review Queue");
            }}
            onCaptureDraftChange={setCaptureDraft}
            projectHandle={activeProject.handle}
          />
        ) : (
          <ProjectsScreen api={api} onSelected={selectProject} />
        );
      case "Graph":
        return activeProject ? (
          <GraphScreen
            api={api}
            onClearSelectedItem={() => setGraphSelection(null)}
            onReturnToOverview={() => navigateWorkspace("Project Overview")}
            projectHandle={activeProject.handle}
            selectedItem={graphSelection}
          />
        ) : (
          <ProjectsScreen api={api} onSelected={selectProject} />
        );
      case "Review Queue":
        return activeProject ? (
          <ReviewScreen
            api={api}
            candidateHandle={reviewCandidateHandle}
            projectHandle={activeProject.handle}
          />
        ) : (
          <ProjectsScreen api={api} onSelected={selectProject} />
        );
      case "Knowledge":
        return activeProject ? (
          <KnowledgeScreen api={api} projectHandle={activeProject.handle} />
        ) : (
          <ProjectsScreen api={api} onSelected={selectProject} />
        );
      case "Q&A":
        return <QuestionScreen api={api} />;
      case "Settings":
        return <SettingsScreen api={api} />;
      case "Connections":
        return activeProject ? (
          <ConnectionsScreen
            api={api}
            onNavigate={setActive}
            projectHandle={activeProject.handle}
          />
        ) : (
          <ProjectsScreen api={api} onSelected={selectProject} />
        );
      case "Diagnostics":
        return (
          <DiagnosticsScreen
            api={api}
            health={health}
            readiness={readiness}
            onHealth={loadHealth}
          />
        );
    }
  })();

  const scopedScreen = active !== "Projects" && activeProject !== null;

  return (
    <AuthShell api={api}>
      {(sessionChrome) => (
        <div className="app-shell">
          <a className="skip-link" href="#main-content">
            Skip to main content
          </a>
          <header className="topbar">
            <div className="topbar-brand">
              <h1>Projecta</h1>
              {activeProject && (
                <div className="topbar-context">
                  <span>Project workspace</span>
                  <strong>{activeProject.name}</strong>
                </div>
              )}
            </div>
            <div className="topbar-status">
              <span className="experience-badge">Server-owned context</span>
              <span className={health ? "health-pill healthy" : "health-pill unavailable"}>
                API {health ? "live" : "offline"}
              </span>
              {sessionChrome}
            </div>
          </header>
          <div className={active === "Projects" ? "workspace project-selection" : "workspace"}>
            {active !== "Projects" && (
              <nav aria-label="Primary navigation" className="sidebar">
                <button
                  className="sidebar-new"
                  onClick={() => {
                    navigateWorkspace("Notes");
                  }}
                  type="button"
                >
                  <span>+ New Note</span>
                </button>
                {navigationGroups.map((group) => (
                  <div className="sidebar-group" key={group.label}>
                    <div className="sidebar-label">{group.label}</div>
                    {group.items.map((item) => (
                      <button
                        aria-current={active === item ? "page" : undefined}
                        className={active === item ? "nav-item active" : "nav-item"}
                        data-nav-short={item.slice(0, 1)}
                        key={item}
                        onClick={() => navigateWorkspace(item)}
                        type="button"
                      >
                        <span className="nav-label">{item}</span>
                      </button>
                    ))}
                  </div>
                ))}
              </nav>
            )}
            <main className="main-content" id="main-content" tabIndex={-1}>
              {scopedScreen && activeProject && (
                <WorkspaceHeader
                  onChangeProject={changeProject}
                  project={activeProject}
                  selectionRevision={selectionRevision}
                />
              )}
              {!activeProject && active !== "Projects" && (
                <EmptyState
                  title="Project selection required"
                  action={
                    <button onClick={() => setActive("Projects")} type="button">
                      Open Projects
                    </button>
                  }
                >
                  Choose a project before opening a scoped workspace.
                </EmptyState>
              )}
              {activeProject || active === "Projects" ? screen : null}
              {healthError !== null && active === "Diagnostics" && (
                <ErrorMessage error={healthError} />
              )}
            </main>
          </div>
        </div>
      )}
    </AuthShell>
  );
}
