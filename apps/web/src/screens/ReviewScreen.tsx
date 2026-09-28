import { useEffect, useState } from "react";

import type { ProjectaApiClient } from "../api/client";
import type {
  CandidateEditOptionsResponse,
  CandidateQueueItem,
  CandidateQueueResponse,
  DecisionResponse,
  ReviewAbstainResponse,
  ValidationResult,
} from "../api/generated";
import type {
  ControlledRelationDecisionRequest,
  ControlledRelationMode,
  ControlledRelationRequest,
  LocalSuggestionDecisionRequest,
  LocalSuggestionResponse,
  ManualCaptureApprovalResponse,
  ManualCaptureRejectionResponse,
  ManualReviewWorkbenchDetailResponse,
  RelationDirection,
  RelationSuggestionTargetsResponse,
} from "../api/manual-capture";
import { canConfirmRequirement } from "../form-state";
import { reviewDecisionDisabled, reviewStatusLabel } from "./review-workbench";
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
  const [detail, setDetail] = useState<ManualReviewWorkbenchDetailResponse | null>(null);
  const [detailBusy, setDetailBusy] = useState(false);
  const [abstainNotice, setAbstainNotice] = useState<string | null>(null);
  const [abstainReceipt, setAbstainReceipt] = useState<ReviewAbstainResponse | null>(null);
  const [manualApproval, setManualApproval] = useState<ManualCaptureApprovalResponse | null>(null);
  const [localSuggestion, setLocalSuggestion] = useState<LocalSuggestionResponse | null>(null);
  const [localSuggestionBusy, setLocalSuggestionBusy] = useState(false);
  const [relationTargets, setRelationTargets] = useState<RelationSuggestionTargetsResponse | null>(
    null,
  );
  const [relationTargetsBusy, setRelationTargetsBusy] = useState(false);
  const [relationTargetCandidate, setRelationTargetCandidate] = useState("");
  const [relationDirection, setRelationDirection] =
    useState<RelationDirection>("source-to-target");
  const [relationMode, setRelationMode] = useState<ControlledRelationMode>("manual");
  const [relationPredicate, setRelationPredicate] = useState("");
  const [relationSuggestion, setRelationSuggestion] = useState<LocalSuggestionResponse | null>(
    null,
  );
  const [relationSuggestionBusy, setRelationSuggestionBusy] = useState(false);
  const [relationRejectionReason, setRelationRejectionReason] = useState("");
  const [suggestionItemText, setSuggestionItemText] = useState("");
  const [suggestionEntityType, setSuggestionEntityType] = useState("");
  const [suggestionTargetHandle, setSuggestionTargetHandle] = useState("");
  const [manualRejection, setManualRejection] = useState<ManualCaptureRejectionResponse | null>(null);
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

  const localSuggestionCandidate =
    selected &&
    detail?.itemHandle === selected.handle &&
    detail.manualCapture &&
    detail.reviewReceipt.state === "accepted"
      ? selected.handle
      : null;
  const controlledRelationCandidate = localSuggestionCandidate;

  useEffect(() => {
    if (!localSuggestionCandidate) {
      setLocalSuggestion(null);
      setLocalSuggestionBusy(false);
      return;
    }
    let active = true;
    setLocalSuggestion(null);
    setLocalSuggestionBusy(true);
    api
      .getLocalSuggestion(projectHandle, localSuggestionCandidate)
      .then((value) => {
        if (active) setLocalSuggestion(value);
      })
      .catch((nextError: unknown) => {
        if (active) setError(nextError);
      })
      .finally(() => {
        if (active) setLocalSuggestionBusy(false);
      });
    return () => {
      active = false;
    };
  }, [api, localSuggestionCandidate, projectHandle]);

  useEffect(() => {
    if (!controlledRelationCandidate) {
      setRelationTargets(null);
      setRelationTargetsBusy(false);
      setRelationTargetCandidate("");
      setRelationSuggestion(null);
      return;
    }
    let active = true;
    setRelationTargets(null);
    setRelationTargetsBusy(true);
    setRelationSuggestion(null);
    api
      .getRelationSuggestionTargets(projectHandle, controlledRelationCandidate)
      .then((value) => {
        if (!active) return;
        setRelationTargets(value);
        setRelationTargetCandidate(value.targets[0]?.candidateHandle ?? "");
      })
      .catch((nextError: unknown) => {
        if (active) setError(nextError);
      })
      .finally(() => {
        if (active) setRelationTargetsBusy(false);
      });
    return () => {
      active = false;
    };
  }, [api, controlledRelationCandidate, projectHandle]);

  const selectedRelationTarget = relationTargets?.targets.find(
    (target) => target.candidateHandle === relationTargetCandidate,
  );
  const relationPredicateOptions =
    selectedRelationTarget?.allowedPredicates[relationDirection] ?? [];

  useEffect(() => {
    if (relationMode === "manual" && !relationPredicateOptions.includes(relationPredicate)) {
      setRelationPredicate(relationPredicateOptions[0] ?? "");
    }
  }, [relationDirection, relationMode, relationPredicate, relationPredicateOptions]);

  useEffect(() => {
    if (
      !controlledRelationCandidate ||
      !relationTargetCandidate ||
      !selectedRelationTarget
    ) {
      setRelationSuggestion(null);
      setRelationSuggestionBusy(false);
      return;
    }
    const predicate =
      relationMode === "manual"
        ? relationPredicateOptions.includes(relationPredicate)
          ? relationPredicate
          : relationPredicateOptions[0]
        : undefined;
    if (relationMode === "manual" && !predicate) {
      setRelationSuggestion(null);
      setRelationSuggestionBusy(false);
      return;
    }
    const query: ControlledRelationRequest = {
      targetCandidateHandle: relationTargetCandidate,
      direction: relationDirection,
      mode: relationMode,
      ...(predicate ? { predicate } : {}),
    };
    let active = true;
    setRelationSuggestion(null);
    setRelationSuggestionBusy(true);
    api
      .getControlledRelationSuggestionState(
        projectHandle,
        controlledRelationCandidate,
        query,
      )
      .then((value) => {
        if (active) setRelationSuggestion(value);
      })
      .catch((nextError: unknown) => {
        if (active) setError(nextError);
      })
      .finally(() => {
        if (active) setRelationSuggestionBusy(false);
      });
    return () => {
      active = false;
    };
  }, [
    api,
    controlledRelationCandidate,
    projectHandle,
    relationDirection,
    relationMode,
    relationPredicate,
    relationPredicateOptions,
    relationTargetCandidate,
    selectedRelationTarget,
  ]);

  useEffect(() => {
    const proposal = localSuggestion?.suggestion;
    if (!proposal) return;
    setSuggestionItemText(proposal.itemText ?? "");
    setSuggestionEntityType(proposal.entityType ?? selected?.proposedType ?? "");
    setSuggestionTargetHandle(
      proposal.targetHandle ?? localSuggestion?.linkOptions[0]?.handle ?? "",
    );
  }, [localSuggestion?.suggestion, localSuggestion?.linkOptions, selected?.proposedType]);

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
    setDetail(null);
    setAbstainNotice(null);
    setAbstainReceipt(null);
    setManualApproval(null);
    setManualRejection(null);
    setRelationTargets(null);
    setRelationTargetsBusy(false);
    setRelationTargetCandidate("");
    setRelationDirection("source-to-target");
    setRelationMode("manual");
    setRelationPredicate("");
    setRelationSuggestion(null);
    setRelationSuggestionBusy(false);
    setRelationRejectionReason("");
    setDetailBusy(true);
    void api
      .getReviewCandidateDetail(projectHandle, candidate.handle)
      .then(setDetail)
      .catch(setError)
      .finally(() => setDetailBusy(false));
  };

  const validate = async () => {
    if (
      !selected ||
      (detail?.manualCapture && detail.reviewReceipt.state !== "not-recorded")
    ) {
      return;
    }
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
    if (
      !selected ||
      !detail ||
      !reason.trim() ||
      reviewDecisionDisabled(detail, "reject", busy)
    ) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      if (detail.manualCapture) {
        const sourceVersionId = detail.sourceVersion.sourceVersionId;
        const anchor = detail.evidence.highlights[0];
        if (!sourceVersionId || !anchor?.quoteDigest) return;
        const receipt = await api.rejectManualCandidate(
          projectHandle,
          selected.handle,
          {
            candidateRevision: detail.candidateRevision,
            expectedCandidateRevision: 0,
            sourceVersionId,
            sourceVersionRevision: detail.sourceVersion.revision,
            anchorQuoteDigest: anchor.quoteDigest,
            reason: reason.trim(),
          },
          operationKey(),
        );
        setManualRejection(receipt);
        await loadQueue();
        setDetail(await api.getReviewCandidateDetail(projectHandle, selected.handle));
      } else {
        setDecision(
          await api.rejectSelectedCandidate(
            projectHandle,
            selected.handle,
            { reason: reason.trim() },
            operationKey(),
          ),
        );
      }
    } catch (nextError) {
      setError(nextError);
    } finally {
      setBusy(false);
    }
  };

  const abstain = async () => {
    if (!selected || !detail || reviewDecisionDisabled(detail, "abstain", busy)) return;
    const sourceVersionId = detail.sourceVersion.sourceVersionId;
    if (!sourceVersionId) return;
    setBusy(true);
    setError(null);
    try {
      const receipt = await api.abstainSelectedCandidate(
        projectHandle,
        selected.handle,
        {
          candidateRevision: detail.candidateRevision,
          expectedCandidateRevision:
            detail.reviewReceipt.state === "not-recorded"
              ? 0
              : detail.reviewReceipt.candidateRevision,
          sourceVersionId,
          sourceVersionRevision: detail.sourceVersion.revision,
          constrainedContractVersion: detail.constrainedContractVersion,
          evidenceDigest: detail.evidence.digest,
          previousDecisionDigest: detail.reviewReceipt.receiptDigest,
        },
        operationKey(),
      );
      setAbstainReceipt(receipt);
      setAbstainNotice(
        receipt.outcome === "replayed"
          ? "Abstention receipt replayed idempotently."
          : "Abstention receipt recorded. No assertion was created.",
      );
      await loadQueue();
      setDetail(await api.getReviewCandidateDetail(projectHandle, selected.handle));
    } catch (nextError) {
      setError(nextError);
      setAbstainNotice(null);
    } finally {
      setBusy(false);
    }
  };
  const approveManual = async () => {
    if (
      !selected ||
      !detail?.manualCapture ||
      reviewDecisionDisabled(detail, "confirm", busy)
    ) {
      return;
    }
    const sourceVersionId = detail.sourceVersion.sourceVersionId;
    const anchor = detail.evidence.highlights[0];
    if (!sourceVersionId || !anchor?.quoteDigest) return;
    setBusy(true);
    setError(null);
    try {
      const receipt = await api.approveManualCandidate(
        projectHandle,
        selected.handle,
        {
          candidateRevision: detail.candidateRevision,
          expectedCandidateRevision: 0,
          sourceVersionId,
          sourceVersionRevision: detail.sourceVersion.revision,
          anchorQuoteDigest: anchor.quoteDigest,
        },
        operationKey(),
      );
      setManualApproval(receipt);
      await loadQueue();
      setDetail(await api.getReviewCandidateDetail(projectHandle, selected.handle));
    } catch (nextError) {
      setError(nextError);
      setManualApproval(null);
    } finally {
      setBusy(false);
    }
  };

  const requestLocalSuggestion = async () => {
    if (
      !selected ||
      !localSuggestion ||
      !localSuggestion.modelAvailable ||
      localSuggestionBusy ||
      busy ||
      !["ready", "failed", "abstained"].includes(localSuggestion.state) ||
      localSuggestion.budget.userRemaining < 1 ||
      localSuggestion.budget.projectRemaining < 1
    ) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      setLocalSuggestion(
        await api.requestLocalSuggestion(
          projectHandle,
          selected.handle,
          localSuggestion.state !== "ready",
          operationKey(),
        ),
      );
    } catch (nextError) {
      setError(nextError);
    } finally {
      setBusy(false);
    }
  };

  const decideLocalSuggestion = async (
    decision: LocalSuggestionDecisionRequest["decision"],
  ) => {
    const current = localSuggestion;
    const proposal = current?.suggestion;
    if (
      !selected ||
      !current ||
      !proposal ||
      busy ||
      !["proposed", "edited"].includes(current.state)
    ) {
      return;
    }
    let editPayload: LocalSuggestionDecisionRequest["edit"];
    if (decision === "edit") {
      if (proposal.kind === "item" && suggestionItemText.trim() && suggestionEntityType) {
        editPayload = {
          itemText: suggestionItemText.trim(),
          entityType: suggestionEntityType,
        };
      } else if (proposal.kind === "type" && suggestionEntityType) {
        editPayload = { entityType: suggestionEntityType };
      } else if (proposal.kind === "link" && suggestionTargetHandle) {
        editPayload = { targetHandle: suggestionTargetHandle };
      } else {
        return;
      }
    }
    const payload: LocalSuggestionDecisionRequest = {
      expectedProposalRevision: proposal.revision,
      decision,
      ...(editPayload ? { edit: editPayload } : {}),
    };
    setBusy(true);
    setError(null);
    try {
      setLocalSuggestion(
        await api.decideLocalSuggestion(
          projectHandle,
          selected.handle,
          proposal.suggestionId,
          payload,
          operationKey(),
        ),
      );
    } catch (nextError) {
      setError(nextError);
    } finally {
      setBusy(false);
    }
  };

  const currentLocalProposal = localSuggestion?.suggestion;
  const localProposalPending =
    localSuggestion !== null && ["proposed", "edited"].includes(localSuggestion.state);
  const localEditValid =
    currentLocalProposal?.kind === "item"
      ? Boolean(suggestionItemText.trim() && suggestionEntityType)
      : currentLocalProposal?.kind === "type"
        ? Boolean(suggestionEntityType)
        : currentLocalProposal?.kind === "link"
          ? Boolean(suggestionTargetHandle)
          : false;


  const requestControlledRelation = async () => {
    if (
      !selected ||
      !controlledRelationCandidate ||
      !relationTargetCandidate ||
      !selectedRelationTarget ||
      busy ||
      relationSuggestionBusy ||
      (relationMode === "manual" &&
        (!relationPredicate || !relationPredicateOptions.includes(relationPredicate))) ||
      (relationMode === "local" && relationPredicateOptions.length === 0)
    ) {
      return;
    }
    const retry =
      relationMode === "local" &&
      relationSuggestion !== null &&
      ["failed", "abstained"].includes(relationSuggestion.state);
    if (
      relationMode === "local" &&
      (relationSuggestion?.modelAvailable !== true ||
        relationSuggestion.budget.userRemaining < 1 ||
        relationSuggestion.budget.projectRemaining < 1 ||
        !["ready", "failed", "abstained"].includes(relationSuggestion.state))
    ) {
      return;
    }
    const payload: ControlledRelationRequest = {
      targetCandidateHandle: relationTargetCandidate,
      direction: relationDirection,
      mode: relationMode,
      ...(relationMode === "manual" ? { predicate: relationPredicate } : {}),
      ...(retry ? { retry: true } : {}),
    };
    setBusy(true);
    setError(null);
    try {
      const requested = await api.requestControlledRelationSuggestion(
        projectHandle,
        selected.handle,
        payload,
        operationKey(),
      );
      const current = requested.suggestion
        ? await api.getControlledRelationSuggestion(
            projectHandle,
            selected.handle,
            requested.suggestion.suggestionId,
          )
        : requested;
      setRelationSuggestion(current);
    } catch (nextError) {
      setError(nextError);
    } finally {
      setBusy(false);
    }
  };

  const decideControlledRelation = async (
    decision: ControlledRelationDecisionRequest["decision"],
  ) => {
    const proposal = relationSuggestion?.suggestion;
    if (
      !selected ||
      !proposal ||
      proposal.kind !== "relation" ||
      relationSuggestion?.state !== "proposed" ||
      busy
    ) {
      return;
    }
    const payload: ControlledRelationDecisionRequest = {
      expectedProposalRevision: proposal.revision,
      decision,
      ...(decision === "reject" && relationRejectionReason.trim()
        ? { reason: relationRejectionReason.trim() }
        : {}),
    };
    setBusy(true);
    setError(null);
    try {
      setRelationSuggestion(
        await api.decideControlledRelationSuggestion(
          projectHandle,
          selected.handle,
          proposal.suggestionId,
          payload,
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
              aria-current={selected?.handle === candidate.handle ? "true" : undefined}
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
            <div aria-live="polite" className="review-status-strip">
              {detailBusy && "Loading source-first review detail…"}
              {detail && reviewStatusLabel(detail)}
            </div>
            {detail?.manualCapture && (
              <StateMessage kind="success">
                Human-authored zero-model capture. The server resolved the Note revision and
                Unicode anchor; no model was called.
              </StateMessage>
            )}
            {detail && (
              <section className="review-evidence-panel" aria-labelledby="review-evidence-heading">
                <div className="section-heading">
                  <div>
                    <p className="eyebrow">Evidence before action</p>
                    <h3 id="review-evidence-heading">Source and receipt state</h3>
                  </div>
                  <StatusBadge status={detail.evidence.status} />
                </div>
                <div className="detail-grid">
                  <span>
                    Source revision<strong>{detail.sourceVersion.revision}</strong>
                  </span>
                  <span>
                    Candidate revision<strong>{detail.candidateRevision}</strong>
                  </span>
                  <span>
                    Validation<strong>{detail.validationState}</strong>
                  </span>
                  <span>
                    Receipt<strong>{detail.reviewReceipt.state}</strong>
                  </span>
                </div>
                {detail.sourceText ? (
                  <blockquote className="source-quote">{detail.sourceText}</blockquote>
                ) : (
                  <StateMessage kind="empty">
                    Source text is unavailable; no unsupported quote is shown.
                  </StateMessage>
                )}
                {detail.evidence.highlights.length > 0 ? (
                  <ul className="review-highlight-list" aria-label="Evidence highlights">
                    {detail.evidence.highlights.map((highlight, index) => (
                      <li
                        key={`${highlight.kind}-${highlight.startOffset}-${highlight.endOffset}-${index}`}
                      >
                        <strong>{highlight.kind}</strong>
                        <span>
                          code points {highlight.startOffset}–{highlight.endOffset}
                        </span>
                        {highlight.utf16Start != null && highlight.utf16End != null && (
                          <span>
                            UTF-16 {highlight.utf16Start}–{highlight.utf16End}
                          </span>
                        )}
                        {highlight.quote && <q>{highlight.quote}</q>}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <StateMessage kind="empty">
                    No selected evidence highlight is available.
                  </StateMessage>
                )}
                {detail.uncertaintyReasons.length > 0 && (
                  <p className="review-uncertainty">
                    Uncertainty: {detail.uncertaintyReasons.join(", ")}
                  </p>
                )}
                {detail.stale && (
                  <StateMessage kind="empty">
                    This source revision is stale. Refresh before deciding.
                  </StateMessage>
                )}
                {detail.quarantined && (
                  <StateMessage kind="empty">
                    This item is quarantined and cannot be materialized.
                  </StateMessage>
                )}
              </section>
            )}
            {detail?.manualCapture &&
              detail.itemHandle === selected.handle &&
              detail.reviewReceipt.state === "accepted" && (
                <section
                  className="review-evidence-panel"
                  aria-labelledby="local-suggestion-heading"
                >
                  <div className="section-heading">
                    <div>
                      <p className="eyebrow">Optional local copilot</p>
                      <h3 id="local-suggestion-heading">One bounded suggestion</h3>
                    </div>
                    <StatusBadge status={localSuggestion?.state ?? "loading"} />
                  </div>
                  <p>
                    Suggestions run only after this human-confirmed occurrence and only when you
                    request them. Reads never call a model; decisions do not create graph
                    assertions.
                  </p>
                  {localSuggestionBusy && (
                    <StateMessage kind="loading">
                      Reading cached suggestion state and budgets. No model call is made.
                    </StateMessage>
                  )}
                  {!localSuggestionBusy && !localSuggestion && (
                    <StateMessage kind="empty">
                      Local suggestion state could not be loaded. No suggestion was requested.
                    </StateMessage>
                  )}
                  {localSuggestion && (
                    <>
                      <div className="detail-grid">
                        <span>
                          User requests remaining
                          <strong>
                            {localSuggestion.budget.userRemaining}/
                            {localSuggestion.budget.userDailyLimit}
                          </strong>
                        </span>
                        <span>
                          Project requests remaining
                          <strong>
                            {localSuggestion.budget.projectRemaining}/
                            {localSuggestion.budget.projectDailyLimit}
                          </strong>
                        </span>
                        <span>
                          Budget resets
                          <strong>
                            {new Date(localSuggestion.budget.resetsAt).toLocaleString()}
                          </strong>
                        </span>
                      </div>
                      {localSuggestion.availabilityReason === "local_model_not_configured" && (
                        <StateMessage kind="empty">
                          No local model is configured. An operator must configure Ollama; no
                          external provider is used.
                        </StateMessage>
                      )}
                      {localSuggestion.availabilityReason === "production_disabled" && (
                        <StateMessage kind="empty">
                          Local suggestions are disabled in production.
                        </StateMessage>
                      )}
                      {localSuggestion.failureCode && (
                        <StateMessage kind="empty">
                          The last request did not complete: {localSuggestion.failureCode}.
                        </StateMessage>
                      )}
                      {currentLocalProposal && (
                        <div className="review-proposal-diff" aria-label="Local suggestion">
                          <div>
                            <span>{currentLocalProposal.kind} suggestion</span>
                            <strong>
                              {currentLocalProposal.itemText ??
                                currentLocalProposal.entityType ??
                                currentLocalProposal.targetLabel ??
                                currentLocalProposal.abstentionCode ??
                                "No proposal"}
                            </strong>
                            <small>
                              Source revision {currentLocalProposal.sourceVersionRevision} ·{" "}
                              {currentLocalProposal.evidenceDigest}
                            </small>
                          </div>
                          <div>
                            <span>Materialization</span>
                            <strong>Blocked</strong>
                            <small>No assertion or inference write can occur here.</small>
                          </div>
                        </div>
                      )}
                      {localProposalPending && currentLocalProposal?.kind === "item" && (
                        <div className="form-grid">
                          <label className="stacked-label">
                            Suggested item text
                            <input
                              value={suggestionItemText}
                              onChange={(event) => setSuggestionItemText(event.target.value)}
                              maxLength={512}
                            />
                          </label>
                          <label className="stacked-label">
                            Entity type
                            <select
                              value={suggestionEntityType}
                              onChange={(event) => setSuggestionEntityType(event.target.value)}
                            >
                              <option value="">Select a type</option>
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
                        </div>
                      )}
                      {localProposalPending && currentLocalProposal?.kind === "type" && (
                        <label className="stacked-label">
                          Suggested type
                          <select
                            value={suggestionEntityType}
                            onChange={(event) => setSuggestionEntityType(event.target.value)}
                          >
                            <option value="">Select a type</option>
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
                      )}
                      {localProposalPending && currentLocalProposal?.kind === "link" && (
                        <label className="stacked-label">
                          Same-project entity link
                          <select
                            value={suggestionTargetHandle}
                            onChange={(event) => setSuggestionTargetHandle(event.target.value)}
                          >
                            <option value="">Select a project entity</option>
                            {localSuggestion.linkOptions.map((option) => (
                              <option key={option.handle} value={option.handle}>
                                {option.label}
                              </option>
                            ))}
                          </select>
                        </label>
                      )}
                      {localProposalPending && currentLocalProposal?.kind !== "abstain" && (
                        <div className="button-row">
                          <button
                            className="secondary"
                            disabled={busy || !localEditValid}
                            onClick={() => void decideLocalSuggestion("edit")}
                            type="button"
                          >
                            Save edit
                          </button>
                          <button
                            disabled={busy}
                            onClick={() => void decideLocalSuggestion("confirm")}
                            type="button"
                          >
                            Confirm suggestion
                          </button>
                          <button
                            className="danger"
                            disabled={busy}
                            onClick={() => void decideLocalSuggestion("reject")}
                            type="button"
                          >
                            Reject suggestion
                          </button>
                        </div>
                      )}
                      {["ready", "failed", "abstained"].includes(localSuggestion.state) && (
                        <button
                          className="secondary"
                          disabled={
                            busy ||
                            localSuggestionBusy ||
                            !localSuggestion.modelAvailable ||
                            localSuggestion.budget.userRemaining < 1 ||
                            localSuggestion.budget.projectRemaining < 1
                          }
                          onClick={() => void requestLocalSuggestion()}
                          type="button"
                        >
                          {localSuggestion.state === "ready"
                            ? "Request local suggestion"
                            : "Request explicit retry"}
                        </button>
                      )}
                      {localSuggestion.state === "confirmed" && (
                        <StateMessage kind="success">
                          Suggestion confirmation recorded
                          {localSuggestion.receipt &&
                            ` with receipt ${localSuggestion.receipt.receiptDigest}`}
                          . The proposal remains blocked from materialization.
                        </StateMessage>
                      )}
                      {localSuggestion.state === "rejected" && (
                        <StateMessage kind="empty">
                          Suggestion rejection recorded. No assertion was created.
                        </StateMessage>
                      )}
                    </>
                  )}
                </section>
              )}
            {controlledRelationCandidate && (
              <section
                className="review-evidence-panel"
                aria-labelledby="controlled-relation-heading"
              >
                <div className="section-heading">
                  <div>
                    <p className="eyebrow">Human-controlled relation</p>
                    <h3 id="controlled-relation-heading">Relate confirmed occurrences</h3>
                  </div>
                  <StatusBadge status={relationSuggestion?.state ?? "loading"} />
                </div>
                <p>
                  Choose a second validated, human-confirmed occurrence from this Note. Manual
                  predicate selection uses deterministic source evidence without a model; local
                  assistance may suggest only a predicate, never endpoints, direction, or evidence.
                </p>
                {relationTargetsBusy && (
                  <StateMessage kind="loading">
                    Checking current endpoint confirmations and source evidence.
                  </StateMessage>
                )}
                {!relationTargetsBusy && relationTargets?.targets.length === 0 && (
                  <StateMessage kind="empty">
                    No other current, confirmed occurrence has a supported relation evidence block.
                  </StateMessage>
                )}
                {relationTargets && relationTargets.targets.length > 0 && (
                  <div className="form-grid">
                    <label className="stacked-label">
                      Other confirmed occurrence
                      <select
                        value={relationTargetCandidate}
                        onChange={(event) => {
                          setRelationTargetCandidate(event.target.value);
                          setRelationSuggestion(null);
                        }}
                      >
                        {relationTargets.targets.map((target) => (
                          <option key={target.candidateHandle} value={target.candidateHandle}>
                            {target.label} ({target.entityType})
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="stacked-label">
                      Direction
                      <select
                        value={relationDirection}
                        onChange={(event) => {
                          setRelationDirection(event.target.value as RelationDirection);
                          setRelationSuggestion(null);
                        }}
                      >
                        <option value="source-to-target">
                          Selected occurrence → other occurrence
                        </option>
                        <option value="target-to-source">
                          Other occurrence → selected occurrence
                        </option>
                      </select>
                    </label>
                    <label className="stacked-label">
                      Predicate selection
                      <select
                        value={relationMode}
                        onChange={(event) => {
                          setRelationMode(event.target.value as ControlledRelationMode);
                          setRelationSuggestion(null);
                        }}
                      >
                        <option value="manual">Manual, no model</option>
                        <option value="local">Ask local model for a predicate</option>
                      </select>
                    </label>
                    {relationMode === "manual" && (
                      <label className="stacked-label">
                        Allowlisted predicate with current evidence
                        <select
                          value={relationPredicate}
                          onChange={(event) => {
                            setRelationPredicate(event.target.value);
                            setRelationSuggestion(null);
                          }}
                        >
                          <option value="">Select a supported predicate</option>
                          {relationPredicateOptions.map((predicate) => (
                            <option key={predicate} value={predicate}>
                              {predicate}
                            </option>
                          ))}
                        </select>
                      </label>
                    )}
                  </div>
                )}
                {selectedRelationTarget && (
                  <p className="muted">
                    Allowed in this direction: {relationPredicateOptions.join(", ") || "none"}.
                  </p>
                )}
                {relationSuggestionBusy && (
                  <StateMessage kind="loading">
                    Reading pair-specific suggestion state. This does not call a model.
                  </StateMessage>
                )}
                {relationMode === "local" &&
                  relationSuggestion?.availabilityReason === "local_model_not_configured" && (
                    <StateMessage kind="empty">
                      No local model is configured. Manual relation selection remains available.
                    </StateMessage>
                  )}
                {relationSuggestion?.failureCode && (
                  <StateMessage kind="empty">
                    The local relation request did not complete: {relationSuggestion.failureCode}.
                  </StateMessage>
                )}
                {relationSuggestion && (
                  <div className="detail-grid">
                    <span>
                      User requests remaining
                      <strong>
                        {relationSuggestion.budget.userRemaining}/
                        {relationSuggestion.budget.userDailyLimit}
                      </strong>
                    </span>
                    <span>
                      Project requests remaining
                      <strong>
                        {relationSuggestion.budget.projectRemaining}/
                        {relationSuggestion.budget.projectDailyLimit}
                      </strong>
                    </span>
                    <span>
                      Materialization
                      <strong>Blocked</strong>
                    </span>
                  </div>
                )}
                {relationSuggestion?.suggestion?.kind === "relation" && (
                  <div className="review-proposal-diff" aria-label="Controlled relation proposal">
                    <div>
                      <span>Proposed relation</span>
                      <strong>{relationSuggestion.suggestion.predicate}</strong>
                      <small>
                        {selected?.label}{" "}
                        {relationSuggestion.suggestion.direction === "source-to-target"
                          ? "→"
                          : "←"}{" "}
                        {selectedRelationTarget?.label}
                      </small>
                    </div>
                    <div>
                      <span>Server-selected evidence</span>
                      <strong>
                        {relationSuggestion.suggestion.relationEvidence?.block?.kind ??
                          relationSuggestion.suggestion.relationEvidence?.reason ??
                          "Unavailable"}
                      </strong>
                      <small>
                        {relationSuggestion.suggestion.relationEvidence?.block
                          ? `Code points ${relationSuggestion.suggestion.relationEvidence.block.startOffset}–${relationSuggestion.suggestion.relationEvidence.block.endOffset}`
                          : "No evidence block was selected"}
                      </small>
                    </div>
                  </div>
                )}
                {relationSuggestion?.suggestion?.kind === "abstain" && (
                  <StateMessage kind="empty">
                    The local model abstained:{" "}
                    {relationSuggestion.suggestion.abstentionCode ?? "no supported predicate"}.
                  </StateMessage>
                )}
                {relationSuggestion?.state === "proposed" &&
                  relationSuggestion.suggestion?.kind === "relation" && (
                    <>
                      <label className="stacked-label">
                        Rejection reason (optional)
                        <input
                          value={relationRejectionReason}
                          onChange={(event) => setRelationRejectionReason(event.target.value)}
                          maxLength={256}
                        />
                      </label>
                      <div className="button-row">
                        <button
                          disabled={busy || relationSuggestionBusy}
                          onClick={() => void decideControlledRelation("confirm")}
                          type="button"
                        >
                          Confirm relation proposal
                        </button>
                        <button
                          className="danger"
                          disabled={busy || relationSuggestionBusy}
                          onClick={() => void decideControlledRelation("reject")}
                          type="button"
                        >
                          Reject relation proposal
                        </button>
                      </div>
                    </>
                  )}
                {relationSuggestion?.state === "confirmed" && (
                  <StateMessage kind="success">
                    Relation confirmation recorded with a review receipt. No graph write occurred.
                  </StateMessage>
                )}
                {relationSuggestion?.state === "rejected" && (
                  <StateMessage kind="empty">
                    Relation rejection recorded with a review receipt. No graph write occurred.
                  </StateMessage>
                )}
                {selectedRelationTarget &&
                  (relationMode === "manual"
                    ? !relationSuggestionBusy &&
                      (!relationSuggestion ||
                        ["ready", "unavailable"].includes(relationSuggestion.state))
                    : !relationSuggestionBusy &&
                      relationSuggestion?.modelAvailable === true &&
                      ["ready", "failed", "abstained"].includes(relationSuggestion.state) &&
                      relationSuggestion.budget.userRemaining > 0 &&
                      relationSuggestion.budget.projectRemaining > 0) && (
                    <button
                      className="secondary"
                      disabled={
                        busy ||
                        relationTargetsBusy ||
                        (relationMode === "manual"
                          ? !relationPredicate ||
                            !relationPredicateOptions.includes(relationPredicate)
                          : relationPredicateOptions.length === 0)
                      }
                      onClick={() => void requestControlledRelation()}
                      type="button"
                    >
                      {relationMode === "manual"
                        ? "Create manual relation proposal"
                        : relationSuggestion?.state === "failed" ||
                            relationSuggestion?.state === "abstained"
                          ? "Retry local predicate suggestion"
                          : "Request local predicate suggestion"}
                    </button>
                  )}
                <p className="muted">
                  Confirm and reject decisions append relation receipts only. They do not mutate
                  Semantic Core or materialize a graph relation.
                </p>
              </section>
            )}
            <div className="review-proposal-diff" aria-label="Proposed and edited values">
              <div>
                <span>Proposed</span>
                <strong>{detail?.proposed.label ?? selected.label}</strong>
                <small>{detail?.proposed.semanticType ?? selected.proposedType}</small>
              </div>
              <div>
                <span>Edited</span>
                <strong>{(detail?.edited?.label ?? label) || "No edit"}</strong>
                <small>{(detail?.edited?.semanticType ?? editType) || "No type change"}</small>
              </div>
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
            <button
              disabled={
                busy ||
                (detail?.manualCapture != null &&
                  detail.reviewReceipt.state !== "not-recorded")
              }
              onClick={() => void validate()}
              type="button"
            >
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
            {detail?.manualCapture ? (
              <>
                {validation?.conforms &&
                  !manualApproval &&
                  !manualRejection &&
                  !abstainReceipt && (
                    <button
                      disabled={reviewDecisionDisabled(detail, "confirm", busy)}
                      onClick={() => void approveManual()}
                      type="button"
                    >
                      {busy ? "Recording…" : "Record manual approval"}
                    </button>
                  )}
                {!manualApproval && !manualRejection && !abstainReceipt && (
                  <>
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
                      disabled={
                        reviewDecisionDisabled(detail, "reject", busy) || !reason.trim()
                      }
                      onClick={() => void reject()}
                      type="button"
                    >
                      Record rejection receipt
                    </button>
                    <button
                      className="secondary"
                      disabled={reviewDecisionDisabled(detail, "abstain", busy)}
                      onClick={() => void abstain()}
                      type="button"
                    >
                      Record abstention receipt
                    </button>
                  </>
                )}
              </>
            ) : (
              validation?.conforms &&
              !decision && (
                <>
                  <button
                    disabled={
                      reviewDecisionDisabled(detail, "confirm", busy) ||
                      editType !== "Requirement" ||
                      !canConfirmRequirement(validation, label)
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
                    disabled={
                      reviewDecisionDisabled(detail, "reject", busy) || !reason.trim()
                    }
                    onClick={() => void reject()}
                    type="button"
                  >
                    Reject candidate
                  </button>
                  <button
                    className="secondary"
                    disabled={reviewDecisionDisabled(detail, "abstain", busy)}
                    onClick={() => void abstain()}
                    type="button"
                  >
                    Abstain
                  </button>
                </>
              )
            )}
            {abstainNotice && (
              <StateMessage kind="success">
                {abstainNotice}
                {abstainReceipt && ` Receipt digest: ${abstainReceipt.receipt.receiptDigest}`}
              </StateMessage>
            )}
            {manualApproval && (
              <StateMessage kind="empty">
                Approval receipt {manualApproval.receipt.receiptDigest} was
                {manualApproval.outcome === "replayed" ? " replayed" : " recorded"}.
                Assertion materialization is blocked by the RM-63 owner-authorization lock; no
                asserted or inferred write occurred.
              </StateMessage>
            )}
            {manualRejection && (
              <StateMessage kind="success">
                Rejection receipt {manualRejection.receipt.receiptDigest} was
                {manualRejection.outcome === "replayed" ? " replayed" : " recorded"}.
                No asserted or inferred write occurred.
              </StateMessage>
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
