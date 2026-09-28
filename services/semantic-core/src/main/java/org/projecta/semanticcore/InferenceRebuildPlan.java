package org.projecta.semanticcore;

import java.util.regex.Pattern;

/** Immutable source- and rule-bound input to an inference rebuild. */
public record InferenceRebuildPlan(
        String project,
        String assertedGraphRevision,
        String sourceVersionId,
        int sourceVersionRevision,
        String sourceVersionDigest,
        String ontologyVersion,
        String ruleVersion,
        String expectedCurrentInferenceRevision,
        String rebuildActivityIri,
        String idempotencyKey) {
    public static final String CONTRACT_VERSION = "inference-rebuild-plan.v1";
    private static final Pattern SOURCE_ID = Pattern.compile("sv_[0-9a-f]{64}");
    private static final Pattern DIGEST = Pattern.compile("sha256:[0-9a-f]{64}");
    private static final Pattern VERSION = Pattern.compile("[A-Za-z0-9][A-Za-z0-9._-]{0,63}");

    public InferenceRebuildPlan {
        new ProjectId(require(project, "project"));
        requireDigest(assertedGraphRevision, "asserted graph revision");
        if (!SOURCE_ID.matcher(require(sourceVersionId, "source version ID")).matches() || sourceVersionRevision < 1) {
            throw new IllegalArgumentException("source version identity/revision is invalid");
        }
        requireDigest(sourceVersionDigest, "source version digest");
        requireVersion(ontologyVersion, "ontology version");
        requireVersion(ruleVersion, "rule version");
        if (!"none".equals(expectedCurrentInferenceRevision)) {
            requireDigest(expectedCurrentInferenceRevision, "expected inference revision");
        }
        requireIri(rebuildActivityIri, "rebuild activity IRI");
        if (idempotencyKey == null
                || idempotencyKey.isBlank()
                || idempotencyKey.length() > 128
                || idempotencyKey.indexOf('|') >= 0) {
            throw new IllegalArgumentException("idempotency key is invalid");
        }
    }

    public String bodyDigest() {
        return ApprovedAssertionPlan.digest(String.join(
                "|",
                CONTRACT_VERSION,
                project,
                assertedGraphRevision,
                sourceVersionId,
                Integer.toString(sourceVersionRevision),
                sourceVersionDigest,
                ontologyVersion,
                ruleVersion,
                expectedCurrentInferenceRevision,
                rebuildActivityIri,
                idempotencyKey));
    }

    private static String require(String value, String name) {
        if (value == null || value.isBlank() || value.indexOf('|') >= 0) {
            throw new IllegalArgumentException(name + " is required");
        }
        return value;
    }

    private static void requireDigest(String value, String name) {
        if (!DIGEST.matcher(require(value, name)).matches()) {
            throw new IllegalArgumentException(name + " must be a sha256 digest");
        }
    }

    private static void requireVersion(String value, String name) {
        if (!VERSION.matcher(require(value, name)).matches()) {
            throw new IllegalArgumentException(name + " is invalid");
        }
    }

    private static void requireIri(String value, String name) {
        require(value, name);
        try {
            if (!java.net.URI.create(value).isAbsolute()) {
                throw new IllegalArgumentException(name + " must be absolute");
            }
        } catch (IllegalArgumentException exception) {
            throw new IllegalArgumentException(name + " is invalid", exception);
        }
    }
}
