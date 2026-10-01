from __future__ import annotations

import importlib.util
import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

_bootstrap_path = Path(__file__).resolve().parents[2] / "scripts" / "bootstrap_fuseki.py"
_bootstrap_spec = importlib.util.spec_from_file_location("projecta_bootstrap_fuseki", _bootstrap_path)
if _bootstrap_spec is None or _bootstrap_spec.loader is None:
    raise RuntimeError("could not load the Fuseki bootstrap module")
bootstrap_fuseki = importlib.util.module_from_spec(_bootstrap_spec)
_bootstrap_spec.loader.exec_module(bootstrap_fuseki)


class _Response:
    status = 200

    def __init__(self, payload: bytes = b"") -> None:
        self.payload = payload

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self) -> bytes:
        return self.payload


def _write_ontology(directory: Path) -> None:
    for module in bootstrap_fuseki.MODULES:
        module_path = directory / module
        module_path.parent.mkdir(parents=True, exist_ok=True)
        module_path.write_text(
            "@prefix projecta: <https://w3id.org/projecta/ontology/> .\n",
            encoding="utf-8",
        )


def _configure(monkeypatch: pytest.MonkeyPatch, ontology: Path, marker: Path) -> None:
    monkeypatch.setenv("ONTOLOGY_DIRECTORY", str(ontology))
    monkeypatch.setenv("FUSEKI_DATASET_URL", "http://127.0.0.1:3030/projecta")
    monkeypatch.setenv("PROJECTA_BOOTSTRAP_ACCEPTANCE_PROJECTS", "project-alpha|Project Alpha")
    monkeypatch.setenv("PROJECTA_FUSEKI_BOOTSTRAP_MARKER_FILE", str(marker))


def _marker(marker: Path, phase: str) -> None:
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(
        json.dumps(
            {"schemaVersion": 1, "bootstrapRevision": 1, "phase": phase},
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )


def test_bootstrap_initializes_an_empty_dataset_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ontology = tmp_path / "ontology"
    _write_ontology(ontology)
    marker = tmp_path / "state" / "projecta-bootstrap.json"
    _configure(monkeypatch, ontology, marker)
    graphs: dict[str, list[str]] = {}
    requests: list[urllib.request.Request] = []

    def store_graph(request: urllib.request.Request, timeout: float) -> _Response:
        del timeout
        requests.append(request)
        if request.get_method() == "GET":
            return _Response(b'{"boolean":false}')
        assert request.get_method() == "POST"
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(request.full_url).query)
        assert request.data is not None
        graphs.setdefault(query["graph"][0], []).append(request.data.decode("utf-8"))
        return _Response()

    monkeypatch.setattr(bootstrap_fuseki.urllib.request, "urlopen", store_graph)

    assert bootstrap_fuseki.main() == 0
    assert [request.get_method() for request in requests] == ["GET", "POST", "POST"]
    assert json.loads(marker.read_text(encoding="utf-8")) == {
        "schemaVersion": 1,
        "bootstrapRevision": 1,
        "phase": "complete",
    }
    assert len(graphs[bootstrap_fuseki.ONTOLOGY_GRAPH]) == 1
    assert len(graphs["https://w3id.org/projecta/data/project/project-alpha/asserted/"]) == 1

    assert bootstrap_fuseki.main() == 0
    assert len(requests) == 3


def test_bootstrap_preserves_an_existing_unmarked_dataset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ontology = tmp_path / "ontology"
    _write_ontology(ontology)
    marker = tmp_path / "state" / "projecta-bootstrap.json"
    _configure(monkeypatch, ontology, marker)
    graphs = {"existing-project-graph": ["existing user notes"]}
    requests: list[urllib.request.Request] = []

    def inspect_existing_data(request: urllib.request.Request, timeout: float) -> _Response:
        del timeout
        requests.append(request)
        assert request.get_method() == "GET"
        return _Response(b'{"boolean":true}')

    monkeypatch.setattr(
        bootstrap_fuseki.urllib.request,
        "urlopen",
        inspect_existing_data,
    )

    assert bootstrap_fuseki.main() == 0
    assert graphs == {"existing-project-graph": ["existing user notes"]}
    assert json.loads(marker.read_text(encoding="utf-8"))["phase"] == "existing-data-preserved"
    assert len(requests) == 1
    assert bootstrap_fuseki.main() == 0
    assert len(requests) == 1


def test_bootstrap_resumes_append_only_after_interruption(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ontology = tmp_path / "ontology"
    _write_ontology(ontology)
    marker = tmp_path / "state" / "projecta-bootstrap.json"
    _configure(monkeypatch, ontology, marker)
    _marker(marker, "initializing")
    ontology_graph = bootstrap_fuseki.ONTOLOGY_GRAPH
    project_graph = "https://w3id.org/projecta/data/project/project-alpha/asserted/"
    graphs = {ontology_graph: ["existing ontology data"], project_graph: ["existing project notes"]}
    requests: list[urllib.request.Request] = []

    def append_graph(request: urllib.request.Request, timeout: float) -> _Response:
        del timeout
        requests.append(request)
        assert request.get_method() == "POST"
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(request.full_url).query)
        assert request.data is not None
        graphs.setdefault(query["graph"][0], []).append(request.data.decode("utf-8"))
        return _Response()

    monkeypatch.setattr(bootstrap_fuseki.urllib.request, "urlopen", append_graph)

    assert bootstrap_fuseki.main() == 0
    assert len(requests) == 2
    assert "existing ontology data" in graphs[ontology_graph]
    assert "existing project notes" in graphs[project_graph]
    assert json.loads(marker.read_text(encoding="utf-8"))["phase"] == "complete"


def test_bootstrap_leaves_an_interrupted_marker_when_fuseki_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ontology = tmp_path / "ontology"
    _write_ontology(ontology)
    marker = tmp_path / "state" / "projecta-bootstrap.json"
    _configure(monkeypatch, ontology, marker)

    def unavailable(request: urllib.request.Request, timeout: float) -> _Response:
        del timeout
        if request.get_method() == "GET":
            return _Response(b'{"boolean":false}')
        raise urllib.error.URLError("offline")

    monkeypatch.setattr(bootstrap_fuseki.urllib.request, "urlopen", unavailable)

    with pytest.raises(urllib.error.URLError):
        bootstrap_fuseki.main()
    assert json.loads(marker.read_text(encoding="utf-8"))["phase"] == "initializing"


@pytest.mark.parametrize(
    "marker_data",
    [
        {"schemaVersion": True, "bootstrapRevision": 1, "phase": "complete"},
        {"schemaVersion": 1, "bootstrapRevision": 1, "phase": []},
        {"schemaVersion": 1, "bootstrapRevision": 0, "phase": "initializing"},
    ],
)
def test_bootstrap_rejects_invalid_markers_before_contacting_fuseki(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    marker_data: dict[str, object],
) -> None:
    ontology = tmp_path / "ontology"
    marker = tmp_path / "state" / "projecta-bootstrap.json"
    _configure(monkeypatch, ontology, marker)
    marker.parent.mkdir(parents=True)
    marker.write_text(json.dumps(marker_data), encoding="utf-8")
    requests: list[urllib.request.Request] = []

    def record_request(request: urllib.request.Request, timeout: float) -> _Response:
        del timeout
        requests.append(request)
        return _Response()

    monkeypatch.setattr(bootstrap_fuseki.urllib.request, "urlopen", record_request)

    with pytest.raises(RuntimeError):
        bootstrap_fuseki.main()
    assert requests == []
