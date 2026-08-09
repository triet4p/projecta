import pytest

from projecta_api.main import _gateway_problem


@pytest.mark.parametrize(
    ("error_class", "status", "code"),
    [
        ("timeout", 504, "PROVIDER_TIMEOUT"),
        ("rate_limit", 429, "PROVIDER_RATE_LIMITED"),
        ("provider_failure", 503, "PROVIDER_UNAVAILABLE"),
        ("schema_invalid", 502, "PROVIDER_RESPONSE_INVALID"),
        ("empty_malformed", 502, "PROVIDER_RESPONSE_INVALID"),
        ("refusal", 502, "PROVIDER_REFUSED"),
        ("unsafe_output", 502, "PROVIDER_RESPONSE_INVALID"),
        ("invalid_evidence", 422, "CANDIDATE_INVALID"),
        ("hallucinated_link", 422, "CANDIDATE_INVALID"),
        ("configuration_invalid", 503, "CONFIGURATION_INVALID"),
    ],
)
def test_gateway_error_mapping_is_finite_and_sanitized(
    error_class: str, status: int, code: str
) -> None:
    mapped_status, mapped_code, title, detail = _gateway_problem(error_class)

    assert (mapped_status, mapped_code) == (status, code)
    assert title and detail
    assert error_class not in detail
