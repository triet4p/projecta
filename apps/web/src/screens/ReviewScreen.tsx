import { useEffect, useState } from "react";

import type { ProjectaApiClient } from "../api/client";
import type {
  CandidateEditOptionsResponse,
  CandidateQueueItem,
  CandidateQueueResponse,
  DecisionResponse,
  ValidationResult,
} from "../api/generated";
import { canConfirmRequirement } from "../form-state";
import { Card, ErrorMessage, operationKey, StateMessage, StatusBadge } from "../ui";

export function ReviewScreen({
  api,
  projectHandle,
}: {
  api: ProjectaApiClient;
  projectHandle: string;
}) {
  const [queue, setQueue] = useState<CandidateQueueResponse | null>(null);
  const [editOptions, setEditOptions] = useState<CandidateEditOptionsResponse | null>(null);
  const [selected, setSelected] = useState<CandidateQueueItem | null>(null);
  const [validation, setValidation] = useState<ValidationResult | null>(null);
  const [decision, setDecision] = useState<DecisionResponse | null>(null);
  const [label, setLabel] = useState("");
  const [editType, setEditType] = useState("");
  const [editRelation, setEditRelation] = useState("");
  const [editEntityLink, setEditEntityLink] = useState("");
  const [editDate, setEditDate] = useState("");
  const [editAssignment, setEditAssignment] = useState("");
  const [editRevision, setEditRevision] = useState(1);
  const [editNotice, setEditNotice] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const loadQueue = async () => {
    setBusy(true);
    setError(null);
    try {
      const [nextQueue, nextOptions] = await Promise.all([
        api.listCandidateQueue(projectHandle),
        api.getCandidateEditOptions(projectHandle),
      ]);
      setQueue(nextQueue);
      setEditOptions(nextOptions);
    } catch (nextError) {
      setError(nextError);
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    void loadQueue();
  }, [projectHandle]);

  const select = (candidate: CandidateQueueItem) => {
    setSelected(candidate);
    setValidation(null);
    setDecision(null);
    setLabel(candidate.label);
    setEditType(candidate.proposedType);
    setEditRelation("");
    setEditEntityLink("");
    setEditDate("");
    setEditAssignment("");
    setEditRevision(1);
    setEditNotice(null);
    setReason("");
  };

  const validate = async () => {
    if (!selected) return;
    setBusy(true);
    setError(null);
    try {
      setValidation(await api.validateSelectedCandidate(projectHandle, selected.handle));
      setDecision(null);
    } catch (nextError) {
      setError(nextError);
    } finally {
      setBusy(false);
    }
  };

  const confirm = async () => {
    if (!selected || !canConfirmRequirement(validation, label)) return;
    setBusy(true);
    setError(null);
    try {
      setDecision(
        await api.confirmSelectedCandidate(
          projectHandle,
          selected.handle,
          {
            assertion: {
              type: "Requirement",
              label: label.trim(),
              validFrom: editDate || new Date().toISOString().slice(0, 10),
            },
            correctionRevision: validation?.correctionRevision ?? 0,
          },
          operationKey(),
        ),
      );
    } catch (nextError) {
      setError(nextError);
    } finally {
      setBusy(false);
    }
  };

  const reject = async () => {
    if (!selected || !reason.trim()) return;
    setBusy(true);
    setError(null);
    try {
      setDecision(
        await api.rejectSelectedCandidate(
          projectHandle,
          selected.handle,
          { reason: reason.trim() },
          operationKey(),
        ),
      );
    } catch (nextError) {
      setError(nextError);
    } finally {
      setBusy(false);
    }
  };

  const edit = async () => {
    if (!selected) return;
    const payload = {
      ...(editType ? { entityType: editType } : {}),
      ...(editLabelValue() ? { label: editLabelValue() } : {}),
      ...(editRelation ? { relation: editRelation } : {}),
      ...(editEntityLink ? { entityLink: editEntityLink } : {}),
      ...(editDate ? { date: editDate } : {}),
      ...(editAssignment ? { assignment: editAssignment } : {}),
      expectedRevision: editRevision,
    };
    if (Object.keys(payload).length === 1) return;
    setBusy(true);
    setError(null);
    try {
      const recorded = await api.editStructuredCandidate(projectHandle, selected.handle, payload);
      setEditRevision(recorded.revision + 1);
      setLabel(editLabelValue());
      setEditNotice("Correction recorded with provenance. Revalidate before confirmation.");
      setValidation(null);
    } catch (nextError) {
      setError(nextError);
    } finally {
      setBusy(false);
    }
  };

  const editLabelValue = () => label.trim();

  return (
    <div className="screen-grid review-workspace">
      {error !== null && <ErrorMessage error={error} />}
      <Card>
        <div className="section-heading">
          <div>
            <p className="eyebrow">Review queue</p>
            <h2>Pending candidates</h2>
          </div>
          <button
            className="secondary"
            disabled={busy}
            onClick={() => void loadQueue()}
            type="button"
          >
            {busy ? "Refreshing…" : "Refresh"}
          </button>
        </div>
        {!queue && error === null && (
          <StateMessage kind="loading">Loading candidates…</StateMessage>
        )}
        {queue?.stale && (
          <StateMessage kind="empty">
            The review queue is stale. Refresh before deciding.
          </StateMessage>
        )}
        {queue && queue.candidates.length === 0 && (
          <StateMessage kind="empty">No pending candidates need review.</StateMessage>
        )}
        <div className="candidate-queue">
          {queue?.candidates.map((candidate) => (
            <button
              className={
                selected?.handle === candidate.handle
                  ? "candidate-queue-item selected"
                  : "candidate-queue-item"
              }
              key={candidate.handle}
              onClick={() => select(candidate)}
              type="button"
            >
              <strong>{candidate.label}</strong>
              <span>
                {candidate.proposedType} · {candidate.validationState}
              </span>
              <small>{candidate.sourceExcerpt ?? "No source excerpt available"}</small>
              <StatusBadge status={candidate.lifecycleState} />
            </button>
          ))}
        </div>
      </Card>
      <Card>
        {!selected ? (
          <>
            <p className="eyebrow">Candidate decision</p>
            <h2>Select a candidate</h2>
            <StateMessage kind="empty">
              Choose a labeled candidate from the queue to begin validation and review.
            </StateMessage>
          </>
        ) : (
          <>
            <div className="section-heading">
              <div>
                <p className="eyebrow">Candidate review</p>
                <h2>{selected.label}</h2>
              </div>
              <StatusBadge status={selected.lifecycleState} />
            </div>
            <div className="detail-grid">
              <span>
                Proposed type<strong>{selected.proposedType}</strong>
              </span>
              <span>
                Confidence
                <strong>
                  {selected.confidence == null
                    ? "Unavailable"
                    : `${Math.round(selected.confidence * 100)}%`}
                </strong>
              </span>
              <span>
                Evidence<strong>{selected.evidenceCount}</strong>
              </span>
              <span>
                Age<strong>{selected.age ?? "Unavailable"}</strong>
              </span>
            </div>
            <div className="candidate-edit-panel">
              <h3>Structured correction</h3>
              <p className="muted">
                Corrections are audited as proposals; they do not silently change asserted
                knowledge.
              </p>
              <label className="stacked-label">
                Type
                <select value={editType} onChange={(event) => setEditType(event.target.value)}>
                  <option value="">Keep current</option>
                  {[
                    "Requirement",
                    "Decision",
                    "Question",
                    "Task",
                    "Risk",
                    "Assumption",
                    "Constraint",
                    "ProgressClaim",
                    "ResearchFinding",
                  ].map((type) => (
                    <option key={type} value={type}>
                      {type}
                    </option>
                  ))}
                </select>
              </label>
              <label className="stacked-label">
                Label
                <input value={label} onChange={(event) => setLabel(event.target.value)} />
              </label>
              <div className="form-grid">
                <label>
                  Relation
                  <select
                    value={editRelation}
                    onChange={(event) => setEditRelation(event.target.value)}
                  >
                    <option value="">None</option>
                    {[
                      "implements",
                      "blocks",
                      "dependsOn",
                      "supports",
                      "answers",
                      "resolves",
                      "constrainedBy",
                    ].map((relation) => (
                      <option key={relation} value={relation}>
                        {relation}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Date
                  <input
                    type="date"
                    value={editDate}
                    onChange={(event) => setEditDate(event.target.value)}
                  />
                </label>
                <label>
                  Entity link
                  <select
                    value={editEntityLink}
                    onChange={(event) => setEditEntityLink(event.target.value)}
                  >
                    <option value="">No entity link</option>
                    {editOptions?.entityLinks.map((option) => (
                      <option key={option.handle} value={option.handle}>
                        {option.label} · {option.type}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Assignment
                  <select
                    value={editAssignment}
                    onChange={(event) => setEditAssignment(event.target.value)}
                  >
                    <option value="">No assignment proposal</option>
                    {editOptions?.assignments.map((option) => (
                      <option key={option.handle} value={option.handle}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <button
                className="secondary"
                disabled={busy || !label.trim()}
                onClick={() => void edit()}
                type="button"
              >
                Save correction
              </button>
              {editNotice && <StateMessage kind="success">{editNotice}</StateMessage>}
            </div>
            <button disabled={busy} onClick={() => void validate()} type="button">
              {busy ? "Working…" : "Validate selected candidate"}
            </button>
            {validation && (
              <div className="validation-result">
                <strong>
                  {validation.conforms ? "Validation passed" : "Validation needs attention"}
                </strong>
                {!validation.conforms && (
                  <pre className="safe-json">{JSON.stringify(validation.violations, null, 2)}</pre>
                )}
              </div>
            )}
            {validation?.conforms && !decision && (
              <>
                <button
                  disabled={
                    busy || editType !== "Requirement" || !canConfirmRequirement(validation, label)
                  }
                  onClick={() => void confirm()}
                  type="button"
                >
                  Confirm Requirement
                </button>
                <label className="stacked-label">
                  Rejection reason
                  <textarea
                    rows={4}
                    value={reason}
                    onChange={(event) => setReason(event.target.value)}
                  />
                </label>
                <button
                  className="danger"
                  disabled={busy || !reason.trim()}
                  onClick={() => void reject()}
                  type="button"
                >
                  Reject candidate
                </button>
              </>
            )}
            {decision && (
              <StateMessage kind="success">
                Decision recorded: {decision.decision}. The queue will refresh on the next review.
              </StateMessage>
            )}
          </>
        )}
      </Card>
    </div>
  );
}
