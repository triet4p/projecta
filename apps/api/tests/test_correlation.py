from projecta_api.correlation import is_safe_correlation_id, resolve_correlation


def test_correlation_reuses_safe_hints() -> None:
    resolved = resolve_correlation("req-1", "op-1")

    assert resolved.request_id == "req-1"
    assert resolved.operation_id == "op-1"
    assert resolved.headers() == {"X-Request-Id": "req-1", "X-Operation-Id": "op-1"}


def test_correlation_replaces_missing_or_unsafe_hints() -> None:
    resolved = resolve_correlation("bad value", "")

    assert resolved.request_id.startswith("req-")
    assert resolved.operation_id.startswith("op-")
    assert is_safe_correlation_id(resolved.request_id)
    assert is_safe_correlation_id(resolved.operation_id)
