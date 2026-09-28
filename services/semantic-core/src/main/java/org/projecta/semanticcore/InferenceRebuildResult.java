package org.projecta.semanticcore;

/** Safe result for invalidation or an accepted/replayed inference rebuild. */
public record InferenceRebuildResult(
        String outcome,
        String contractVersion,
        String project,
        String materializationRevision,
        String assertedGraphRevision,
        String sourceVersionId,
        String ruleVersion,
        String failureReason) {}
