import { useEffect, useState } from "react";

import type { ProjectaApiClient } from "../api/client";
import type { DecisionResponse, ValidationResult } from "../api/generated";
import { canConfirmRequirement } from "../form-state";
import { Card, ErrorMessage, operationKey, StateMessage } from "../ui";

export function ReviewScreen({
  api,
  initialCandidateId,
}: {
  api: ProjectaApiClient;
  initialCandidateId: string;
}) {
  const [candidateId, setCandidateId] = useState(initialCandidateId);
  const [validation, setValidation] = useState<ValidationResult | null>(null);
  const [decision, setDecision] = useState<DecisionResponse | null>(null);
  const [label, setLabel] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    setCandidateId(initialCandidateId);
    setValidation(null);
    setDecision(null);
  }, [initialCandidateId]);

  const validate = async () => {
    if (!candidateId.trim()) return;
    setBusy(true);
    setError(null);
    try {
      setValidation(await api.validateCandidate(candidateId.trim()));
      setDecision(null);
    } catch (nextError) {
      setError(nextError);
    } finally {
      setBusy(false);
    }
  };

  const confirm = async () => {
    if (!canConfirmRequirement(validation, label)) return;
    setBusy(true);
    setError(null);
    try {
      setDecision(
        await api.confirmCandidate(
          candidateId,
          {
            assertion: {
              type: "Requirement",
              label: label.trim(),
              validFrom: new Date().toISOString().slice(0, 10),
            },
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
    if (!validation?.conforms || !reason.trim()) return;
    setBusy(true);
    setError(null);
    try {
      setDecision(
        await api.rejectCandidate(candidateId, { reason: reason.trim() }, operationKey()),
      );
    } catch (nextError) {
      setError(nextError);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="screen-grid two-column">
      <Card>
        <p className="eyebrow">Candidate review</p>
        <h2>Validate one candidate</h2>
        <label className="stacked-label">
          Opaque candidate ID
          <input
            value={candidateId}
            onChange={(event) => {
              setCandidateId(event.target.value);
              setValidation(null);
              setDecision(null);
            }}
            placeholder="candidate ID"
          />
        </label>
        <button
          disabled={busy || !candidateId.trim()}
          onClick={() => void validate()}
          type="button"
        >
          {busy ? "Working…" : "Validate candidate"}
        </button>
        {error !== null && <ErrorMessage error={error} />}
        {validation && (
          <div className="validation-result">
            <strong>{validation.conforms ? "Conforms" : "Does not conform"}</strong>
            <span>Validated at {validation.validatedAt}</span>
            {validation.violations.length > 0 && (
              <pre className="safe-json">{JSON.stringify(validation.violations, null, 2)}</pre>
            )}
          </div>
        )}
      </Card>
      <Card>
        <p className="eyebrow">Requirement-only decision</p>
        <h2>Choose a lifecycle action</h2>
        {!validation && (
          <StateMessage kind="empty">Validate a candidate before deciding.</StateMessage>
        )}
        {validation && !validation.conforms && (
          <StateMessage kind="error">
            This candidate cannot be decided until validation conforms.
          </StateMessage>
        )}
        {validation?.conforms && !decision && (
          <>
            <label className="stacked-label">
              Requirement label
              <input
                value={label}
                onChange={(event) => setLabel(event.target.value)}
                placeholder="A human-confirmed requirement"
              />
            </label>
            <button
              disabled={busy || !canConfirmRequirement(validation, label)}
              onClick={() => void confirm()}
              type="button"
            >
              Confirm Requirement
            </button>
            <label className="stacked-label">
              Rejection reason
              <textarea
                value={reason}
                onChange={(event) => setReason(event.target.value)}
                rows={4}
                placeholder="Why should this candidate be rejected?"
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
            Decision recorded: {decision.decision}. This review is locked to prevent a double
            decision.
          </StateMessage>
        )}
      </Card>
    </div>
  );
}
