"""Integration tests for the runtime analysis endpoints."""

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


def _start_run(client: TestClient, project_id: str) -> dict:
    response = client.post("/api/v1/runtime/run", json={"project_id": project_id})
    assert response.status_code == 202
    return response.json()


def test_start_returns_queued_summary(client: TestClient) -> None:
    """Starting a runtime run returns a queued record for the project."""
    project_id = _ingest(client, {"main.py": "print('hi')\n"})
    body = _start_run(client, project_id)

    assert body["project_id"] == project_id
    assert body["status"] in {"queued", "running", "ready"}
    assert body["id"]


def test_run_completes_to_ready_with_trace(client: TestClient) -> None:
    """The background run finishes and captures an execution trace."""
    project_id = _ingest(
        client,
        {
            "main.py": (
                "def greet(name):\n" "    return f'hello {name}'\n" "\n" "print(greet('world'))\n"
            )
        },
    )
    run_id = _start_run(client, project_id)["id"]

    detail = client.get(f"/api/v1/runtime/{run_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["status"] == "ready"
    assert "Python" in body["languages"]
    assert body["succeeded"] is True

    trace = client.get(f"/api/v1/runtime/{run_id}/trace/Python")
    assert trace.status_code == 200
    trace_body = trace.json()
    assert trace_body["stdout"].strip() == "hello world"
    assert trace_body["event_count"] > 0
    assert "greet" in trace_body["function_order"]


def test_run_captures_exception(client: TestClient) -> None:
    """A crashing entry point surfaces the exception through the trace endpoint."""
    project_id = _ingest(client, {"main.py": "raise ValueError('kaboom')\n"})
    run_id = _start_run(client, project_id)["id"]

    trace = client.get(f"/api/v1/runtime/{run_id}/trace/Python")
    assert trace.status_code == 200
    body = trace.json()
    assert body["exception"] is not None
    assert body["exception"]["type"] == "ValueError"


def test_get_unknown_run_returns_404(client: TestClient) -> None:
    """Unknown runtime identifiers return the structured error envelope."""
    response = client.get("/api/v1/runtime/missing")

    assert response.status_code == 404
    assert response.json()["status"] == "error"


def test_start_unknown_project_returns_404(client: TestClient) -> None:
    """Starting a run for an unknown project is rejected."""
    response = client.post("/api/v1/runtime/run", json={"project_id": "nope"})

    assert response.status_code == 404
    assert response.json()["status"] == "error"


def test_trace_rejects_unknown_language(client: TestClient) -> None:
    """Languages outside the supported set are rejected by validation."""
    project_id = _ingest(client, {"main.py": "pass\n"})
    run_id = _start_run(client, project_id)["id"]

    response = client.get(f"/api/v1/runtime/{run_id}/trace/Rust")

    assert response.status_code == 422


def test_list_runtime_empty(client: TestClient) -> None:
    """Listing runtime runs before any start returns an empty list."""
    response = client.get("/api/v1/runtime")

    assert response.status_code == 200
    assert response.json() == []


def test_list_runtime_returns_runs_newest_first(client: TestClient) -> None:
    """Started runtime runs appear in the listing, most recent first."""
    project_id = _ingest(client, {"main.py": "print('hi')\n"})
    first_id = _start_run(client, project_id)["id"]
    second_id = _start_run(client, project_id)["id"]

    response = client.get("/api/v1/runtime")
    assert response.status_code == 200
    body = response.json()

    assert [run["id"] for run in body] == [second_id, first_id]
    assert all(run["project_id"] == project_id for run in body)
