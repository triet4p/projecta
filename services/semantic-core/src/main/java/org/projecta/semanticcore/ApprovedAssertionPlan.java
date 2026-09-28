package org.projecta.semanticcore;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.List;
import java.util.regex.Pattern;

/** Immutable, review-bound input to the approved-only assertion boundary. */
public record ApprovedAssertionPlan(
        String project,
        String sourceVersionId,
        int sourceVersionRevision,
        List<ApprovedCandidate> candidates,
        String ontologyVersion,
        String constrainedRelationContractVersion,
        String evidenceSelectionVersion,
        String expectedAssertedGraphRevision,
        String provenanceActivityIri,
        String idempotencyKey) {
    public static final String CONTRACT_VERSION = "approved-assertion-plan.v1";
    private static final Pattern SOURCE_ID = Pattern.compile("sv_[0-9a-f]{64}");
    private static final Pattern DIGEST = Pattern.compile("sha256:[0-9a-f]{64}");
    private static final Pattern VERSION = Pattern.compile("[A-Za-z0-9][A-Za-z0-9._-]{0,63}");

    public ApprovedAssertionPlan {
        new ProjectId(project);
        if (!SOURCE_ID.matcher(require(sourceVersionId, "source version ID")).matches() || sourceVersionRevision < 1) {
            throw new IllegalArgumentException("source version identity/revision is invalid");
        }
        requireVersion(ontologyVersion, "ontology version");
        requireVersion(constrainedRelationContractVersion, "constrained relation contract version");
        requireVersion(evidenceSelectionVersion, "evidence selection version");
        requireDigest(expectedAssertedGraphRevision, "expected asserted graph revision");
        requireIri(provenanceActivityIri, "provenance activity IRI");
        requireKey(idempotencyKey);
        if (candidates == null || candidates.isEmpty()) {
            throw new IllegalArgumentException("at least one approved candidate is required");
        }
        var sorted = new ArrayList<>(candidates);
        sorted.sort((left, right) -> left.candidateIri().compareTo(right.candidateIri()));
        candidates = List.copyOf(sorted);
        for (ApprovedCandidate candidate : candidates) {
            if (!candidate.project().equals(project)
                    || !candidate.sourceVersionId().equals(sourceVersionId)
                    || candidate.sourceVersionRevision() != sourceVersionRevision
                    || !candidate.ontologyVersion().equals(ontologyVersion)
                    || !candidate.constrainedRelationContractVersion().equals(constrainedRelationContractVersion)
                    || !candidate.evidenceSelectionVersion().equals(evidenceSelectionVersion)) {
                throw new IllegalArgumentException("candidate is not bound to the plan scope and versions");
            }
        }
    }

    public String bodyDigest() {
        var body = new StringBuilder(CONTRACT_VERSION)
                .append('|')
                .append(project)
                .append('|')
                .append(sourceVersionId)
                .append('|')
                .append(sourceVersionRevision)
                .append('|')
                .append(ontologyVersion)
                .append('|')
                .append(constrainedRelationContractVersion)
                .append('|')
                .append(evidenceSelectionVersion)
                .append('|')
                .append(expectedAssertedGraphRevision)
                .append('|')
                .append(provenanceActivityIri)
                .append('|')
                .append(idempotencyKey);
        for (ApprovedCandidate candidate : candidates) {
            body.append('|').append(candidate.canonical());
        }
        return digest(body.toString());
    }

    public record ApprovedCandidate(
            String project,
            String candidateIri,
            int candidateRevision,
            String sourceVersionId,
            int sourceVersionRevision,
            String reviewReceiptDigest,
            String evidenceDigest,
            String ontologyVersion,
            String constrainedRelationContractVersion,
            String evidenceSelectionVersion,
            String assertedIri,
            String reviewerIri,
            String label,
            LocalDate validFrom) {
        public ApprovedCandidate {
            new ProjectId(require(project, "candidate project"));
            requireIri(candidateIri, "candidate IRI");
            if (candidateRevision < 1 || sourceVersionRevision < 1) {
                throw new IllegalArgumentException("candidate/source revisions must be positive");
            }
            if (!SOURCE_ID
                    .matcher(require(sourceVersionId, "candidate source version ID"))
                    .matches()) {
                throw new IllegalArgumentException("candidate source version ID is invalid");
            }
            requireDigest(reviewReceiptDigest, "review receipt digest");
            requireDigest(evidenceDigest, "evidence digest");
            requireVersion(ontologyVersion, "candidate ontology version");
            requireVersion(constrainedRelationContractVersion, "candidate relation contract version");
            requireVersion(evidenceSelectionVersion, "candidate evidence selection version");
            requireIri(assertedIri, "asserted IRI");
            requireIri(reviewerIri, "reviewer IRI");
            if (label == null || label.isBlank() || label.indexOf('|') >= 0 || validFrom == null) {
                throw new IllegalArgumentException("assertion label and valid-from date are required");
            }
        }

        private String canonical() {
            return String.join(
                    "|",
                    project,
                    candidateIri,
                    Integer.toString(candidateRevision),
                    sourceVersionId,
                    Integer.toString(sourceVersionRevision),
                    reviewReceiptDigest,
                    evidenceDigest,
                    ontologyVersion,
                    constrainedRelationContractVersion,
                    evidenceSelectionVersion,
                    assertedIri,
                    reviewerIri,
                    label,
                    validFrom.toString());
        }
    }

    public static String metadataComment(ApprovedCandidate candidate) {
        return "projecta-approved-candidate/v1|candidateRevision=" + candidate.candidateRevision()
                + "|sourceVersionId=" + candidate.sourceVersionId()
                + "|sourceVersionRevision=" + candidate.sourceVersionRevision()
                + "|reviewReceiptDigest=" + candidate.reviewReceiptDigest()
                + "|evidenceDigest=" + candidate.evidenceDigest()
                + "|constrainedRelationContractVersion=" + candidate.constrainedRelationContractVersion()
                + "|evidenceSelectionVersion=" + candidate.evidenceSelectionVersion();
    }

    static String require(String value, String name) {
        if (value == null || value.isBlank() || value.indexOf('|') >= 0) {
            throw new IllegalArgumentException(name + " is required");
        }
        return value;
    }

    static void requireDigest(String value, String name) {
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

    private static void requireKey(String value) {
        if (value == null || value.isBlank() || value.length() > 128 || value.indexOf('|') >= 0) {
            throw new IllegalArgumentException("idempotency key is invalid");
        }
    }

    static String digest(String value) {
        try {
            return "sha256:"
                    + HexFormat.of()
                            .formatHex(MessageDigest.getInstance("SHA-256")
                                    .digest(value.getBytes(StandardCharsets.UTF_8)));
        } catch (NoSuchAlgorithmException exception) {
            throw new IllegalStateException("SHA-256 is unavailable", exception);
        }
    }
}
