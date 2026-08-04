"""Integration tests for the static analysis endpoints."""

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


def _start_analysis(client: TestClient, project_id: str) -> dict:
    response = client.post("/api/v1/analysis/start", json={"project_id": project_id})
    assert response.status_code == 202
    return response.json()


def test_start_returns_queued_summary(client: TestClient) -> None:
    """Starting an analysis returns a queued record for the project."""
    project_id = _ingest(client, {"main.py": "def f():\n    return 1\n"})
    body = _start_analysis(client, project_id)

    assert body["project_id"] == project_id
    assert body["status"] in {"queued", "running", "ready"}
    assert body["id"]


def test_analysis_completes_to_ready(client: TestClient) -> None:
    """The background analysis finishes and produces graph results."""
    project_id = _ingest(client, {"main.py": "def f():\n    return 1\n"})
    analysis_id = _start_analysis(client, project_id)["id"]

    detail = client.get(f"/api/v1/analysis/{analysis_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["status"] == "ready"
    assert body["parsed_file_count"] == 1
    assert body["failed_file_count"] == 0
    assert body["dependency_edge_count"] >= 0
    assert body["cfg_node_count"] > 0


def test_get_unknown_analysis_returns_404(client: TestClient) -> None:
    """Unknown analysis identifiers return the structured error envelope."""
    response = client.get("/api/v1/analysis/missing")

    assert response.status_code == 404
    assert response.json()["status"] == "error"


def test_start_unknown_project_returns_404(client: TestClient) -> None:
    """Starting an analysis for an unknown project is rejected."""
    response = client.post("/api/v1/analysis/start", json={"project_id": "nope"})

    assert response.status_code == 404
    assert response.json()["status"] == "error"


def test_graph_endpoint_returns_graph_data(client: TestClient) -> None:
    """A finished analysis exposes its graphs as serializable payloads."""
    project_id = _ingest(
        client,
        {
            "utils.py": "def helper(x):\n    return x * 2\n",
            "main.py": "from utils import helper\n\ndef run():\n    return helper(1)\n",
        },
    )
    analysis_id = _start_analysis(client, project_id)["id"]
    assert client.get(f"/api/v1/analysis/{analysis_id}").json()["status"] == "ready"

    response = client.get(f"/api/v1/analysis/{analysis_id}/graphs/call")
    assert response.status_code == 200
    body = response.json()
    assert body["node_count"] > 0
    assert body["edge_count"] > 0
    assert any(node["label"] == "helper" for node in body["nodes"])


def test_graph_endpoint_rejects_unknown_kind(client: TestClient) -> None:
    """Graph kinds outside the supported set are rejected by validation."""
    project_id = _ingest(client, {"main.py": "pass\n"})
    analysis_id = _start_analysis(client, project_id)["id"]

    response = client.get(f"/api/v1/analysis/{analysis_id}/graphs/bogus")

    assert response.status_code == 422


def test_list_analysis_empty(client: TestClient) -> None:
    """Listing analysis runs before any start returns an empty list."""
    response = client.get("/api/v1/analysis")

    assert response.status_code == 200
    assert response.json() == []


def test_list_analysis_returns_runs_newest_first(client: TestClient) -> None:
    """Started analyses appear in the listing, most recent first."""
    project_id = _ingest(client, {"main.py": "pass\n"})
    first_id = _start_analysis(client, project_id)["id"]
    second_id = _start_analysis(client, project_id)["id"]

    response = client.get("/api/v1/analysis")
    assert response.status_code == 200
    body = response.json()

    assert [run["id"] for run in body] == [second_id, first_id]
    assert all(run["project_id"] == project_id for run in body)
    assert body[0]["status"] in {"queued", "running", "ready", "failed"}
