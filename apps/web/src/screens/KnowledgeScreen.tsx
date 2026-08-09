import { useEffect, useState } from "react";

import type { ProjectaApiClient } from "../api/client";
import type {
  GraphEvidenceResponse,
  GraphLifecycleResponse,
  GraphNodeDetail,
  KnowledgeCollectionResponse,
} from "../api/generated";
import { Card, ErrorMessage, StateMessage, StatusBadge } from "../ui";

export function KnowledgeScreen({
  api,
  projectHandle,
}: {
  api: ProjectaApiClient;
  projectHandle: string;
}) {
  const [collection, setCollection] = useState<KnowledgeCollectionResponse | null>(null);
  const [selectedHandle, setSelectedHandle] = useState<string | null>(null);
  const [detail, setDetail] = useState<GraphNodeDetail | null>(null);
  const [evidence, setEvidence] = useState<GraphEvidenceResponse | null>(null);
  const [lifecycle, setLifecycle] = useState<GraphLifecycleResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const load = async () => {
    setBusy(true);
    setError(null);
    try {
      setCollection(await api.listKnowledgeCollection(projectHandle));
    } catch (nextError) {
      setError(nextError);
    } finally {
      setBusy(false);
    }
  };
  useEffect(() => {
    void load();
  }, [projectHandle]);

  const select = async (handle: string) => {
    setSelectedHandle(handle);
    setBusy(true);
    setError(null);
    try {
      const [nextDetail, nextEvidence, nextLifecycle] = await Promise.all([
        api.getGraphNodeDetail(projectHandle, handle),
        api.getGraphEvidence(projectHandle, handle),
        api.getGraphLifecycle(projectHandle, handle),
      ]);
      setDetail(nextDetail);
      setEvidence(nextEvidence);
      setLifecycle(nextLifecycle);
    } catch (nextError) {
      setError(nextError);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="screen-grid two-column">
      {error !== null && <ErrorMessage error={error} />}
      <Card>
        <div className="section-heading">
          <div>
            <p className="eyebrow">Knowledge collection</p>
            <h2>Current project items</h2>
          </div>
          <button className="secondary" disabled={busy} onClick={() => void load()} type="button">
            {busy ? "Refreshing…" : "Refresh"}
          </button>
        </div>
        {collection?.stale && (
          <StateMessage kind="empty">
            Knowledge is stale; refresh before relying on this view.
          </StateMessage>
        )}
        {!collection && error === null && (
          <StateMessage kind="loading">Loading labeled knowledge…</StateMessage>
        )}
        {collection?.items.length === 0 && (
          <StateMessage kind="empty">No current knowledge items are available.</StateMessage>
        )}
        <div className="knowledge-list">
          {collection?.items.map((item) => (
            <button
              className={
                selectedHandle === item.handle ? "knowledge-item selected" : "knowledge-item"
              }
              key={item.handle}
              onClick={() => void select(item.handle)}
              type="button"
            >
              <strong>{item.label}</strong>
              <span>
                {item.semanticType} · {item.lifecycleState}
              </span>
              <small>
                {item.evidenceCount} evidence records · {item.provenanceState}
              </small>
            </button>
          ))}
        </div>
      </Card>
      <Card>
        {!detail ? (
          <>
            <p className="eyebrow">Knowledge detail</p>
            <h2>Select an item</h2>
            <StateMessage kind="empty">
              Browse the returned collection to open detail, evidence, and lifecycle history.
            </StateMessage>
          </>
        ) : (
          <>
            <div className="section-heading">
              <div>
                <p className="eyebrow">Labeled detail</p>
                <h2>{detail.label}</h2>
              </div>
              <StatusBadge status={detail.lifecycleState} />
            </div>
            <div className="detail-grid">
              <span>
                Type<strong>{detail.semanticType}</strong>
              </span>
              <span>
                Verification<strong>{detail.verificationState}</strong>
              </span>
              <span>
                Provenance<strong>{detail.provenanceState}</strong>
              </span>
              <span>
                Project<strong>{detail.projectLabel}</strong>
              </span>
            </div>
            <h3>Evidence</h3>
            {evidence?.items.length ? (
              evidence.items.map((item, index) => (
                <div className="evidence-row" key={index}>
                  <strong>
                    {String(item.evidenceText ?? item.sourceText ?? "Evidence record")}
                  </strong>
                </div>
              ))
            ) : (
              <StateMessage kind="empty">No evidence is available for this item.</StateMessage>
            )}
            <h3>Lifecycle history</h3>
            {lifecycle?.items.length ? (
              lifecycle.items.map((item, index) => (
                <div className="knowledge-item" key={index}>
                  <strong>{item.decision ?? "Lifecycle event"}</strong>
                  <small>{item.endedAt ?? "Time unavailable"}</small>
                </div>
              ))
            ) : (
              <StateMessage kind="empty">No lifecycle history is available.</StateMessage>
            )}
          </>
        )}
      </Card>
    </div>
  );
}
