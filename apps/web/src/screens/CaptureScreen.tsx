import { useEffect, useRef, useState } from "react";

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

export interface CaptureDraft {
  rawText: string;
  type: EntityType;
  segments: TypedSegment[];
}

export function CaptureScreen({
  api,
  onCandidate,
  draft,
  onDraftChange,
}: {
  api: ProjectaApiClient;
  onCandidate: (handle: string) => void;
  draft: CaptureDraft | null;
  onDraftChange: (draft: CaptureDraft | null) => void;
}) {
  const [rawText, setRawText] = useState(draft?.rawText ?? "");
  const [type, setType] = useState<EntityType>(draft?.type ?? "requirement");
  const [segments, setSegments] = useState<TypedSegment[]>(draft?.segments ?? []);
  const [selection, setSelection] = useState({ start: 0, end: 0 });
  const [result, setResult] = useState<CaptureResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (result !== null || (rawText.length === 0 && segments.length === 0)) {
      onDraftChange(null);
      return;
    }
    onDraftChange({ rawText, type, segments });
  }, [onDraftChange, rawText, result, segments, type]);

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
        <p className="eyebrow">Human-selected evidence</p>
        <h2>Select an exact source span</h2>
        <p className="muted">
          Use this path when a particular passage must stay anchored to its source. Select the
          passage itself; its displayed range comes from your selection.
        </p>
        <label className="stacked-label">
          Source note
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
            placeholder="Type or paste a source note, then select an exact span…"
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
        <h2>Capture result</h2>
        {!result && (
          <StateMessage kind="empty">
            Add an exact span, then capture. Returned candidates stay unreviewed until you inspect
            their source and evidence in the Review Queue.
          </StateMessage>
        )}
        {result && (
          <>
            <StateMessage kind="success">
              Capture succeeded.{" "}
              {result.candidates.length === 0
                ? "No review candidate was returned."
                : `${result.candidates.length} candidate${result.candidates.length === 1 ? "" : "s"} returned for review.`}
            </StateMessage>
            <p className="metadata">Request {result.requestId}</p>
            {result.candidates.length > 0 && (
              <>
                <p>
                  <strong>Next step:</strong> open the Review Queue. The candidate you just captured
                  is selected there automatically, so you can inspect its source and evidence before
                  making an explicit decision. Capture does not approve a candidate or materialize
                  graph data.
                </p>
                <div className="result-stack">
                  {result.candidates.map((candidate) => (
                    <button
                      className="candidate-chip"
                      key={candidate.id}
                      onClick={() => onCandidate(candidate.handle)}
                      type="button"
                    >
                      Open Review Queue · {candidate.status}
                    </button>
                  ))}
                </div>
              </>
            )}
          </>
        )}
      </Card>
    </div>
  );
}
