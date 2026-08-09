"""Public knowledge projections never expose RDF resource syntax."""

from projecta_api.projections import (
    project_candidate_history,
    project_current_knowledge,
    project_evidence,
)


def test_current_knowledge_projects_iri_to_local_opaque_id() -> None:
    result = project_current_knowledge(
        {
            "requestId": "request-1",
            "items": [
                {
                    "item": "https://w3id.org/projecta/data/project/p/requirement/address-confirmation",
                    "label": "Address confirmation",
                    "validFrom": "2026-08-06",
                }
            ],
        }
    )

    assert result == {
        "requestId": "request-1",
        "items": [
            {
                "id": "address-confirmation",
                "label": "Address confirmation",
                "type": "Requirement",
                "validFrom": "2026-08-06",
            }
        ],
    }
    assert "https://" not in str(result)


def test_history_and_evidence_allowlist_only_opaque_ids_and_spans() -> None:
    history = project_candidate_history(
        {
            "requestId": "request-2",
            "items": [
                {
                    "activity": "https://w3id.org/projecta/data/project/p/activity/review-1",
                    "decision": "https://w3id.org/projecta/ontology/confirmed",
                    "reviewer": "https://w3id.org/projecta/data/project/p/person/le",
                    "endedAt": "2026-08-06T08:00:00Z",
                    "ignored": "https://internal.invalid/not-public",
                }
            ],
        },
        "https://w3id.org/projecta/data/project/p/candidate/address-confirmation",
    )
    evidence = project_evidence(
        {
            "requestId": "request-3",
            "items": [
                {
                    "candidate": "https://w3id.org/projecta/data/project/p/candidate/address-confirmation",
                    "source": "https://w3id.org/projecta/data/project/p/note-item/ni-1",
                    "note": "https://w3id.org/projecta/data/project/p/note/n-1",
                    "author": "https://w3id.org/projecta/data/project/p/person/alice",
                    "reviewer": "https://w3id.org/projecta/data/project/p/person/le",
                    "sourceText": "Confirm the address.",
                    "startOffset": "0",
                    "endOffset": "7",
                    "rawText": "must not be returned",
                }
            ],
        },
        "https://w3id.org/projecta/data/project/p/requirement/address-confirmation",
    )

    assert history["candidateId"] == "address-confirmation"
    assert history["items"] == [
        {
            "id": "review-1",
            "decision": "confirmed",
            "reviewerId": "le",
            "endedAt": "2026-08-06T08:00:00Z",
        }
    ]
    assert evidence["itemId"] == "address-confirmation"
    assert evidence["items"] == [
        {
            "candidateId": "address-confirmation",
            "sourceId": "ni-1",
            "noteId": "n-1",
            "authorId": "alice",
            "reviewerId": "le",
            "evidenceText": "Confirm the address.",
            "sourceText": "Confirm the address.",
            "startOffset": 0,
            "endOffset": 7,
        }
    ]
    serialized = str(history) + str(evidence)
    assert "https://" not in serialized
    assert "rawText" not in serialized
