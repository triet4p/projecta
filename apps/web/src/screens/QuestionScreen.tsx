import { useState } from "react";

import type { ProjectaApiClient } from "../api/client";
import type { Answer } from "../api/generated";
import { Card, ErrorMessage, SafeJson, StateMessage } from "../ui";

export function QuestionScreen({ api }: { api: ProjectaApiClient }) {
  const [question, setQuestion] = useState("");
  const [limit, setLimit] = useState(50);
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const ask = async () => {
    if (!question.trim()) return;
    setBusy(true);
    setError(null);
    try {
      setAnswer(await api.answerProjectContext({ question: question.trim(), limit }));
    } catch (nextError) {
      setError(nextError);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="screen-grid two-column">
      <Card>
        <p className="eyebrow">M4 grounded Q&A</p>
        <h2>Ask about this project</h2>
        <p className="muted">
          Ask a bounded natural-language question. SPARQL and arbitrary filters are not accepted
          here.
        </p>
        <label className="stacked-label">
          Question
          <textarea
            aria-label="Project question"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            rows={7}
            placeholder="What are the current requirements?"
          />
        </label>
        <label>
          Fact limit
          <input
            max={100}
            min={1}
            onChange={(event) =>
              setLimit(Math.max(1, Math.min(100, Number(event.target.value) || 1)))
            }
            type="number"
            value={limit}
          />
        </label>
        {error !== null && <ErrorMessage error={error} />}
        <button disabled={busy || !question.trim()} onClick={() => void ask()} type="button">
          {busy ? "Grounding…" : "Ask question"}
        </button>
      </Card>
      <Card>
        <p className="eyebrow">Answer</p>
        <h2>Evidence-backed response</h2>
        {!answer && (
          <StateMessage kind="empty">
            Your answer, completeness, citations, and freshness warnings will appear here.
          </StateMessage>
        )}
        {answer && (
          <div className="result-stack">
            <div className="answer-status">
              <span className={answer.complete ? "health-pill healthy" : "health-pill unavailable"}>
                {answer.complete ? "complete" : "partial"}
              </span>
              {answer.abstained && <span className="health-pill unavailable">abstained</span>}
            </div>
            <p className="answer-text">{answer.text}</p>
            {answer.warnings.map((warning) => (
              <StateMessage kind="empty" key={warning}>
                {warning}
              </StateMessage>
            ))}
            <h3>Facts</h3>
            {answer.facts.length ? (
              <SafeJson value={answer.facts} />
            ) : (
              <StateMessage kind="empty">No grounded facts were returned.</StateMessage>
            )}
            <h3>Citations and derivation</h3>
            {answer.citations.length ? (
              <SafeJson value={answer.citations} />
            ) : (
              <StateMessage kind="empty">No citations were returned.</StateMessage>
            )}
            <SafeJson value={answer.meta} />
          </div>
        )}
      </Card>
    </div>
  );
}
