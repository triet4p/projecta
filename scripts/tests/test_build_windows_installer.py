"""Staged-commit behavior tests for the per-user NSIS installer transaction.

The 0.7.0 unsigned installer stages the full application tree into a sibling
``*.staging`` directory and then renames it over the install directory. The
transaction fails closed when the installer process still has the staging
directory as its working directory: Windows refuses to rename a process's
own current directory, so the commit rename always fails and the installer
reports that the staged files could not be committed. These tests exercise
that exact mechanics through the real pinned NSIS 3.13 toolchain in
throwaway directories: a fresh install must commit the staged payload, an
upgrade must replace the previous tree, and a forced commit failure must
leave the previous installation in place. Nothing here touches the owner
profile, HKCU, shortcuts, or the network.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
NSIS_COMPILER = (
    ROOT / "build" / "tools" / "nsis-3.13" / "distribution" / "nsis-3.13" / "makensis.exe"
)
INSTALLER_SCRIPT = ROOT / "scripts" / "projecta-setup.nsi"

_COPY_COMMIT_SECTION = r"""
Section "probe"
  CreateDirectory "${TARGET_ROOT}"
  GetTempFileName $0 "${TARGET_ROOT}"
  Delete "$0"
  StrCpy $1 "$0.staging"
  GetTempFileName $0 "${TARGET_ROOT}"
  Delete "$0"
  StrCpy $2 "$0.previous"
  CreateDirectory "$1"
  SetOutPath "$1"
  File /r "${SOURCE_DIR}\*"
  StrCpy $3 0
  SetOutPath "${TARGET_ROOT}"
  IfFileExists "${TARGET_INST}" 0 stageReady
  IfFileExists "${TARGET_INST}\*.*" 0 stageReady
  ClearErrors
  Rename "${TARGET_INST}" "$2"
  StrCpy $3 1
stageReady:
  SetOutPath "${TARGET_ROOT}"
  ClearErrors
  IfFileExists "${TARGET_INST}" 0 commitRename
  RMDir "${TARGET_INST}"
  ClearErrors
commitRename:
  Rename "$1" "${TARGET_INST}"
  IfErrors commitFailed 0
  StrCmp $3 1 removePreviousTemp cleanupTemp
cleanupTemp:
  RMDir "$2"
removePreviousTemp:
  RMDir /r "$2"
  Goto finishCommit
finishCommit:
  FileOpen $9 "${TARGET_ROOT}\RESULT.txt" w
  FileWrite $9 "COMMITTED"
  FileClose $9
  Goto done
commitFailed:
  StrCmp $3 1 0 preserved
  ClearErrors
  Rename "$2" "${TARGET_INST}"
preserved:
  RMDir /r "$1"
  RMDir "$2"
  FileOpen $9 "${TARGET_ROOT}\RESULT.txt" w
  FileWrite $9 "NOT_COMMITTED"
  FileClose $9
