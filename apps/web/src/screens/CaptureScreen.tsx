import { useRef, useState } from "react";

import type { ProjectaApiClient } from "../api/client";
import type { CaptureResponse, EntityType, TypedSegment } from "../api/generated";
import { canCapture } from "../form-state";
import { Card, ErrorMessage, operationKey, StateMessage } from "../ui";
import { canAddSegment, normalizeNoteText, selectedTypedSegment } from "../workflows";

const types: EntityType[] = [
  "requirement",
  "decision",
  "question",
  "task",
  "risk",
  "assumption",
  "constraint",
  "progress-update",
  "research-need",
];

export function CaptureScreen({
  api,
  onCandidate,
}: {
  api: ProjectaApiClient;
  onCandidate: (id: string) => void;
}) {
  const [rawText, setRawText] = useState("");
  const [type, setType] = useState<EntityType>("requirement");
  const [segments, setSegments] = useState<TypedSegment[]>([]);
  const [selection, setSelection] = useState({ start: 0, end: 0 });
  const [result, setResult] = useState<CaptureResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const syncSelection = () => {
    const textarea = textareaRef.current;
    if (textarea === null) return;
    setSelection({ start: textarea.selectionStart, end: textarea.selectionEnd });
  };

  const addSelection = () => {
    const textarea = textareaRef.current;
    const start = textarea?.selectionStart ?? selection.start;
    const end = textarea?.selectionEnd ?? selection.end;
    const next = selectedTypedSegment(rawText, start, end, type);
    if (!next || !canAddSegment(segments, next)) {
      setError(new Error("Choose one ordered, non-overlapping exact span."));
      return;
    }
    setSegments([...segments, next].sort((left, right) => left.startOffset - right.startOffset));
    setError(null);
  };

  const submit = async () => {
    const normalized = normalizeNoteText(rawText);
    if (!canCapture(normalized, segments.length)) {
      setError(new Error("Add at least one exact evidence span before capture."));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      setResult(await api.captureQuickNote({ rawText: normalized, segments }, operationKey()));
    } catch (nextError) {
      setError(nextError);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="screen-grid two-column">
      <Card>
        <p className="eyebrow">M2 typed capture</p>
        <h2>Capture exact evidence</h2>
        <p className="muted">
          Select text in the note, choose its released type, then add the exact span.
        </p>
        <label className="stacked-label">
          Raw note
          <textarea
            ref={textareaRef}
            aria-label="Capture note"
            onKeyUp={syncSelection}
            onMouseUp={syncSelection}
            onSelect={syncSelection}
            onChange={(event) => {
              setRawText(normalizeNoteText(event.target.value));
              setSegments([]);
              setResult(null);
            }}
            rows={10}
            value={rawText}
            placeholder="Type a note, then select a span…"
          />
        </label>
        <div className="inline-form">
          <label>
            Type
            <select value={type} onChange={(event) => setType(event.target.value as EntityType)}>
              {types.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>
          <button
            className="secondary"
            disabled={!rawText || selection.start === selection.end}
            onClick={addSelection}
            type="button"
          >
            Add selected span
          </button>
        </div>
        {error !== null && <ErrorMessage error={error} />}
        <div className="segment-list">
          {segments.map((segment) => (
            <div className="segment" key={`${segment.startOffset}-${segment.endOffset}`}>
              <span>{segment.type}</span>
              <strong>{segment.text}</strong>
              <small>
                {segment.startOffset}–{segment.endOffset}
              </small>
              <button
                aria-label={`Remove ${segment.text}`}
                onClick={() => setSegments(segments.filter((item) => item !== segment))}
                type="button"
              >
                ×
              </button>
            </div>
          ))}
        </div>
        <button
          disabled={busy || !canCapture(rawText, segments.length)}
          onClick={() => void submit()}
          type="button"
        >
          {busy ? "Capturing…" : "Capture note"}
        </button>
      </Card>
      <Card>
        <p className="eyebrow">Result</p>
        <h2>Reviewable candidates</h2>
        {!result && (
          <StateMessage kind="empty">
            Your captured note and candidates will appear here.
          </StateMessage>
        )}
        {result && (
          <div className="result-stack">
            <p className="metadata">Request {result.requestId} · captured note ready for review</p>
            {result.candidates.map((candidate) => (
              <button
                className="candidate-chip"
                key={candidate.id}
                onClick={() => onCandidate(candidate.id)}
                type="button"
              >
                Open review queue · {candidate.status}
              </button>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
