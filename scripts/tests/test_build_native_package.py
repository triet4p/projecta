from __future__ import annotations

import base64
import hashlib
import importlib.util
import sys
from pathlib import Path

import pytest

_builder_path = Path(__file__).resolve().parents[1] / "build_native_package.py"
sys.path.insert(0, str(_builder_path.parent))  # sibling projecta_local import
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


def test_release_signing_allows_unconfigured_authenticode_with_valid_ed25519(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without Authenticode settings the release identity is Ed25519-only and NotSigned."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    key_dir = tmp_path / "owner-keys"
    key_dir.mkdir()
    private_key = Ed25519PrivateKey.generate()
    key_path = key_dir / "update-signing.key"
    key_path.write_bytes(
        private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    public_b64 = base64.b64encode(
        private_key.public_key().public_bytes(
            serialization.Encoding.Raw,
            serialization.PublicFormat.Raw,
        )
    ).decode("ascii")
    monkeypatch.setenv("PROJECTA_UPDATE_SIGNING_KEY_PATH", str(key_path))
    monkeypatch.setenv("PROJECTA_UPDATE_PUBLIC_KEY_B64", public_b64)
    monkeypatch.delenv("PROJECTA_AUTHENTICODE_THUMBPRINT", raising=False)
    monkeypatch.delenv("PROJECTA_AUTHENTICODE_TIMESTAMP_URL", raising=False)
    monkeypatch.delenv("PROJECTA_SIGNTOOL_PATH", raising=False)
    monkeypatch.setattr(builder.shutil, "which", lambda name: None)

    signing = builder._load_release_signing_configuration(tmp_path / "package", tmp_path / "release.zip")

    assert signing["authenticode"] is None
    assert signing["publicKeyFingerprint"] == hashlib.sha256(base64.b64decode(public_b64)).hexdigest()


def _ephemeral_ed25519_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point the release identity at a disposable key so refusal tests reach their branch."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    private_key = Ed25519PrivateKey.generate()
    key_path = tmp_path / "ephemeral-signing.key"
    key_path.write_bytes(
        private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    public_b64 = base64.b64encode(
        private_key.public_key().public_bytes(
            serialization.Encoding.Raw,
            serialization.PublicFormat.Raw,
        )
    ).decode("ascii")
    monkeypatch.setenv("PROJECTA_UPDATE_SIGNING_KEY_PATH", str(key_path))
    monkeypatch.setenv("PROJECTA_UPDATE_PUBLIC_KEY_B64", public_b64)


def test_release_signing_refuses_partial_authenticode_configuration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One Authenticode setting without the other refuses instead of downgrading."""
    _ephemeral_ed25519_env(tmp_path, monkeypatch)
    monkeypatch.setenv("PROJECTA_AUTHENTICODE_THUMBPRINT", "0" * 40)
    monkeypatch.delenv("PROJECTA_AUTHENTICODE_TIMESTAMP_URL", raising=False)

    with pytest.raises(SystemExit) as failure:
        builder._load_release_signing_configuration(tmp_path / "package", tmp_path / "release.zip")

    assert "partially configured" in str(failure.value)


def test_release_signing_rejects_invalid_configured_authenticode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A malformed configured thumbprint fails closed."""
    _ephemeral_ed25519_env(tmp_path, monkeypatch)
    monkeypatch.setenv("PROJECTA_AUTHENTICODE_THUMBPRINT", "not-a-thumbprint")
    monkeypatch.setenv("PROJECTA_AUTHENTICODE_TIMESTAMP_URL", "https://timestamp.example.invalid/rfc3161")

    with pytest.raises(SystemExit) as failure:
        builder._load_release_signing_configuration(tmp_path / "package", tmp_path / "release.zip")

    assert "thumbprint" in str(failure.value).casefold()


def test_release_manifest_accepts_missing_authenticode_with_ed25519_anchor(
    tmp_path: Path,
) -> None:
    """A release manifest stays eligible with Ed25519 pinned and Authenticode absent."""
    import json

    package = tmp_path / "package"
    (package / "projecta" / "semantic-core").mkdir(parents=True)
    (package / "runtime" / "python").mkdir(parents=True)
    (package / "runtime" / "java" / "legal").mkdir(parents=True)
    (package / "runtime" / "python" / "wheel-manifest.json").write_text(json.dumps({"distributions": []}))
    (package / "projecta" / "semantic-core" / "java-third-party-notices.json").write_text(
        json.dumps({"libraries": []})
    )
    provenance = {"sourceRevision": "abc", "sourceFilesSha256": "x", "sourceFiles": []}

    manifest = builder.write_manifest(
        package, "fp-test", source_provenance=provenance, release_eligible=True, authenticode_signing=None
    )

    assert manifest["releaseEligible"] is True
    assert manifest["distributionChannel"] == "signed-release"
    assert manifest["authenticodeSigning"] is None
    assert manifest["publicKeyFingerprint"] == "fp-test"


def test_release_manifest_still_requires_ed25519_anchor(tmp_path: Path) -> None:
    """Authenticode optionality never waives the mandatory Ed25519 trust anchor."""
    import json

    package = tmp_path / "package"
    (package / "projecta" / "semantic-core").mkdir(parents=True)
    (package / "runtime" / "python").mkdir(parents=True)
    (package / "runtime" / "java" / "legal").mkdir(parents=True)
    (package / "runtime" / "python" / "wheel-manifest.json").write_text(json.dumps({"distributions": []}))
    (package / "projecta" / "semantic-core" / "java-third-party-notices.json").write_text(
        json.dumps({"libraries": []})
    )
    provenance = {"sourceRevision": "abc", "sourceFilesSha256": "x", "sourceFiles": []}

    with pytest.raises(SystemExit) as failure:
        builder.write_manifest(
            package, None, source_provenance=provenance, release_eligible=True, authenticode_signing=None
        )

    assert "Ed25519 trust anchor" in str(failure.value)


def test_source_provenance_hashes_untracked_build_inputs(tmp_path: Path) -> None:
    script = tmp_path / "scripts" / "projecta_start.ps1"
    script.parent.mkdir()
    script.write_bytes(b"first build input\n")

    first_records = builder._source_input_records(tmp_path, ("scripts",))
    first_digest = builder._records_sha256(first_records)
    assert first_records == [
        {
            "path": "scripts/projecta_start.ps1",
            "size": len(b"first build input\n"),
            "sha256": hashlib.sha256(b"first build input\n").hexdigest(),
        }
    ]

    script.write_bytes(b"changed build input\n")
    second_records = builder._source_input_records(tmp_path, ("scripts",))
    assert builder._records_sha256(second_records) != first_digest


def test_license_override_rejects_malformed_entry(tmp_path: Path) -> None:
    """A pinned license entry without URL=PATH fails closed."""

    with pytest.raises(SystemExit) as failure:
        builder._resolve_license_overrides("https://example.invalid/license.html")

    assert "URL=PATH" in str(failure.value)


def test_license_override_rejects_missing_file(tmp_path: Path) -> None:
    """A pinned license URL pointing at no file fails closed."""

    with pytest.raises(SystemExit) as failure:
        builder._resolve_license_overrides(
            f"https://example.invalid/license.html={tmp_path / 'absent.txt'}"
        )

    assert "missing or unsafe" in str(failure.value)


def test_pinned_license_text_keeps_official_url_and_validates_content(
    tmp_path: Path,
) -> None:
    """A pinned file supplies authentic bytes without changing the source URL."""

    notice_root = tmp_path / "semantic-core" / "third-party-notices"
    notice_root.mkdir(parents=True)
    pinned = tmp_path / "classpath-license.txt"
    pinned.write_bytes(b"GPL2 w/ CPE authentic license text " + b"x" * 200)
    overrides = builder._resolve_license_overrides(
        f"https://www.gnu.org/software/classpath/license.html={pinned}"
    )
    record = builder._store_java_license(
        notice_root,
        {},
        name="GPL2 w/ CPE",
        url="https://www.gnu.org/software/classpath/license.html",
        pinned_files=overrides,
    )

    assert record["sourceUrl"] == "https://www.gnu.org/software/classpath/license.html"
    assert record["retrieval"] == "pinned-file:classpath-license.txt"
    assert (tmp_path / "semantic-core" / record["path"]).is_file()

    with pytest.raises(SystemExit):
        builder._read_pinned_license_text(tmp_path / "absent.txt", "https://example.invalid/x")
