import { type ReactElement, useCallback, useEffect, useState } from "react";

import { ApiError, type ProjectaApiClient } from "../api/client";
import type {
  EntityType,
  StructuredNoteDetail,
  StructuredNoteDraftInput,
  StructuredNoteDraftResponse,
  StructuredNoteListResponse,
} from "../api/generated";
import { Card, ErrorMessage, operationKey, StateMessage, StatusBadge } from "../ui";
import { CaptureScreen, type CaptureDraft } from "./CaptureScreen";
import { moveNoteItem } from "./note-composer";

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

interface Props {
  api: ProjectaApiClient;
  projectHandle: string;
  onCandidate: (candidateHandle: string) => void;
  captureDraft: CaptureDraft | null;
  onCaptureDraftChange: (draft: CaptureDraft | null) => void;
  selectedNote: { handle: string; label: string } | null;
  onClearSelectedNote: () => void;
  onReturnToOverview: () => void;
}

export function NotesScreen({
  api,
  projectHandle,
  onCandidate,
  captureDraft,
  onCaptureDraftChange,
  selectedNote,
  onClearSelectedNote,
  onReturnToOverview,
}: Props): ReactElement {
  const [title, setTitle] = useState("Untitled Note");
  const [items, setItems] = useState<StructuredNoteDraftInput["items"]>([]);
  const [draft, setDraft] = useState<StructuredNoteDraftResponse | null>(null);
  const [notes, setNotes] = useState<StructuredNoteListResponse | null>(null);
  const [detail, setDetail] = useState<StructuredNoteDetail | null>(null);
  const [importText, setImportText] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [manualCaptureOpen, setManualCaptureOpen] = useState(false);
  const [selectedNoteStatus, setSelectedNoteStatus] = useState<
    "idle" | "loading" | "loaded" | "missing" | "unavailable"
  >("idle");
  const [selectedNoteError, setSelectedNoteError] = useState<unknown>(null);
  const [selectedNoteRetry, setSelectedNoteRetry] = useState(0);
  const selectedNoteHandle = selectedNote?.handle ?? null;
  const selectedNoteLabel = selectedNote?.label ?? "";

  const loadNotes = useCallback(async () => {
    try {
      setNotes(await api.listStructuredNotes(projectHandle));
      setError(null);
    } catch (nextError) {
      setError(nextError);
    }
  }, [api, projectHandle]);

  useEffect(() => {
    void loadNotes();
  }, [loadNotes]);
  useEffect(() => {
    if (!selectedNoteHandle) {
      setSelectedNoteStatus("idle");
      setSelectedNoteError(null);
      return;
    }
    let active = true;
    setSelectedNoteStatus("loading");
    setSelectedNoteError(null);
    setDetail(null);
    void api
      .readStructuredNote(projectHandle, selectedNoteHandle)
      .then((record) => {
        if (!active) return;
        if (record.noteHandle !== selectedNoteHandle) {
          setSelectedNoteStatus("unavailable");
          setSelectedNoteError(new Error("The API returned a different Note than the selected one."));
          return;
        }
        setDetail(record);
        setSelectedNoteStatus("loaded");
      })
      .catch((nextError: unknown) => {
        if (!active) return;
        setSelectedNoteStatus(
          nextError instanceof ApiError && nextError.problem.status === 404
            ? "missing"
            : "unavailable",
        );
        setSelectedNoteError(nextError);
      });
    return () => {
      active = false;
    };
  }, [api, projectHandle, selectedNoteHandle, selectedNoteRetry]);

  const payload = (): StructuredNoteDraftInput => ({
    title,
    items,
    draftStatus: draft?.draftStatus ?? "draft",
  });

  const save = async () => {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const saved = draft
        ? await api.updateNoteDraft(projectHandle, draft.draftHandle, payload(), draft.revision)
        : await api.createNoteDraft(projectHandle, payload(), operationKey());
      setDraft(saved);
      setTitle(saved.title);
      setItems(saved.items.map(({ itemType, content }) => ({ itemType, content })));
      setNotice(`Draft saved at revision ${saved.revision}.`);
      await loadNotes();
    } catch (nextError) {
      setError(nextError);
    } finally {
      setBusy(false);
    }
  };

  const commit = async () => {
    if (!draft) {
      setNotice("Save the draft before committing it.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const committed = await api.commitNoteDraft(projectHandle, draft.draftHandle, operationKey());
      setDraft(committed);
      setNotice("Note committed. Source evidence and candidate lifecycle remain separate.");
      await loadNotes();
    } catch (nextError) {
      setError(nextError);
    } finally {
      setBusy(false);
    }
  };

  const importTextIntoComposer = async () => {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const result = await api.importNoteText(projectHandle, importText, title);
      if (result.status === "abstained") {
        setNotice(result.abstentionReason ?? "Import abstained.");
      } else {
        setItems(result.proposals);
        setNotice(
          `${result.proposals.length} editable proposals loaded. Save explicitly to persist.`,
        );
      }
    } catch (nextError) {
      setError(nextError);
    } finally {
      setBusy(false);
    }
  };

  const addItem = () => setItems([...items, { itemType: "task", content: "" }]);
  const updateItem = (index: number, next: Partial<(typeof items)[number]>) =>
    setItems(items.map((item, itemIndex) => (itemIndex === index ? { ...item, ...next } : item)));
  const removeItem = (index: number) =>
    setItems(items.filter((_, itemIndex) => itemIndex !== index));
  const moveItem = (index: number, direction: -1 | 1) =>
    setItems(moveNoteItem(items, index, direction));
  if (manualCaptureOpen) {
    return (
      <div className="workspace-page">
        <div className="workspace-header">
          <div>
            <p className="eyebrow">Notes · exact-span capture</p>
            <h2>Capture exact spans</h2>
            <p className="muted">
              Use this path when a particular passage must stay anchored to its source. A successful
              capture returns a candidate for the Review Queue. Review is a separate decision;
              capture does not approve or materialize the candidate.
            </p>
          </div>
          <button
            className="secondary"
            onClick={() => setManualCaptureOpen(false)}
            type="button"
          >
            Back to Notes
          </button>
        </div>
        <CaptureScreen
          api={api}
          draft={captureDraft}
          onCandidate={onCandidate}
          onDraftChange={onCaptureDraftChange}
        />
      </div>
    );
  }


  return (
    <div className="workspace-page">

      {captureDraft !== null && (
        <Card>
          <StateMessage kind="empty">
            An unfinished source capture is preserved in this session only. It has not been
            submitted and is not a saved Note.
          </StateMessage>
          <div className="button-row">
            <button onClick={() => setManualCaptureOpen(true)} type="button">
              Continue capture
            </button>
            <button
              className="danger"
              onClick={() => onCaptureDraftChange(null)}
              type="button"
            >
              Discard unsubmitted capture
            </button>
          </div>
        </Card>
      )}
      <div className="workspace-header">
        <div>
          <p className="eyebrow">Source notes</p>
          <h2>Notes</h2>
          <p className="muted">
            Choose typed items, editable proposals from pasted text, or an exact source passage.
            Each path has a different save and review outcome.
          </p>
        </div>
      </div>
      {selectedNoteHandle && (
        <Card className="note-selection-context">
          <p className="eyebrow">Project Overview selection</p>
          <h3>{selectedNoteLabel}</h3>
          {selectedNoteStatus === "loading" && (
            <StateMessage kind="loading">Opening this Note in the active project…</StateMessage>
          )}
          {selectedNoteStatus === "loaded" && detail?.noteHandle === selectedNoteHandle && (
            <>
              <StateMessage kind="success">
                The selected Note’s source detail is open below. No candidate decision or Graph
                materialization was made.
              </StateMessage>
              <div className="note-detail">
                <h3>{detail.title}</h3>
                <p className="metadata">
                  {detail.author} · {detail.recordedAt} · {Math.round(detail.evidenceCoverage * 100)}%
                  evidence coverage
                </p>
                {detail.items.map((item) => (
                  <div className="evidence-row" key={`${item.startOffset}-${item.endOffset}`}>
                    <StatusBadge status={item.itemType} />
                    <strong>{item.content}</strong>
                    <small>
                      {item.startOffset}–{item.endOffset}
                    </small>
                  </div>
                ))}
              </div>
            </>
          )}
          {selectedNoteStatus === "missing" && (
            <>
              <StateMessage kind="empty">
                The selected Note could not be found in this project. No other Note was opened.
              </StateMessage>
              {selectedNoteError !== null && <ErrorMessage error={selectedNoteError} />}
            </>
          )}
          {selectedNoteStatus === "unavailable" && (
            <>
              <p className="metadata">
                The selected Note could not be loaded. No other record was substituted.
              </p>
              {selectedNoteError !== null && <ErrorMessage error={selectedNoteError} />}
            </>
          )}
          <div className="button-row">
            {(selectedNoteStatus === "missing" || selectedNoteStatus === "unavailable") && (
              <button
                className="secondary"
                onClick={() => setSelectedNoteRetry((revision) => revision + 1)}
                type="button"
              >
                Retry selected Note
              </button>
            )}
            <button className="secondary" onClick={onReturnToOverview} type="button">
              Back to Project Overview
            </button>
          </div>
        </Card>
      )}
      <section className="note-path-guide" aria-labelledby="note-path-guide-heading">
        <div>
          <p className="eyebrow">Choose a Notes path</p>
          <h3 id="note-path-guide-heading">How do you want to work with this source?</h3>
        </div>
        <div className="note-path-grid">
          <article className="note-path-option">
            <h3>Note Composer</h3>
            <p>
              Use for writing a structured Note from typed items. Save a draft to persist it;
              commit is a separate, deliberate step.
            </p>
            <a className="note-path-action" href="#note-composer">
              Open Note Composer
            </a>
          </article>
          <article className="note-path-option">
            <h3>Assisted import</h3>
            <p>
              Use when you have source text and want editable item proposals. Proposals load into
              the Composer; nothing is saved or committed automatically.
            </p>
            <a className="note-path-action" href="#assisted-import">
              Open Assisted import
            </a>
          </article>
          <article className="note-path-option">
            <h3>Exact-span capture</h3>
            <p>
              Use when a specific passage must remain anchored to its source. Capture creates a
              review candidate, not an approval or graph materialization.
            </p>
            <button
              className="secondary"
              onClick={() => setManualCaptureOpen(true)}
              type="button"
            >
              Capture exact spans
            </button>
          </article>
        </div>
      </section>
      <div className="screen-grid two-column">
        <Card>
          <div className="section-heading" id="note-composer">
            <div>
              <p className="eyebrow">Note Composer</p>
              <h3>Editable typed items</h3>
            </div>
            <StatusBadge status={draft?.draftStatus ?? "draft"} />
          </div>
          <label className="stacked-label">
            Human title
            <input value={title} onChange={(event) => setTitle(event.target.value)} />
          </label>
          <div className="note-composer-list">
            {items.map((item, index) => (
              <div className="note-item-card" key={`${index}-${item.itemType}`}>
                <label>
                  Type
                  <select
                    aria-label={`Item ${index + 1} type`}
                    value={item.itemType}
                    onChange={(event) =>
                      updateItem(index, { itemType: event.target.value as EntityType })
                    }
                  >
                    {types.map((type) => (
                      <option key={type} value={type}>
                        {type}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Source content
                  <textarea
                    aria-label={`Item ${index + 1} content`}
                    rows={3}
                    value={item.content}
                    onChange={(event) => updateItem(index, { content: event.target.value })}
                  />
                </label>
                <div className="button-row">
                  <button
                    className="secondary"
                    disabled={index === 0}
                    onClick={() => moveItem(index, -1)}
                    type="button"
                  >
                    Move up
                  </button>
                  <button
                    className="secondary"
                    disabled={index === items.length - 1}
                    onClick={() => moveItem(index, 1)}
                    type="button"
                  >
                    Move down
                  </button>
                  <button className="danger" onClick={() => removeItem(index)} type="button">
                    Remove
                  </button>
                </div>
              </div>
            ))}
          </div>
          {items.length === 0 && (
            <StateMessage kind="empty">
              Add at least one item before commit. Empty drafts are allowed while editing.
            </StateMessage>
          )}
          <div className="button-row">
            <button className="secondary" onClick={addItem} type="button">
              Add typed item
            </button>
            <button disabled={busy || !title.trim()} onClick={() => void save()} type="button">
              {busy ? "Saving…" : "Save draft"}
            </button>
            <button
              disabled={busy || !draft || items.length === 0 || draft.draftStatus === "committed"}
              onClick={() => void commit()}
              type="button"
            >
              Commit Note
            </button>
          </div>
          {notice && <StateMessage kind="success">{notice}</StateMessage>}
          {error !== null && <ErrorMessage error={error} />}
        </Card>
        <div className="screen-grid">
          <Card>
            <p className="eyebrow">Assisted import</p>
            <h3 id="assisted-import">Paste text for editable proposals</h3>
            <label className="stacked-label">
              Source text
              <textarea
                rows={7}
                value={importText}
                onChange={(event) => setImportText(event.target.value)}
                placeholder="Paste meeting notes…"
              />
            </label>
            <button
              className="secondary"
              disabled={busy || !importText.trim()}
              onClick={() => void importTextIntoComposer()}
              type="button"
            >
              Propose items
            </button>
            <p className="metadata">
              Import never saves automatically. Abstention is shown explicitly.
            </p>
          </Card>
          <Card>
            <p className="eyebrow">Canonical preview</p>
            <h3>Server-derived source body</h3>
            <pre className="note-preview">
              {items.map((item) => item.content.replace(/\r\n|\r/g, "\n")).join("\n") ||
                "No source items yet."}
            </pre>
            <p className="metadata">
              Offsets are calculated at save/commit time and are not user input.
            </p>
          </Card>
        </div>
      </div>
      <Card>
        <div className="section-heading">
          <div>
            <p className="eyebrow">Project Notes</p>
            <h3>Browse by title and source state</h3>
          </div>
          <button className="secondary" onClick={() => void loadNotes()} type="button">
            Refresh
          </button>
        </div>
        {notes?.drafts.length === 0 && notes.committed.length === 0 && (
          <StateMessage kind="empty">No saved drafts or committed Notes.</StateMessage>
        )}
        <div className="note-browse-grid">
          {notes?.drafts.map((item) => (
            <button
              className="note-list-item"
              key={item.draftHandle}
              onClick={() => {
                onClearSelectedNote();
                setDetail(null);
                setDraft(item);
                setTitle(item.title);
                setItems(item.items.map(({ itemType, content }) => ({ itemType, content })));
              }}
              type="button"
            >
              <strong>{item.title}</strong>
              <span>
                Draft · revision {item.revision} · {item.items.length} items
              </span>
            </button>
          ))}
          {notes?.committed.map((item) => (
            <button
              className="note-list-item"
              key={item.handle}
              onClick={() => {
                if (item.handle !== selectedNoteHandle) onClearSelectedNote();
                setDetail(null);
                setError(null);
                void api
                  .readStructuredNote(projectHandle, item.handle)
                  .then(setDetail)
                  .catch(setError);
              }}
              type="button"
            >
              <strong>{item.title}</strong>
              <span>
                {item.author ?? "Author unavailable"} · {item.itemTypeSummary.join(", ")}
              </span>
              <small>{Math.round((item.evidenceCoverage ?? 0) * 100)}% evidence coverage</small>
            </button>
          ))}
        </div>
        {detail && detail.noteHandle !== selectedNoteHandle && (
          <div className="note-detail">
            <div className="section-heading">
              <h3>{detail.title}</h3>
              <button
                className="secondary"
                onClick={() => {
                  setDetail(null);
                  onClearSelectedNote();
                }}
                type="button"
              >
                Close detail
              </button>
            </div>
            <p className="metadata">
              {detail.author} · {detail.recordedAt} · {Math.round(detail.evidenceCoverage * 100)}%
              evidence coverage
            </p>
            {detail.items.map((item) => (
              <div className="evidence-row" key={`${item.startOffset}-${item.endOffset}`}>
                <StatusBadge status={item.itemType} />
                <strong>{item.content}</strong>
                <small>
                  {item.startOffset}–{item.endOffset}
                </small>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
