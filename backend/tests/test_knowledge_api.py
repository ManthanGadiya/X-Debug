"""Integration tests for the knowledge graph endpoints."""

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


def test_build_merges_analysis_and_runtime(client: TestClient) -> None:
    """Building after analysis and runtime merges evidence from both."""
    project_id = _ingest(
        client,
        {"main.py": "def greet(name):\n    return f'Hi {name}'\n\nprint(greet('x'))\n"},
    )
    _start_analysis(client, project_id)
    _start_run(client, project_id)

    response = client.post("/api/v1/knowledge/build", json={"project_id": project_id})

    assert response.status_code == 200
    body = response.json()
    assert body["project_id"] == project_id
    assert body["status"] == "ready"
    assert body["stats"]["node_count"] > 0
    assert body["stats"]["edge_count"] > 0
    assert "ast" in body["sources"]
    assert "runtime" in body["sources"]
    assert body["stats"]["node_kinds"]["function"] > 0
    assert body["stats"]["edge_kinds"]["executes_after"] > 0


def test_build_with_only_analysis(client: TestClient) -> None:
    """Building without runtime evidence reports runtime as missing."""
    project_id = _ingest(client, {"main.py": "def f():\n    return 1\n"})
    _start_analysis(client, project_id)

    response = client.post("/api/v1/knowledge/build", json={"project_id": project_id})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert "runtime" in body["missing_sources"]
    assert body["sources"] == ["ast", "callgraph", "cfg", "dataflow", "dependency"]


def test_build_requires_evidence(client: TestClient) -> None:
    """Building without any analysis or runtime evidence is rejected."""
    project_id = _ingest(client, {"main.py": "pass\n"})

    response = client.post("/api/v1/knowledge/build", json={"project_id": project_id})

    assert response.status_code == 422
    assert response.json()["status"] == "error"


def test_build_unknown_project_returns_404(client: TestClient) -> None:
    """Building for an unknown project returns the structured error envelope."""
    response = client.post("/api/v1/knowledge/build", json={"project_id": "nope"})

    assert response.status_code == 404
    assert response.json()["status"] == "error"


def test_get_knowledge_after_build(client: TestClient) -> None:
    """A built knowledge graph is retrievable by project id."""
    project_id = _ingest(
        client,
        {
            "utils.py": "def helper(x):\n    return x * 2\n",
            "main.py": "from utils import helper\n\ndef run():\n    return helper(1)\n",
        },
    )
    _start_analysis(client, project_id)
    client.post("/api/v1/knowledge/build", json={"project_id": project_id})

    response = client.get(f"/api/v1/knowledge/{project_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert any(node["kind"] == "function" for node in body["nodes"])
    assert any(node["kind"] == "module" for node in body["nodes"])
    assert any(edge["kind"] == "calls" for edge in body["edges"])
    assert any(edge["kind"] == "imports" for edge in body["edges"])


def test_get_unknown_knowledge_returns_404(client: TestClient) -> None:
    """Unknown projects have no stored knowledge graph."""
    response = client.get("/api/v1/knowledge/missing")

    assert response.status_code == 404
    assert response.json()["status"] == "error"
