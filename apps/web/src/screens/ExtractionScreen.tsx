import { useState } from "react";

import type { ProjectaApiClient } from "../api/client";
import type { ExtractionResult } from "../api/generated";
import { Card, ErrorMessage, operationKey, StateMessage } from "../ui";

export function ExtractionScreen({
  api,
  onCandidate,
}: {
  api: ProjectaApiClient;
  onCandidate: (id: string) => void;
}) {
  const [rawText, setRawText] = useState("");
  const [result, setResult] = useState<ExtractionResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const submit = async () => {
    if (!rawText.trim()) return;
    setBusy(true);
    setError(null);
    try {
      setResult(
        await api.extractQuickNote(
          { rawText: rawText.replace(/\r\n?/g, "\n"), extractionVersion: "m3.v1" },
          operationKey(),
        ),
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
        <p className="eyebrow">M3 extraction</p>
        <h2>Extract a quick note</h2>
        <p className="muted">
          The server normalizes line endings and validates exact Unicode code-point evidence.
        </p>
        <label className="stacked-label">
          Raw note
          <textarea
            aria-label="Raw note"
            value={rawText}
            onChange={(event) => setRawText(event.target.value)}
            rows={12}
            placeholder="Write a project note…"
          />
        </label>
        {error !== null && <ErrorMessage error={error} />}
        <button disabled={busy || !rawText.trim()} onClick={() => void submit()} type="button">
          {busy ? "Extracting…" : "Extract note"}
        </button>
      </Card>
      <Card>
        <p className="eyebrow">Result</p>
        <h2>Normalized evidence</h2>
        {!result && (
          <StateMessage kind="empty">
            Submit a note to see candidates, entities, relations, links, and abstention.
          </StateMessage>
        )}
        {result?.abstentionReason && (
          <StateMessage kind="empty">Extraction abstained: {result.abstentionReason}</StateMessage>
        )}
        {result && (
          <div className="result-stack">
            <p className="metadata">
              Request {result.requestId} · note {result.note.id}
            </p>
            {result.candidates.map((candidate) => (
              <button
                className="candidate-chip"
                key={candidate.id}
                onClick={() => onCandidate(candidate.id)}
                type="button"
              >
                Review candidate {candidate.id} · {candidate.status}
              </button>
            ))}
            {result.entities?.map((entity, index) => (
              <EvidenceRow
                key={`entity-${index}`}
                label={`${entity.type}: ${entity.label}`}
                evidence={entity.evidence}
              />
            ))}
            {result.relations?.map((relation, index) => (
              <EvidenceRow
                key={`relation-${index}`}
                label={`${relation.predicate}: ${relation.sourceEntityId} → ${relation.targetEntityId}`}
                evidence={relation.evidence}
              />
            ))}
            {result.links?.map((link, index) => (
              <EvidenceRow
                key={`link-${index}`}
                label={`Link: ${link.mention} → ${link.targetEntityId}`}
                evidence={link.evidence}
              />
            ))}
            {result.entities?.length === 0 && !result.abstentionReason && (
              <StateMessage kind="empty">No entities were extracted.</StateMessage>
            )}
          </div>
        )}
      </Card>
    </div>
  );
}

function EvidenceRow({
  label,
  evidence,
}: {
  label: string;
  evidence: { startOffset: number; endOffset: number; text: string };
}) {
  return (
    <div className="evidence-row">
      <strong>{label}</strong>
      <span>{evidence.text}</span>
      <small>
        code points {evidence.startOffset}–{evidence.endOffset}
      </small>
    </div>
  );
}
