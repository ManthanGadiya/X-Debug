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
