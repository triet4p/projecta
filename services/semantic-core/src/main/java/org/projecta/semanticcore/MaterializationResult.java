package org.projecta.semanticcore;

import java.util.List;

/** Safe result of an accepted or exact replayed assertion materialization. */
public record MaterializationResult(
        String outcome,
        String contractVersion,
        String bodyDigest,
        String materializationRevision,
        List<String> assertedIris) {
    public MaterializationResult {
        assertedIris = List.copyOf(assertedIris);
    }
}
