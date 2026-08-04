"""Integration tests for the explanation endpoints."""

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


def _localize(client: TestClient, project_id: str) -> None:
    response = client.post(f"/api/v1/localization/{project_id}", json={"language": "python"})
    assert response.status_code == 200


_CRASH_PROJECT = {
    "compute.py": "def compute(x):\n    return 10 / x\n",
    "main.py": "from compute import compute\n\ndef main():\n    return compute(0)\n\nmain()\n",
}

_HEALTHY_PROJECT = {"main.py": "def f():\n    return 1\n"}


def test_explain_after_localize(client: TestClient) -> None:
    """A crash project produces a complete explanation report."""
    project_id = _ingest(client, _CRASH_PROJECT)
    _start_analysis(client, project_id)
    _start_run(client, project_id)
    _build(client, project_id)
    _localize(client, project_id)

    response = client.post(f"/api/v1/explanation/{project_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["project_id"] == project_id
    assert body["status"] == "ready"
    # The crash fixture localizes below the confidence threshold (0.664 < 0.7),
    # so the report is honest: evidence-backed but unresolved.
    assert body["resolved"] is False
    assert body["root_cause"] is None
    assert body["insufficient_evidence"] is True
    assert body["error_summary"]
    assert body["why"]
    assert isinstance(body["where"], list)
    assert body["where"]
    assert isinstance(body["evidence"], list)
    assert body["evidence"]
    assert body["confidence"] >= 0.0
    assert isinstance(body["propagation_path"], list)


def test_explain_requires_localization(client: TestClient) -> None:
    """Without a localization run the API refuses to explain."""
    project_id = _ingest(client, _CRASH_PROJECT)
    _start_analysis(client, project_id)
    _start_run(client, project_id)
    _build(client, project_id)

    response = client.post(f"/api/v1/explanation/{project_id}")

    assert response.status_code == 404
    assert response.json()["status"] == "error"


def test_explain_get_returns_stored_report(client: TestClient) -> None:
    """The generated report is retrievable after a run."""
    project_id = _ingest(client, _CRASH_PROJECT)
    _start_analysis(client, project_id)
    _start_run(client, project_id)
    _build(client, project_id)
    _localize(client, project_id)
    client.post(f"/api/v1/explanation/{project_id}")

    response = client.get(f"/api/v1/explanation/{project_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["project_id"] == project_id
    assert body["status"] == "ready"
    assert body["resolved"] is False


def test_explain_unresolved_is_honest(client: TestClient) -> None:
    """An unresolved localization explains why, without inventing a cause."""
    project_id = _ingest(client, _HEALTHY_PROJECT)
    _start_analysis(client, project_id)
    _build(client, project_id)
    _localize(client, project_id)

    response = client.post(f"/api/v1/explanation/{project_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["resolved"] is False
    assert body["root_cause"] is None
    assert body["insufficient_evidence"] is True
    assert body["evidence"] == []


def test_explain_unknown_project_returns_404(client: TestClient) -> None:
    """Unknown projects return the structured error envelope."""
    response = client.post("/api/v1/explanation/nope")

    assert response.status_code == 404
    assert response.json()["status"] == "error"


def test_get_unknown_explanation_returns_404(client: TestClient) -> None:
    """Fetching an explanation that was never generated is a structured 404."""
    project_id = _ingest(client, _HEALTHY_PROJECT)

    response = client.get(f"/api/v1/explanation/{project_id}")

    assert response.status_code == 404
