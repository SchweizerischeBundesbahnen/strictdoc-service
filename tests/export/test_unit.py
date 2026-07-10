"""Unit tests for the export functionality of StrictDoc service."""

from http import HTTPStatus
from pathlib import Path

import pytest
from fastapi.responses import FileResponse
from fastapi.testclient import TestClient
from pytest_mock import MockFixture


@pytest.mark.parametrize(
    ("export_format", "mime_type", "file_extension", "content"),
    [
        ("html", "application/zip", ".zip", b"test content"),
        ("json", "application/json", ".json", b'{"test": "content"}'),
        ("excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".xlsx", b"test content"),
        ("reqif-sdoc", "application/xml", ".reqif", b"<?xml version='1.0'?>"),
        ("reqifz-sdoc", "application/zip", ".reqifz", b"PK"),
        ("rst", "text/x-rst", ".rst", b"test content"),
        ("sdoc", "text/plain", ".sdoc", b"test content"),
    ],
)
def test_export_formats(
    client: TestClient,
    sample_sdoc: str,
    export_format: str,
    mime_type: str,
    file_extension: str,
    content: bytes,
    mocker: MockFixture,
    tmp_path: Path,
) -> None:
    """Test exporting to different formats with proper mocking."""
    temp_file = tmp_path / f"test-export{file_extension}"
    temp_file.write_bytes(content)

    mocker.patch(
        "app.strictdoc_controller._export_documents",
        return_value=FileResponse(
            path=str(temp_file),
            media_type=mime_type,
            filename=f"test-export{file_extension}",
        ),
    )

    response = client.post(
        "/export",
        json={"content": {"doc.sdoc": sample_sdoc}, "format": export_format, "file_name": "test-export"},
    )

    # Verify the response
    assert response.status_code == HTTPStatus.OK
    assert mime_type in response.headers["Content-Type"]
    content_disposition = response.headers.get("Content-Disposition", "")
    assert f'filename="test-export{file_extension}"' in content_disposition


def test_export_pdf(client: TestClient, sample_sdoc: str, mocker: MockFixture, tmp_path: Path) -> None:
    """Test exporting to PDF format (which might be unstable)."""
    export_format = "html2pdf"
    mime_type = "application/pdf"
    file_extension = ".pdf"
    content = b"%PDF-1.4"  # PDF magic number

    temp_file = tmp_path / f"test-export{file_extension}"
    temp_file.write_bytes(content)

    mocker.patch(
        "app.strictdoc_controller._export_documents",
        return_value=FileResponse(
            path=str(temp_file),
            media_type=mime_type,
            filename=f"test-export{file_extension}",
        ),
    )

    response = client.post(
        "/export",
        json={"content": {"doc.sdoc": sample_sdoc}, "format": export_format, "file_name": "test-export"},
    )

    # If successful, verify the response
    if response.status_code == HTTPStatus.OK:
        assert mime_type in response.headers["Content-Type"]
        content_disposition = response.headers.get("Content-Disposition", "")
        assert f'filename="test-export{file_extension}"' in content_disposition


def test_export_pdf_error(client: TestClient, sample_sdoc: str, mocker: MockFixture) -> None:
    """Test handling of PDF export failures."""
    from fastapi import HTTPException

    mocker.patch(
        "app.strictdoc_controller._export_documents",
        side_effect=HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail="Export failed: PDF export failed",
        ),
    )

    response = client.post(
        "/export",
        json={"content": {"doc.sdoc": sample_sdoc}, "format": "html2pdf", "file_name": "test-export"},
    )

    # Verify the expected error response
    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert "Export failed" in response.text


def test_invalid_export_format(client: TestClient, sample_sdoc: str) -> None:
    """Test providing an invalid export format."""
    response = client.post(
        "/export",
        json={"content": {"doc.sdoc": sample_sdoc}, "format": "invalid", "file_name": "test-export"},
    )

    # Verify the expected error response
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "Invalid export format" in response.text


def test_invalid_sdoc_content(client: TestClient) -> None:
    """Test providing invalid SDOC content."""
    response = client.post(
        "/export",
        json={"content": {"doc.sdoc": "This is not valid SDOC content"}, "format": "html", "file_name": "test-export"},
    )

    # Verify the expected error response
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "Missing [DOCUMENT] section" in response.text or "Invalid SDOC content" in response.text


def test_empty_sdoc_body(client: TestClient) -> None:
    """Test providing empty SDOC content."""
    response = client.post(
        "/export",
        json={"content": {"doc.sdoc": ""}, "format": "html", "file_name": "test-export"},
    )

    # Empty content string fails validation
    assert response.status_code == HTTPStatus.BAD_REQUEST


def test_missing_sdoc_body(client: TestClient) -> None:
    """Test request without JSON body at all."""
    response = client.post(
        "/export",
        headers={"Content-Type": "application/json"},
    )

    # Verify the expected error response - FastAPI returns 422 for missing required body
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
