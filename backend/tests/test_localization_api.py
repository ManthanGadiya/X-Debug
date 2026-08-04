"""Integration tests for the bug localization endpoints."""

from __future__ import annotations

import io
import zipfile

from fastapi.testclient import TestClient


def _zip_payload(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def _ingest(client: TestClient, files: dict[str, str]) -> str:
    response = client.post(
        "/api/v1/projects/upload",
        files={"file": ("demo.zip", _zip_payload(files), "application/zip")},
    )
    assert response.status_code == 200
    return response.json()["id"]


def _start_analysis(client: TestClient, project_id: str) -> None:
    response = client.post("/api/v1/analysis/start", json={"project_id": project_id})
    assert response.status_code == 202


def _start_run(client: TestClient, project_id: str) -> None:
    response = client.post("/api/v1/runtime/run", json={"project_id": project_id})
    assert response.status_code == 202


def _build(client: TestClient, project_id: str) -> None:
    response = client.post("/api/v1/knowledge/build", json={"project_id": project_id})
    assert response.status_code == 200


_CRASH_PROJECT = {
    "compute.py": "def compute(x):\n    return 10 / x\n",
    "main.py": "from compute import compute\n\ndef main():\n    return compute(0)\n\nmain()\n",
}

_HEALTHY_PROJECT = {"main.py": "def f():\n    return 1\n"}


def test_localize_after_crash(client: TestClient) -> None:
    """A crash project is localized with ranked candidates."""
    project_id = _ingest(client, _CRASH_PROJECT)
    _start_analysis(client, project_id)
    _start_run(client, project_id)
    _build(client, project_id)

    response = client.post(f"/api/v1/localization/{project_id}", json={"language": "python"})

    assert response.status_code == 200
    body = response.json()
    assert body["project_id"] == project_id
    assert body["status"] == "ready"
    assert isinstance(body["resolved"], bool)
    assert body["confidence"] >= 0.0
    assert body["summary"]
    assert isinstance(body["candidates"], list)
    assert body["candidates"]
    assert isinstance(body["propagation_path"], list)
    assert isinstance(body["missing_sources"], list)


def test_localize_without_runtime_is_unresolved(client: TestClient) -> None:
    """Without runtime evidence the result is unresolved and explains why."""
    project_id = _ingest(client, _HEALTHY_PROJECT)
    _start_analysis(client, project_id)
    _build(client, project_id)

    response = client.post(f"/api/v1/localization/{project_id}", json={"language": "python"})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["resolved"] is False
    assert body["confidence"] == 0.0
    assert body["candidates"] == []
    assert "runtime_trace" in body["missing_sources"]


def test_localize_get_returns_stored_result(client: TestClient) -> None:
    """The stored result is retrievable after a run."""
    project_id = _ingest(client, _CRASH_PROJECT)
    _start_analysis(client, project_id)
    _start_run(client, project_id)
    _build(client, project_id)
    client.post(f"/api/v1/localization/{project_id}", json={"language": "python"})

    response = client.get(f"/api/v1/localization/{project_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["project_id"] == project_id
    assert body["status"] == "ready"


def test_localize_unknown_project_returns_404(client: TestClient) -> None:
    """Unknown projects return the structured error envelope."""
    response = client.post("/api/v1/localization/nope", json={"language": "python"})

    assert response.status_code == 404
    assert response.json()["status"] == "error"


def test_localize_unsupported_language_returns_422(client: TestClient) -> None:
    """Unsupported languages are rejected with the structured error envelope."""
    project_id = _ingest(client, _HEALTHY_PROJECT)

    response = client.post(f"/api/v1/localization/{project_id}", json={"language": "brainfuck"})

    assert response.status_code == 422
    assert response.json()["status"] == "error"


def test_localize_accepts_canonical_language(client: TestClient) -> None:
    """The canonical language value works as well as the lowercase form."""
    project_id = _ingest(client, _CRASH_PROJECT)
    _start_analysis(client, project_id)
    _start_run(client, project_id)
    _build(client, project_id)

    response = client.post(f"/api/v1/localization/{project_id}", json={"language": "Python"})

    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_localize_without_knowledge_returns_404(client: TestClient) -> None:
    """A project with no built knowledge graph is not localizable."""
    project_id = _ingest(client, _HEALTHY_PROJECT)

    response = client.post(f"/api/v1/localization/{project_id}", json={"language": "python"})

    assert response.status_code == 404
    assert response.json()["status"] == "error"


def test_get_unknown_localization_returns_404(client: TestClient) -> None:
    """Fetching a localization that was never run is a structured 404."""
    project_id = _ingest(client, _HEALTHY_PROJECT)

    response = client.get(f"/api/v1/localization/{project_id}")

    assert response.status_code == 404
