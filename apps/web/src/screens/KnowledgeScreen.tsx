import { useEffect, useState } from "react";

import type { ProjectaApiClient } from "../api/client";
import type {
  CandidateHistoryResponse,
  EvidenceResponse,
  KnowledgeItemsResponse,
} from "../api/generated";
import { Card, ErrorMessage, StateMessage } from "../ui";

export function KnowledgeScreen({ api }: { api: ProjectaApiClient }) {
  const [current, setCurrent] = useState<KnowledgeItemsResponse | null>(null);
  const [history, setHistory] = useState<CandidateHistoryResponse | null>(null);
  const [evidence, setEvidence] = useState<EvidenceResponse | null>(null);
  const [candidateId, setCandidateId] = useState("");
  const [itemId, setItemId] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const loadCurrent = async () => {
    setLoading(true);
    setError(null);
    try {
      setCurrent(await api.listCurrentKnowledge());
    } catch (nextError) {
      setError(nextError);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadCurrent();
  }, []);

  const loadHistory = async () => {
    if (!candidateId.trim()) return;
    setError(null);
    try {
      setHistory(await api.getCandidateHistory(candidateId.trim()));
    } catch (nextError) {
      setError(nextError);
    }
  };

  const loadEvidence = async (requestedItemId = itemId) => {
    if (!requestedItemId.trim()) return;
    setItemId(requestedItemId);
    setError(null);
    try {
      setEvidence(await api.getEvidence(requestedItemId.trim()));
    } catch (nextError) {
      setError(nextError);
    }
  };

  return (
    <div className="screen-grid">
      {error !== null && <ErrorMessage error={error} />}
      <Card>
        <div className="section-heading">
          <div>
            <p className="eyebrow">Knowledge</p>
            <h2>Current Requirements</h2>
          </div>
          <button
            className="secondary"
            disabled={loading}
            onClick={() => void loadCurrent()}
            type="button"
          >
            {loading ? "Refreshing…" : "Refresh"}
          </button>
        </div>
        {!current && <StateMessage kind="loading">Loading current project knowledge…</StateMessage>}
        {current && current.items.length === 0 && (
          <StateMessage kind="empty">No current Requirement items are available.</StateMessage>
        )}
        {current?.items.map((item, index) => (
          <div className="knowledge-item" key={String(item.id ?? index)}>
            <strong>{item.label}</strong>
            <span>{item.type}</span>
            <small>Opaque ID: {item.id}</small>
            <button className="secondary" onClick={() => void loadEvidence(item.id)} type="button">
              View evidence
            </button>
          </div>
        ))}
      </Card>
      <div className="screen-grid two-column">
        <Card>
          <p className="eyebrow">Candidate lifecycle</p>
          <h2>History by opaque ID</h2>
          <label className="stacked-label">
            Candidate ID
            <input value={candidateId} onChange={(event) => setCandidateId(event.target.value)} />
          </label>
          <button disabled={!candidateId.trim()} onClick={() => void loadHistory()} type="button">
            Load history
          </button>
          {history ? (
            <div className="result-stack">
              <p className="metadata">Candidate {history.candidateId}</p>
              {history.items.map((activity) => (
                <div className="knowledge-item" key={activity.id}>
                  <strong>{activity.decision ?? "Lifecycle activity"}</strong>
                  <span>Activity {activity.id}</span>
                  <small>Reviewer {activity.reviewerId ?? "unavailable"}</small>
                </div>
              ))}
            </div>
          ) : (
            <StateMessage kind="empty">No candidate history loaded.</StateMessage>
          )}
        </Card>
        <Card>
          <p className="eyebrow">Evidence and provenance</p>
          <h2>Evidence by opaque ID</h2>
          <label className="stacked-label">
            Knowledge item ID
            <input value={itemId} onChange={(event) => setItemId(event.target.value)} />
          </label>
          <button disabled={!itemId.trim()} onClick={() => void loadEvidence()} type="button">
            Load evidence
          </button>
          {evidence ? (
            <div className="result-stack">
              <p className="metadata">Item {evidence.itemId}</p>
              {evidence.items.map((record, index) => (
                <div className="evidence-row" key={`${record.sourceId ?? "source"}-${index}`}>
                  <strong>{record.evidenceText ?? "Evidence span"}</strong>
                  <span>Source {record.sourceId ?? "unavailable"}</span>
                  <small>
                    code points {record.startOffset ?? "?"}–{record.endOffset ?? "?"}
                  </small>
                </div>
              ))}
            </div>
          ) : (
            <StateMessage kind="empty">No evidence loaded.</StateMessage>
          )}
        </Card>
      </div>
    </div>
  );
}
