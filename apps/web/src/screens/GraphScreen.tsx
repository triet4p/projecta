import { useEffect, useMemo, useState } from "react";

import type { ProjectaApiClient } from "../api/client";
import type { GraphNode, GraphNodeDetail, GraphProjectionResponse } from "../api/generated";
import { Card, ErrorMessage, StateMessage, StatusBadge } from "../ui";

const types = ["All", "Requirement", "Question", "Task", "Risk", "Decision", "Note"] as const;
const states = ["All", "candidate", "asserted", "inferred"] as const;
const relations = ["All", "supports", "blocks", "dependsOn", "implements", "derivedFrom"] as const;
const lifecycles = ["All", "current", "pending-review", "confirmed", "rejected", "stale"] as const;
const provenances = [
  "All",
  "source-backed",
  "human-confirmed",
  "rule-derived",
  "candidate-proposed",
] as const;

export function GraphScreen({
  api,
  projectHandle,
}: {
  api: ProjectaApiClient;
  projectHandle: string;
}) {
  const [graph, setGraph] = useState<GraphProjectionResponse | null>(null);
  const [detail, setDetail] = useState<GraphNodeDetail | null>(null);
  const [nodeType, setNodeType] = useState<(typeof types)[number]>("All");
  const [verification, setVerification] = useState<(typeof states)[number]>("All");
  const [relation, setRelation] = useState<(typeof relations)[number]>("All");
  const [lifecycle, setLifecycle] = useState<(typeof lifecycles)[number]>("All");
  const [provenance, setProvenance] = useState<(typeof provenances)[number]>("All");
  const [evidence, setEvidence] = useState<"any" | "with-evidence" | "without-evidence">("any");
  const [scale, setScale] = useState(1);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const load = async (signal?: AbortSignal) => {
    setBusy(true);
    setError(null);
    try {
      setGraph(
        await api.getProjectGraph(
          projectHandle,
          {
            semanticTypes: nodeType === "All" ? undefined : [nodeType],
            verificationStates: verification === "All" ? undefined : [verification],
            relationTypes: relation === "All" ? undefined : [relation],
            lifecycleStates: lifecycle === "All" ? undefined : [lifecycle],
            provenanceStates: provenance === "All" ? undefined : [provenance],
            evidence,
          },
          signal,
        ),
      );
    } catch (nextError) {
      if (nextError instanceof DOMException && nextError.name === "AbortError") return;
      setError(nextError);
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [projectHandle, nodeType, verification, relation, lifecycle, provenance, evidence]);

  const visibleNodes = useMemo(() => {
    if (!graph) return [];
    return graph.nodes.filter((node) => {
      const typeMatch = nodeType === "All" || node.semanticType === nodeType;
      const stateMatch = verification === "All" || node.verificationState === verification;
      const lifecycleMatch = lifecycle === "All" || node.lifecycleState === lifecycle;
      const provenanceMatch = provenance === "All" || node.provenanceState === provenance;
      const evidenceMatch =
        evidence === "any" ||
        (evidence === "with-evidence" ? node.evidenceCount > 0 : node.evidenceCount === 0);
      return typeMatch && stateMatch && lifecycleMatch && provenanceMatch && evidenceMatch;
    });
  }, [graph, nodeType, verification, lifecycle, provenance, evidence]);

  const visibleEdges = useMemo(
    () => graph?.edges.filter((edge) => relation === "All" || edge.relationType === relation) ?? [],
    [graph, relation],
  );

  const openDetail = async (node: GraphNode) => {
    setError(null);
    try {
      setDetail(await api.getGraphNodeDetail(projectHandle, node.handle));
    } catch (nextError) {
      setError(nextError);
    }
  };

  const expand = async (node: GraphNode) => {
    setBusy(true);
    setError(null);
    try {
      setGraph(await api.expandGraphNode(projectHandle, node.handle, graph?.sourceRevision));
    } catch (nextError) {
      setError(nextError);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="screen-grid graph-screen">
      <Card>
        <div className="section-heading">
          <div>
            <p className="eyebrow">Project graph</p>
            <h2>Finite knowledge projection</h2>
          </div>
          <div className="toolbar-actions">
            <button
              className="secondary"
              onClick={() => setScale((value) => Math.max(0.75, value - 0.1))}
              type="button"
            >
              −
            </button>
            <span aria-live="polite">{Math.round(scale * 100)}%</span>
            <button
              className="secondary"
              onClick={() => setScale((value) => Math.min(1.5, value + 0.1))}
              type="button"
            >
              +
            </button>
            <button className="secondary" disabled={busy} onClick={() => void load()} type="button">
              {busy ? "Loading…" : "Refresh"}
            </button>
          </div>
        </div>
        <div className="filter-bar" aria-label="Graph filters">
          <label>
            Domain type
            <select
              value={nodeType}
              onChange={(event) => setNodeType(event.target.value as (typeof types)[number])}
            >
              {types.map((value) => (
                <option key={value}>{value}</option>
              ))}
            </select>
          </label>
          <label>
            State
            <select
              value={verification}
              onChange={(event) => setVerification(event.target.value as (typeof states)[number])}
            >
              {states.map((value) => (
                <option key={value}>{value}</option>
              ))}
            </select>
          </label>
          <label>
            Relation
            <select
              value={relation}
              onChange={(event) => setRelation(event.target.value as (typeof relations)[number])}
            >
              {relations.map((value) => (
                <option key={value}>{value}</option>
              ))}
            </select>
          </label>
          <label>
            Lifecycle
            <select
              value={lifecycle}
              onChange={(event) => setLifecycle(event.target.value as (typeof lifecycles)[number])}
            >
              {lifecycles.map((value) => (
                <option key={value}>{value}</option>
              ))}
            </select>
          </label>
          <label>
            Provenance
            <select
              value={provenance}
              onChange={(event) =>
                setProvenance(event.target.value as (typeof provenances)[number])
              }
            >
              {provenances.map((value) => (
                <option key={value}>{value}</option>
              ))}
            </select>
          </label>
          <label>
            Evidence
            <select
              value={evidence}
              onChange={(event) => setEvidence(event.target.value as typeof evidence)}
            >
              <option value="any">Any</option>
              <option value="with-evidence">With evidence</option>
              <option value="without-evidence">Without evidence</option>
            </select>
          </label>
        </div>
        {error !== null && <ErrorMessage error={error} />}
        {graph?.stale && (
          <StateMessage kind="empty">
            This projection is stale. Refresh to request the current project revision.
          </StateMessage>
        )}
        {!graph && error === null && (
          <StateMessage kind="loading">Loading the bounded project graph…</StateMessage>
        )}
        {graph && visibleNodes.length === 0 && (
          <StateMessage kind="empty">No graph nodes match these finite filters.</StateMessage>
        )}
        {graph && visibleNodes.length > 0 && (
          <div className="graph-canvas-wrap" role="img" aria-label="Directed project graph">
            <svg
              className="graph-canvas"
              height="360"
              viewBox="0 0 900 360"
              style={{ transform: `scale(${scale})` }}
            >
              {visibleEdges.map((edge) => {
                const source = visibleNodes.findIndex((node) => node.handle === edge.sourceHandle);
                const target = visibleNodes.findIndex((node) => node.handle === edge.targetHandle);
                if (source < 0 || target < 0) return null;
                const x1 = 120 + (source % 4) * 210;
                const y1 = 70 + Math.floor(source / 4) * 130;
                const x2 = 120 + (target % 4) * 210;
                const y2 = 70 + Math.floor(target / 4) * 130;
                return (
                  <line
                    className={`graph-edge ${edge.verificationState}`}
                    key={edge.handle}
                    markerEnd="url(#arrow)"
                    x1={x1}
                    x2={x2}
                    y1={y1}
                    y2={y2}
                  />
                );
              })}
              <defs>
                <marker
                  id="arrow"
                  markerHeight="7"
                  markerWidth="7"
                  orient="auto"
                  refX="6"
                  refY="3.5"
                >
                  <path d="M0,0 L7,3.5 L0,7 z" />
                </marker>
              </defs>
              {visibleNodes.map((node, index) => {
                const x = 120 + (index % 4) * 210;
                const y = 70 + Math.floor(index / 4) * 130;
                return (
                  <g
                    className={`graph-node ${node.verificationState}`}
                    key={node.handle}
                    onClick={() => void openDetail(node)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") void openDetail(node);
                    }}
                    role="button"
                    tabIndex={0}
                  >
                    <rect height="56" rx="8" width="170" x={x - 85} y={y - 28} />
                    <text className="graph-node-label" textAnchor="middle" x={x} y={y - 4}>
                      {node.label.slice(0, 25)}
                    </text>
                    <text className="graph-node-type" textAnchor="middle" x={x} y={y + 15}>
                      {node.semanticType} · {node.lifecycleState}
                    </text>
                  </g>
                );
              })}
            </svg>
          </div>
        )}
        <div className="graph-legend" aria-label="Graph legend">
          <span>
            <i className="legend-dot asserted" />
            Asserted
          </span>
          <span>
            <i className="legend-dot inferred" />
            Inferred
          </span>
          <span>
            <i className="legend-dot candidate" />
            Candidate
          </span>
          <span>Edges are directed; click a node for detail.</span>
        </div>
      </Card>
      {detail && (
        <Card>
          <div className="section-heading">
            <div>
              <p className="eyebrow">Node detail</p>
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
            <span>
              Evidence<strong>{detail.evidenceCount} linked records</strong>
            </span>
            <span>
              Freshness<strong>{detail.freshness}</strong>
            </span>
          </div>
          <div className="toolbar-actions">
            <button className="secondary" onClick={() => void expand(detail)} type="button">
              Expand one hop
            </button>
            <button className="secondary" onClick={() => setDetail(null)} type="button">
              Close
            </button>
          </div>
        </Card>
      )}
      {graph && (
        <GraphCompanionTable
          nodes={visibleNodes}
          onExpand={(node) => void expand(node)}
          onSelect={(node) => void openDetail(node)}
        />
      )}
    </div>
  );
}

export function GraphCompanionTable({
  nodes,
  onSelect,
  onExpand,
}: {
  nodes: GraphNode[];
  onSelect: (node: GraphNode) => void;
  onExpand: (node: GraphNode) => void;
}) {
  return (
    <Card>
      <div className="section-heading">
        <div>
          <p className="eyebrow">Accessible companion view</p>
          <h2>Graph nodes</h2>
        </div>
        <span className="metadata">{nodes.length} visible</span>
      </div>
      {nodes.length === 0 ? (
        <StateMessage kind="empty">No nodes to navigate.</StateMessage>
      ) : (
        <div className="table-wrap">
          <table>
            <caption className="sr-only">Same nodes shown in the graph projection</caption>
            <thead>
              <tr>
                <th>Label</th>
                <th>Type</th>
                <th>State</th>
                <th>Evidence</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {nodes.map((node) => (
                <tr key={node.handle}>
                  <td>{node.label}</td>
                  <td>{node.semanticType}</td>
                  <td>
                    <StatusBadge status={`${node.verificationState} · ${node.lifecycleState}`} />
                  </td>
                  <td>{node.evidenceCount}</td>
                  <td>
                    <div className="toolbar-actions">
                      <button className="secondary" onClick={() => onSelect(node)} type="button">
                        Open detail
                      </button>
                      <button className="secondary" onClick={() => onExpand(node)} type="button">
                        Expand
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
