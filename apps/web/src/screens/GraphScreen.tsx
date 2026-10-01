import { useEffect, useMemo, useState } from "react";

import type { ProjectaApiClient } from "../api/client";
import type { GraphNode, GraphNodeDetail, GraphProjectionResponse } from "../api/generated";
import { Card, ErrorMessage, StateMessage, StatusBadge } from "../ui";

const types = ["All", "Requirement", "Question", "Task", "Risk", "Decision", "Note"] as const;
const states = ["All", "candidate", "asserted", "inferred", "unverified"] as const;
const relations = ["All", "supports", "blocks", "dependsOn", "implements", "derivedFrom"] as const;
const lifecycles = ["All", "current", "pending-review", "confirmed", "rejected", "stale"] as const;
const provenances = [
  "All",
  "source-backed",
  "human-confirmed",
  "rule-derived",
  "candidate-proposed",
] as const;
interface GraphPoint {
  x: number;
  y: number;
}

interface GraphEdgeGeometry {
  path: string;
  arrowheadPoints: string;
  selfLoop: boolean;
}

const GRAPH_NODE_HALF_WIDTH = 85;
const GRAPH_NODE_HALF_HEIGHT = 36;
const GRAPH_ARROW_LENGTH = 12;
const GRAPH_ARROW_HALF_WIDTH = 5;
const SELF_EDGE_DIRECTION_LENGTH = Math.hypot(44, 48);

function graphNodeCenter(index: number): GraphPoint {
  return { x: 120 + (index % 4) * 210, y: 70 + Math.floor(index / 4) * 130 };
}

function graphEdgeGeometry(sourceIndex: number, targetIndex: number): GraphEdgeGeometry {
  const source = graphNodeCenter(sourceIndex);
  const target = graphNodeCenter(targetIndex);
  const dx = target.x - source.x;
  const dy = target.y - source.y;
  const distance = Math.hypot(dx, dy);
  const selfLoop = sourceIndex === targetIndex || distance === 0;

  const boundaryScale = selfLoop
    ? 0
    : 1 / Math.max(Math.abs(dx) / GRAPH_NODE_HALF_WIDTH, Math.abs(dy) / GRAPH_NODE_HALF_HEIGHT);
  const direction = selfLoop
    ? { x: -44 / SELF_EDGE_DIRECTION_LENGTH, y: 48 / SELF_EDGE_DIRECTION_LENGTH }
    : { x: dx / distance, y: dy / distance };
  const tip = selfLoop
    ? { x: target.x + 24, y: target.y - GRAPH_NODE_HALF_HEIGHT }
    : { x: target.x - dx * boundaryScale, y: target.y - dy * boundaryScale };
  const base = {
    x: tip.x - direction.x * GRAPH_ARROW_LENGTH,
    y: tip.y - direction.y * GRAPH_ARROW_LENGTH,
  };
  const perpendicular = { x: -direction.y, y: direction.x };
  const baseA = {
    x: base.x + perpendicular.x * GRAPH_ARROW_HALF_WIDTH,
    y: base.y + perpendicular.y * GRAPH_ARROW_HALF_WIDTH,
  };
  const baseB = {
    x: base.x - perpendicular.x * GRAPH_ARROW_HALF_WIDTH,
    y: base.y - perpendicular.y * GRAPH_ARROW_HALF_WIDTH,
  };
  const arrowheadPoints = `${tip.x},${tip.y} ${baseA.x},${baseA.y} ${baseB.x},${baseB.y}`;

  if (selfLoop) {
    const start = { x: source.x - 24, y: source.y - GRAPH_NODE_HALF_HEIGHT };
    const control1 = { x: source.x - 48, y: source.y - 66 };
    const control2 = {
      x: base.x - direction.x * 20,
      y: base.y - direction.y * 20,
    };
    return {
      path: `M ${start.x} ${start.y} C ${control1.x} ${control1.y}, ${control2.x} ${control2.y}, ${base.x} ${base.y}`,
      arrowheadPoints,
      selfLoop,
    };
  }

  const start = { x: source.x + dx * boundaryScale, y: source.y + dy * boundaryScale };
  return {
    path: `M ${start.x} ${start.y} L ${base.x} ${base.y}`,
    arrowheadPoints,
    selfLoop,
  };
}


