from projecta_api.config import Settings
from projecta_api.extraction.service import _response_schema


def test_deepseek_responses_requires_explicit_configuration_and_strict_schema() -> None:
    settings = Settings()
    assert str(settings.llm_base_url) == "https://api.deepseek.com/"
    schema = _response_schema()
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {"entities", "relations", "links", "abstentionReason"}
    assert schema["properties"]["entities"]["items"]["required"] == ["type", "label", "evidence", "confidence"]
