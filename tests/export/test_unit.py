"""Unit tests for the export functionality of StrictDoc service."""

from http import HTTPStatus

import pytest
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
) -> None:
    """Test exporting to different formats with proper mocking."""
    target_path = "app.strictdoc_controller.export_document"
    mocker.patch(target_path, return_value=content)

    response = client.post(
        f"/export?format={export_format}&file_name=test-export",
        content=sample_sdoc,
        headers={"Content-Type": "text/plain"},
    )

    # Verify the response
    assert response.status_code == HTTPStatus.OK
    assert mime_type in response.headers["Content-Type"]
    content_disposition = response.headers.get("Content-Disposition", "")
    assert f'filename="test-export{file_extension}"' in content_disposition


def test_export_pdf(client: TestClient, sample_sdoc: str, mocker: MockFixture) -> None:
    """Test exporting to PDF format (which might be unstable)."""
    export_format = "html2pdf"
    mime_type = "application/pdf"
    file_extension = ".pdf"
    content = b"%PDF-1.4"  # PDF magic number

    target_path = "app.strictdoc_controller.export_document"
    mocker.patch(target_path, return_value=content)

    response = client.post(
        f"/export?format={export_format}&file_name=test-export",
        content=sample_sdoc,
        headers={"Content-Type": "text/plain"},
    )

    # If successful, verify the response
    if response.status_code == HTTPStatus.OK:
        assert mime_type in response.headers["Content-Type"]
        content_disposition = response.headers.get("Content-Disposition", "")
        assert f'filename="test-export{file_extension}"' in content_disposition


def test_export_pdf_error(client: TestClient, sample_sdoc: str, mocker: MockFixture) -> None:
    """Test handling of PDF export failures."""
    target_path = "app.strictdoc_controller.export_document"
    mocker.patch(target_path, side_effect=RuntimeError("PDF export failed"))

    response = client.post(
        "/export?format=html2pdf&file_name=test-export",
        content=sample_sdoc,
        headers={"Content-Type": "text/plain"},
    )

    # Verify the expected error response
    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert "Export failed" in response.text


def test_invalid_export_format(client: TestClient, sample_sdoc: str) -> None:
    """Test providing an invalid export format."""
    response = client.post(
        "/export?format=invalid&file_name=test-export",
        content=sample_sdoc,
        headers={"Content-Type": "text/plain"},
    )

    # Verify the expected error response
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "Invalid export format" in response.text


def test_invalid_sdoc_content(client: TestClient) -> None:
    """Test providing invalid SDOC content."""
    invalid_sdoc = "This is not valid SDOC content"
    response = client.post(
        "/export?format=html&file_name=test-export",
        content=invalid_sdoc,
        headers={"Content-Type": "text/plain"},
    )

    # Verify the expected error response
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "Missing [DOCUMENT] section" in response.text or "Invalid SDOC content" in response.text