export function GraphScreen({
  api,
  projectHandle,
  selectedItem,
  onClearSelectedItem,
  onReturnToOverview,
}: {
  api: ProjectaApiClient;
  projectHandle: string;
  selectedItem: { handle: string; label: string } | null;
  onClearSelectedItem: () => void;
  onReturnToOverview: () => void;
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
  const [selectionStatus, setSelectionStatus] = useState<
    "idle" | "loading" | "loaded" | "unavailable"
  >("idle");
  const [selectionError, setSelectionError] = useState<unknown>(null);
  const selectedItemHandle = selectedItem?.handle;

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

  useEffect(() => {
    if (!selectedItemHandle) {
      setSelectionStatus("idle");
      setSelectionError(null);
      setDetail(null);
      return;
    }
    let active = true;
    setSelectionStatus("loading");
    setSelectionError(null);
    setDetail(null);
    void api
      .getGraphNodeDetail(projectHandle, selectedItemHandle)
      .then((nextDetail) => {
        if (!active) return;
        setDetail(nextDetail);
        setSelectionStatus("loaded");
      })
      .catch((nextError: unknown) => {
        if (!active) return;
        setSelectionError(nextError);
        setSelectionStatus("unavailable");
      });
    return () => {
      active = false;
    };
  }, [api, projectHandle, selectedItemHandle]);

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
    onClearSelectedItem();
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
      {selectedItem && (
        <Card className="graph-selection-context">
          <p className="eyebrow">Project Overview selection</p>
          <h3>{selectedItem.label}</h3>
          {selectionStatus === "loading" && (
            <StateMessage kind="loading">
              Opening this item in the selected project's Graph…
            </StateMessage>
          )}
          {selectionStatus === "loaded" && (
            <StateMessage kind="success">
              The matching project-scoped detail is open below. Graph inspection is read-only;
              no review decision or graph write was made.
            </StateMessage>
          )}
          {selectionStatus === "unavailable" && (
            <>
              <StateMessage kind="empty">
                This overview item could not be opened in the selected project's Graph. The project
                context is unchanged; clear this selection to browse the available projection.
              </StateMessage>
              {selectionError !== null && <ErrorMessage error={selectionError} />}
            </>
          )}
          <div className="toolbar-actions">
            <button className="secondary" onClick={onClearSelectedItem} type="button">
              Browse Graph
            </button>
            <button className="secondary" onClick={onReturnToOverview} type="button">
              Back to Project Overview
            </button>
          </div>
        </Card>
      )}
      <Card>
        <div className="section-heading">
          <div>
            <p className="eyebrow">Project graph</p>
            <h2>Finite knowledge projection</h2>
          </div>
          <div className="toolbar-actions">
            <button className="secondary" onClick={onReturnToOverview} type="button">
              Back to Project Overview
            </button>
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
          <div className="graph-canvas-wrap">
            <svg
              aria-label="Directed project graph. Node verification and lifecycle states are shown in each node."
              className="graph-canvas"
              height="360"
              role="group"
              viewBox="0 0 900 360"
              width="900"
              style={{ transform: `scale(${scale})` }}
            >
              {visibleEdges.map((edge) => {
                const source = visibleNodes.findIndex((node) => node.handle === edge.sourceHandle);
                const target = visibleNodes.findIndex((node) => node.handle === edge.targetHandle);
                if (source < 0 || target < 0) return null;
                const { x: x1, y: y1 } = graphNodeCenter(source);
                const { x: x2, y: y2 } = graphNodeCenter(target);
                const geometry = graphEdgeGeometry(source, target);
                return (
                  <g className={`graph-edge-group ${edge.verificationState}`} key={edge.handle}>
                    <path
                      aria-hidden="true"
                      className={`graph-edge ${edge.verificationState}`}
                      d={geometry.path}
                    />
                    <polygon
                      aria-hidden="true"
                      className={`graph-edge-arrowhead ${edge.verificationState}`}
                      points={geometry.arrowheadPoints}
                    />
                    <text
                      className="graph-edge-label"
                      textAnchor="middle"
                      x={geometry.selfLoop ? x1 : (x1 + x2) / 2}
                      y={
                        geometry.selfLoop
                          ? y1 + 54
                          : y1 === y2
                            ? y1 - 42
                            : (y1 + y2) / 2 - 8
                      }
                    >
                      {edge.relationType}
                    </text>
                  </g>
                );
              })}
              {visibleNodes.map((node, index) => {
                const { x, y } = graphNodeCenter(index);
                const selected = detail?.handle === node.handle;
                const visibleLabel =
                  node.label.length > 23 ? `${node.label.slice(0, 22)}…` : node.label;
                return (
                  <g
                    aria-label={`${node.label}. ${node.semanticType}; ${node.verificationState}; ${node.lifecycleState}.`}
                    aria-pressed={selected}
                    className={`graph-node ${node.verificationState}${selected ? " selected" : ""}`}
                    key={node.handle}
                    onClick={() => void openDetail(node)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        void openDetail(node);
                      }
                    }}
                    role="button"
                    tabIndex={0}
                  >
                    <title>{node.label}</title>
                    <rect
                      className="graph-node-frame"
                      height="72"
                      rx="8"
                      width="170"
                      x={x - 85}
                      y={y - 36}
                    />
                    {selected && (
                      <rect
                        className="graph-node-selected-ring"
                        height="82"
                        rx="11"
                        width="180"
                        x={x - 90}
                        y={y - 41}
                      />
                    )}
                    <rect
                      className="graph-node-focus-ring"
                      height="88"
                      rx="13"
                      width="186"
                      x={x - 93}
                      y={y - 44}
                    />
                    <text className="graph-node-label" textAnchor="middle" x={x} y={y - 13}>
                      {visibleLabel}
                    </text>
                    <text className="graph-node-type" textAnchor="middle" x={x} y={y + 5}>
                      {node.semanticType}
                    </text>
                    <text
                      className={`graph-node-state ${node.verificationState}`}
                      textAnchor="middle"
                      x={x}
                      y={y + 23}
                    >
                      {node.verificationState} · {node.lifecycleState}
                    </text>
                  </g>
                );
              })}
            </svg>
          </div>
        )}
        <div className="graph-legend" aria-label="Graph legend" role="group">
          <span>
            <span aria-hidden="true" className="legend-marker asserted">
              A
            </span>
            Asserted (solid outline)
          </span>
          <span>
            <span aria-hidden="true" className="legend-marker inferred">
              I
            </span>
            Inferred (dashed outline)
          </span>
          <span>
            <span aria-hidden="true" className="legend-marker candidate">
              C
            </span>
            Candidate (long-dashed outline)
          </span>
          <span>
            <span aria-hidden="true" className="legend-marker unverified">
              U
            </span>
            Unverified (dotted outline)
          </span>
          <span>
            <span aria-hidden="true" className="legend-marker selected">
              S
            </span>
            Selected (dashed outer ring)
          </span>
          <span>
            <span aria-hidden="true" className="legend-marker hovered">
              H
            </span>
            Hovered (heavier outline)
          </span>
          <span>
            <span aria-hidden="true" className="legend-marker focused">
              F
            </span>
            Keyboard focus (dotted outer ring)
          </span>
          <span>
            <span aria-hidden="true" className="legend-arrow">
              →
            </span>
            Directed relation; edge labels name the relation.
          </span>
          <span>Click or press Enter/Space on a node for detail.</span>
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
            <button
              className="secondary"
              onClick={() => {
                setDetail(null);
                if (selectedItem) onClearSelectedItem();
              }}
              type="button"
            >
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
