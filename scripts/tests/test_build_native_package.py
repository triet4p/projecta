from __future__ import annotations

import hashlib
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
