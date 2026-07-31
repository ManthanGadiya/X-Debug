"""Integration tests for the execution replay endpoints."""

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


def _start_run(client: TestClient, project_id: str) -> str:
    response = client.post("/api/v1/runtime/run", json={"project_id": project_id})
    assert response.status_code == 202
    return response.json()["id"]


def test_replay_summary_after_run_completes(client: TestClient) -> None:
    """A finished run exposes a replay timeline summary."""
    project_id = _ingest(
        client,
        {"main.py": "def helper():\n    return 1\n\nprint(helper())\n"},
    )
    run_id = _start_run(client, project_id)

    response = client.get(f"/api/v1/runtime/{run_id}/replay/Python")

    assert response.status_code == 200
    body = response.json()
    assert body["language"] == "Python"
    assert body["total_events"] > 0
    assert body["count_by_type"]["call"] >= 1
    assert "helper" in body["function_order"]
    assert body["first_index"] == 0
    assert body["last_index"] == body["total_events"] - 1


def test_replay_summary_captures_exception(client: TestClient) -> None:
    """A crashing run surfaces the exception in the replay summary."""
    project_id = _ingest(client, {"main.py": "raise ValueError('kaboom')\n"})
    run_id = _start_run(client, project_id)

    response = client.get(f"/api/v1/runtime/{run_id}/replay/Python")

    assert response.status_code == 200
    body = response.json()
    assert body["exception"] is not None
    assert body["exception"]["type"] == "ValueError"


def test_replay_step_navigates_forward_and_back(client: TestClient) -> None:
    """Steps link to their neighbours so a client can walk the timeline."""
    project_id = _ingest(client, {"main.py": "print('hi')\n"})
    run_id = _start_run(client, project_id)

    first = client.get(f"/api/v1/runtime/{run_id}/replay/Python/step")
    assert first.status_code == 200
    first_body = first.json()
    assert first_body["index"] == 0
    assert first_body["previous_index"] is None
    next_index = first_body["next_index"]
    assert next_index is not None

    following = client.get(
        f"/api/v1/runtime/{run_id}/replay/Python/step", params={"index": next_index}
    )
    assert following.status_code == 200
    following_body = following.json()
    assert following_body["previous_index"] == 0
    assert following_body["position"] == next_index + 1


def test_replay_steps_filters_and_paginates(client: TestClient) -> None:
    """The steps endpoint filters by event type and paginates."""
    project_id = _ingest(
        client,
        {"main.py": "def helper():\n    return 1\n\nprint(helper())\n"},
    )
    run_id = _start_run(client, project_id)

    response = client.get(
        f"/api/v1/runtime/{run_id}/replay/Python/steps",
        params={"event_type": "call", "offset": 0, "limit": 2},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 1
    assert body["offset"] == 0
    assert all(item["event"]["type"] == "call" for item in body["items"])


def test_replay_step_out_of_range_returns_404(client: TestClient) -> None:
    """Stepping past the end of the timeline returns a structured 404."""
    project_id = _ingest(client, {"main.py": "print('hi')\n"})
    run_id = _start_run(client, project_id)

    response = client.get(f"/api/v1/runtime/{run_id}/replay/Python/step", params={"index": 10_000})

    assert response.status_code == 404
    assert "detail" in response.json()


def test_replay_unknown_run_returns_404(client: TestClient) -> None:
    """Unknown runtime identifiers return the structured error envelope."""
    response = client.get("/api/v1/runtime/missing/replay/Python")

    assert response.status_code == 404
    assert response.json()["status"] == "error"


def test_replay_rejects_missing_language_result(client: TestClient) -> None:
    """Replay for a language that never ran returns a structured 404."""
    project_id = _ingest(client, {"main.py": "pass\n"})
    run_id = _start_run(client, project_id)

    response = client.get(f"/api/v1/runtime/{run_id}/replay/C")

    assert response.status_code == 404


def test_replay_rejects_unknown_language(client: TestClient) -> None:
    """Languages outside the supported set are rejected by validation."""
    project_id = _ingest(client, {"main.py": "pass\n"})
    run_id = _start_run(client, project_id)

    response = client.get(f"/api/v1/runtime/{run_id}/replay/Rust")

    assert response.status_code == 422
