import { useEffect, useState } from "react";

import type { ProjectaApiClient } from "../api/client";
import type { InferenceRebuildResponse, LiveResponse, ReadyResponse } from "../api/generated";
import { apiErrorMessage, Card, ErrorMessage, StateMessage } from "../ui";

export function DiagnosticsScreen({
  api,
  health,
  readiness,
  onHealth,
}: {
  api: ProjectaApiClient;
  health: LiveResponse | null;
  readiness: ReadyResponse | null;
  onHealth: () => Promise<void>;
}) {
  const [rebuild, setRebuild] = useState<InferenceRebuildResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  useEffect(() => {
    void onHealth();
  }, [onHealth]);

  const rebuildInference = async () => {
    setBusy(true);
    setError(null);
    try {
      setRebuild(await api.rebuildInference());
    } catch (nextError) {
      setError(nextError);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="screen-grid two-column">
      <Card>
        <p className="eyebrow">Experience diagnostics</p>
        <h2>Runtime status</h2>
        <div className="diagnostic-row">
          <span>Application API</span>
          <strong className={health ? "online" : "offline"}>
            {health ? health.status : "unavailable"}
          </strong>
        </div>
        <div className="diagnostic-row">
          <span>Semantic dependency</span>
          <strong
            className={
              readiness?.semanticCore === "ready" || readiness?.semanticCore === "injected"
                ? "online"
                : "offline"
            }
          >
            {readiness?.semanticCore ?? "unavailable"}
          </strong>
        </div>
        <p className="muted">
          Request IDs are shown in errors and operation results. This panel is local-experience
          diagnostics, not a production admin console.
        </p>
        {error !== null && <ErrorMessage error={error} />}
        <button className="secondary" onClick={() => void onHealth()} type="button">
          Refresh liveness
        </button>
      </Card>
      <Card>
        <p className="eyebrow">Experience-only control</p>
        <h2>Inference materialization</h2>
        <p className="muted">
          Rebuild is available only through the approved local experience boundary.
        </p>
        <button disabled={busy} onClick={() => void rebuildInference()} type="button">
          {busy ? "Rebuilding…" : "Rebuild inference"}
        </button>
        {rebuild ? (
          <StateMessage kind="success">
            Rebuilt {rebuild.materializedRuleIds.length} rule(s). Source revision{" "}
            {rebuild.sourceRevision}; materialization {rebuild.materializationRevision}.
          </StateMessage>
        ) : (
          <StateMessage kind="empty">No rebuild requested.</StateMessage>
        )}
        {error !== null && <p className="metadata">{apiErrorMessage(error)}</p>}
      </Card>
    </div>
  );
}
