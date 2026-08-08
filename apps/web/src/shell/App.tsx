import { type ReactElement, useCallback, useEffect, useMemo, useState } from "react";

import { ProjectaApiClient } from "../api/client";
import type { LiveResponse, ReadyResponse } from "../api/generated";
import { CaptureScreen } from "../screens/CaptureScreen";
import { DiagnosticsScreen } from "../screens/DiagnosticsScreen";
import { ExtractionScreen } from "../screens/ExtractionScreen";
import { KnowledgeScreen } from "../screens/KnowledgeScreen";
import { QuestionScreen } from "../screens/QuestionScreen";
import { ReviewScreen } from "../screens/ReviewScreen";
import { SettingsScreen } from "../screens/SettingsScreen";
import { ErrorMessage, StateMessage } from "../ui";

const navigation = [
  "Overview",
  "Extract",
  "Capture",
  "Review",
  "Knowledge",
  "Q&A",
  "Settings",
  "Diagnostics",
] as const;
type Screen = (typeof navigation)[number];

export function App(): ReactElement {
  const api = useMemo(() => new ProjectaApiClient(), []);
  const [active, setActive] = useState<Screen>("Overview");
  const [health, setHealth] = useState<LiveResponse | null>(null);
  const [readiness, setReadiness] = useState<ReadyResponse | null>(null);
  const [healthError, setHealthError] = useState<unknown>(null);
  const [candidateId, setCandidateId] = useState("");

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

  const openReview = (id: string) => {
    setCandidateId(id);
    setActive("Review");
  };

  const screen = (() => {
    switch (active) {
      case "Extract":
        return <ExtractionScreen api={api} onCandidate={openReview} />;
      case "Capture":
        return <CaptureScreen api={api} onCandidate={openReview} />;
      case "Review":
        return <ReviewScreen api={api} initialCandidateId={candidateId} />;
      case "Knowledge":
        return <KnowledgeScreen api={api} />;
      case "Q&A":
        return <QuestionScreen api={api} />;
      case "Settings":
        return <SettingsScreen api={api} />;
      case "Diagnostics":
        return (
          <DiagnosticsScreen
            api={api}
            health={health}
            readiness={readiness}
            onHealth={loadHealth}
          />
        );
      default:
        return (
          <Overview
            health={health}
            healthError={healthError}
            onRetry={loadHealth}
            onNavigate={setActive}
          />
        );
    }
  })();

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>
      <header className="topbar">
        <div>
          <p className="eyebrow">Project intelligence</p>
          <h1>Projecta</h1>
        </div>
        <div className="topbar-status">
          <span className="experience-badge">Local experience</span>
          <span className={health ? "health-pill healthy" : "health-pill unavailable"}>
            API {health ? "live" : "offline"}
          </span>
        </div>
      </header>
      <div className="workspace">
        <nav aria-label="Primary navigation" className="sidebar">
          {navigation.map((item) => (
            <button
              aria-current={active === item ? "page" : undefined}
              className={active === item ? "nav-item active" : "nav-item"}
              key={item}
              onClick={() => setActive(item)}
              type="button"
            >
              {item}
            </button>
          ))}
        </nav>
        <main className="main-content" id="main-content" tabIndex={-1}>
          {screen}
        </main>
      </div>
    </div>
  );
}

function Overview({
  health,
  healthError,
  onRetry,
  onNavigate,
}: {
  health: LiveResponse | null;
  healthError: unknown;
  onRetry: () => Promise<void>;
  onNavigate: (screen: Screen) => void;
}): ReactElement {
  return (
    <div className="screen-grid">
      <section aria-live="polite" className="hero-card">
        <p className="eyebrow">Local project workspace</p>
        <h2>Turn project notes into grounded knowledge.</h2>
        <p>
          Capture exact evidence, extract candidate knowledge, review Requirement assertions, and
          ask bounded questions through the same-origin Application API.
        </p>
        <div className="overview-actions">
          <button onClick={() => onNavigate("Extract")} type="button">
            Start with extraction
          </button>
          <span className="metadata">
            Browser context is server-owned; graph and provider internals stay hidden.
          </span>
        </div>
      </section>
      <div className="screen-grid two-column">
        <section className="card">
          <p className="eyebrow">Runtime</p>
          <h3>{health ? "Application API is live" : "Application API unavailable"}</h3>
          {health ? (
            <StateMessage kind="success">
              The local experience can call the typed API boundary.
            </StateMessage>
          ) : (
            <>
              {healthError !== null && <ErrorMessage error={healthError} />}
              <button className="secondary" onClick={() => void onRetry()} type="button">
                Retry liveness
              </button>
            </>
          )}
        </section>
        <section className="card">
          <p className="eyebrow">Safety boundary</p>
          <h3>Server-owned experience</h3>
          <p className="muted">
            Trusted project context, LLM credentials, Semantic Core, Fuseki, graph IRIs, and
            arbitrary queries are not browser capabilities.
          </p>
        </section>
      </div>
    </div>
  );
}
