"""Integration tests for repository ingestion endpoints."""

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


def test_upload_project_returns_normalized_structure(client: TestClient) -> None:
    """A zip upload returns the normalized project representation."""
    payload = _zip_payload({"main.py": "print('hi')\n", "lib/util.c": "int x;\n"})

    response = client.post(
        "/api/v1/projects/upload",
        files={"file": ("demo.zip", payload, "application/zip")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "demo"
    assert body["source"] == "upload"
    assert body["file_count"] == 2
    assert body["source_file_count"] == 2
    assert body["languages"] == ["Python", "C"]
    assert {file["path"] for file in body["files"]} == {"main.py", "lib/util.c"}
    assert all(file["lines"] == 1 for file in body["files"])


def test_upload_project_ignores_binaries(client: TestClient) -> None:
    """Binary assets in the archive are excluded from the result."""
    payload = _zip_payload({"main.py": "pass\n", "logo.png": ""})

    response = client.post(
        "/api/v1/projects/upload",
        files={"file": ("demo.zip", payload, "application/zip")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["file_count"] == 1
    assert body["files"][0]["path"] == "main.py"


def test_upload_rejects_non_zip(client: TestClient) -> None:
    """Non-zip uploads return the structured error envelope."""
    response = client.post(
        "/api/v1/projects/upload",
        files={"file": ("demo.tar.gz", b"not zip", "application/gzip")},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["status"] == "error"
    assert "zip" in body["reason"].lower()


def test_upload_rejects_missing_file(client: TestClient) -> None:
    """Uploads without a file are rejected."""
    response = client.post("/api/v1/projects/upload")

    assert response.status_code == 422


def test_github_ingest_validates_url(client: TestClient) -> None:
    """An empty GitHub URL fails validation."""
    response = client.post(
        "/api/v1/projects/github",
        json={"url": ""},
    )

    assert response.status_code == 422


def test_list_projects_empty(client: TestClient) -> None:
    """Listing projects before any ingestion returns an empty list."""
    response = client.get("/api/v1/projects")

    assert response.status_code == 200
    assert response.json() == []


def test_list_projects_returns_ingested_newest_first(client: TestClient) -> None:
    """Ingested projects appear in the listing, most recent first."""
    first_id = _ingest_id(client, "first.zip", {"a.py": "print(1)\n"})
    second_id = _ingest_id(client, "second.zip", {"b.py": "print(2)\n"})

    response = client.get("/api/v1/projects")
    assert response.status_code == 200
    body = response.json()

    assert [project["id"] for project in body] == [second_id, first_id]
    assert body[0]["name"] == "second"
    assert body[0]["languages"] == ["Python"]


def test_get_project_returns_normalized_structure(client: TestClient) -> None:
    """A project detail response matches the upload structure."""
    project_id = _ingest_id(
        client,
        "demo.zip",
        {"main.py": "print('hi')\n", "lib/util.c": "int x;\n"},
    )

    response = client.get(f"/api/v1/projects/{project_id}")
    assert response.status_code == 200
    body = response.json()

    assert body["id"] == project_id
    assert body["name"] == "demo"
    assert body["source"] == "upload"
    assert body["file_count"] == 2
    assert body["source_file_count"] == 2
    assert body["languages"] == ["Python", "C"]
    assert {file["path"] for file in body["files"]} == {"main.py", "lib/util.c"}
    assert all(file["lines"] == 1 for file in body["files"])


def test_get_project_unknown_returns_404(client: TestClient) -> None:
    """Unknown project IDs produce the structured error envelope."""
    response = client.get("/api/v1/projects/nope")

    assert response.status_code == 404
    body = response.json()
    assert body["status"] == "error"
    assert body["reason"] == "Project not found"


def _ingest_id(client: TestClient, filename: str, files: dict[str, str]) -> str:
    response = client.post(
        "/api/v1/projects/upload",
        files={"file": (filename, _zip_payload(files), "application/zip")},
    )
    assert response.status_code == 200
    return response.json()["id"]