done:
SectionEnd
"""


_SABOTAGED_COMMIT_SECTION = _COPY_COMMIT_SECTION.replace(
    '  SetOutPath "${TARGET_ROOT}"\n',
    "",
)


def _compile_probe(tmp_path: Path, *, body: str) -> Path:
    source = tmp_path / "payload"
    (source).mkdir()
    (source / "hello.txt").write_text("probe payload\n", encoding="utf-8")
    script = tmp_path / "probe.nsi"
    script.write_text(
        "Unicode true\n"
        'Name "CommitProbe"\n'
        'OutFile "${OUTPUT_FILE}"\n'
        'InstallDir "${TARGET_INST}"\n'
        "RequestExecutionLevel user\n"
        "ShowInstDetails show\n" + body,
        encoding="utf-8",
    )
    output = tmp_path / "probe.exe"
    completed = subprocess.run(
        [
            str(NSIS_COMPILER),
            f"/DSOURCE_DIR={source}",
            f"/DTARGET_ROOT={tmp_path}",
            f"/DTARGET_INST={tmp_path / 'app'}",
            f"/DOUTPUT_FILE={output}",
            str(script),
        ],
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr[-2000:]
    assert output.is_file()
    return output


def _run_silent(installer: Path, timeout: int = 120) -> None:
    completed = subprocess.run(
        [str(installer), "/S"],
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )
    assert completed.returncode == 0, completed.stderr[-2000:]


@pytest.mark.skipif(os.name != "nt" or not NSIS_COMPILER.is_file(), reason="pinned NSIS toolchain is required")
def test_staged_commit_installs_payload(tmp_path: Path) -> None:
    """A fresh install commits the staged payload to the target directory."""

    installer = _compile_probe(tmp_path, body=_COPY_COMMIT_SECTION)
    _run_silent(installer)

    assert (tmp_path / "RESULT.txt").read_text(encoding="utf-8") == "COMMITTED"
    assert (tmp_path / "app" / "hello.txt").read_text(encoding="utf-8") == "probe payload\n"

@pytest.mark.skipif(os.name != "nt" or not NSIS_COMPILER.is_file(), reason="pinned NSIS toolchain is required")
def test_staged_commit_installs_into_empty_target_directory(tmp_path: Path) -> None:
    """A pre-created but empty target directory still commits the payload."""

    previous = tmp_path / "app"
    previous.mkdir()

    installer = _compile_probe(tmp_path, body=_COPY_COMMIT_SECTION)
    _run_silent(installer)

    assert (tmp_path / "RESULT.txt").read_text(encoding="utf-8") == "COMMITTED"
    assert (previous / "hello.txt").read_text(encoding="utf-8") == "probe payload\n"



@pytest.mark.skipif(os.name != "nt" or not NSIS_COMPILER.is_file(), reason="pinned NSIS toolchain is required")
def test_staged_commit_upgrade_replaces_previous_install(tmp_path: Path) -> None:
    """An upgrade moves the previous tree aside and commits the new payload."""

    previous = tmp_path / "app"
    previous.mkdir()
    (previous / "legacy.txt").write_text("previous version\n", encoding="utf-8")

    installer = _compile_probe(tmp_path, body=_COPY_COMMIT_SECTION)
    _run_silent(installer)

    assert (tmp_path / "RESULT.txt").read_text(encoding="utf-8") == "COMMITTED"
    assert (previous / "hello.txt").read_text(encoding="utf-8") == "probe payload\n"
    assert not (previous / "legacy.txt").exists()

@pytest.mark.skipif(os.name != "nt" or not NSIS_COMPILER.is_file(), reason="pinned NSIS toolchain is required")
def test_forced_commit_failure_preserves_previous_install(tmp_path: Path) -> None:
    """A failed commit restores the previous tree and reports no commit."""

    previous = tmp_path / "app"
    previous.mkdir()
    (previous / "legacy.txt").write_text("previous version\n", encoding="utf-8")

    installer = _compile_probe(tmp_path, body=_SABOTAGED_COMMIT_SECTION)
    _run_silent(installer)

    assert (tmp_path / "RESULT.txt").read_text(encoding="utf-8") == "NOT_COMMITTED"
    assert (previous / "legacy.txt").read_text(encoding="utf-8") == "previous version\n"
    assert not (previous / "hello.txt").exists()


@pytest.mark.skipif(os.name != "nt" or not NSIS_COMPILER.is_file(), reason="pinned NSIS toolchain is required")
def test_shipped_installer_script_compiles_against_fixture_package(tmp_path: Path) -> None:
    """The shipped installer script still compiles with the pinned toolchain."""

    package = tmp_path / "package"
    package.mkdir()
    (package / "ProjectaStart.ps1").write_text("exit 0\n", encoding="utf-8")
    output = tmp_path / "shipped.exe"
    completed = subprocess.run(
        [
            str(NSIS_COMPILER),
            f"/DPACKAGE_DIR={package}",
            f"/DOUTPUT_FILE={output}",
            str(INSTALLER_SCRIPT),
        ],
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr[-2000:]
    assert output.is_file()

