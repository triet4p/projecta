from __future__ import annotations

import base64
import importlib.util
import sys
from pathlib import Path

import pytest

_builder_path = Path(__file__).resolve().parents[1] / "build_native_package.py"
_builder_spec = importlib.util.spec_from_file_location("build_native_package", _builder_path)
if _builder_spec is None or _builder_spec.loader is None:
    raise RuntimeError("could not load the native package builder")
builder = importlib.util.module_from_spec(_builder_spec)
sys.modules[_builder_spec.name] = builder
_builder_spec.loader.exec_module(builder)


def test_release_signing_rejects_private_key_inside_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(
        "PROJECTA_UPDATE_SIGNING_KEY_PATH",
        str(builder.ROOT / "build" / "test-only-ed25519-private-key.pem"),
    )
    monkeypatch.setenv("PROJECTA_UPDATE_PUBLIC_KEY_B64", base64.b64encode(bytes(32)).decode("ascii"))
    monkeypatch.setenv("PROJECTA_AUTHENTICODE_THUMBPRINT", "0" * 40)
    monkeypatch.setenv("PROJECTA_AUTHENTICODE_TIMESTAMP_URL", "https://timestamp.example.invalid/rfc3161")

    with pytest.raises(SystemExit) as failure:
        builder._load_release_signing_configuration(tmp_path / "package", tmp_path / "release.zip")

    assert str(failure.value) == (
        "the owner Ed25519 private key must remain outside the repository, package, and archive."
    )
