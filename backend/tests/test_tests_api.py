"""Integration tests for the test execution endpoints."""

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


def _start_tests(client: TestClient, project_id: str) -> dict:
    response = client.post("/api/v1/tests/run", json={"project_id": project_id})
    assert response.status_code == 202
    return response.json()


def test_start_returns_queued_summary(client: TestClient) -> None:
    """Starting a test run returns a queued record for the project."""
    project_id = _ingest(client, {"test_sample.py": "def test_ok():\n    assert True\n"})
    body = _start_tests(client, project_id)

    assert body["project_id"] == project_id
    assert body["status"] in {"queued", "running", "ready"}
    assert body["id"]


def test_test_run_completes_to_ready(client: TestClient) -> None:
    """The background test run finishes and reports per-case results."""
    project_id = _ingest(
        client,
        {
            "test_sample.py": (
                "def test_add():\n    assert 1 + 1 == 2\n\n"
                "def test_sub():\n    assert 3 - 1 == 2\n"
            )
        },
    )
    run_id = _start_tests(client, project_id)["id"]

    detail = client.get(f"/api/v1/tests/{run_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["status"] == "ready"
    assert "Python" in body["languages"]
    assert body["tests_run"] == 2
    assert body["passed"] == 2
    assert body["failed"] == 0
    assert body["succeeded"] is True

    results = client.get(f"/api/v1/tests/{run_id}/results/Python")
    assert results.status_code == 200
    results_body = results.json()
    assert results_body["tests_run"] == 2
    names = {case["name"] for case in results_body["cases"]}
    assert "test_add" in names
    assert "test_sub" in names


def test_failing_test_reported_through_api(client: TestClient) -> None:
    """A failing test surfaces its failure count and per-case outcome."""
    project_id = _ingest(client, {"test_bad.py": "def test_fails():\n    assert 1 == 2\n"})
    run_id = _start_tests(client, project_id)["id"]

    detail = client.get(f"/api/v1/tests/{run_id}").json()
    assert detail["status"] == "ready"
    assert detail["failed"] == 1
    assert detail["succeeded"] is False

    results = client.get(f"/api/v1/tests/{run_id}/results/Python").json()
    assert results["cases"][0]["outcome"] == "failed"


def test_get_unknown_test_run_returns_404(client: TestClient) -> None:
    """Unknown test run identifiers return the structured error envelope."""
    response = client.get("/api/v1/tests/missing")

    assert response.status_code == 404
    assert response.json()["status"] == "error"


def test_start_unknown_project_returns_404(client: TestClient) -> None:
    """Starting a test run for an unknown project is rejected."""
    response = client.post("/api/v1/tests/run", json={"project_id": "nope"})

    assert response.status_code == 404
    assert response.json()["status"] == "error"


def test_results_rejects_unknown_language(client: TestClient) -> None:
    """Languages outside the supported set are rejected by validation."""
    project_id = _ingest(client, {"test_sample.py": "def test_ok():\n    pass\n"})
    run_id = _start_tests(client, project_id)["id"]

    response = client.get(f"/api/v1/tests/{run_id}/results/Rust")

    assert response.status_code == 422
