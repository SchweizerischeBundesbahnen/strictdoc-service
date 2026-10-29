"""Unit tests for the export functionality of StrictDoc service."""

from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient
from pytest_mock import MockFixture

from app.strictdoc_controller import __version_key_to_header_key


@pytest.mark.parametrize(
    "export_format",
    ["html", "json", "excel", "reqif-sdoc", "reqifz-sdoc", "rst", "sdoc", "html2pdf"],
)
def test_export_formats_return_zip(
    client: TestClient,
    sample_sdoc: str,
    export_format: str,
    mocker: MockFixture,
) -> None:
    """Test that every export format is returned as a ZIP archive."""
    mocker.patch(
        "app.strictdoc_controller.export_bulk_to_format",
        return_value=None,
    )

    response = client.post(
        "/export",
        json={"content": {"doc.sdoc": sample_sdoc}, "format": export_format, "file_name": "test-export"},
    )

    assert response.status_code == HTTPStatus.OK
    assert "application/zip" in response.headers["Content-Type"]
    content_disposition = response.headers.get("Content-Disposition", "")
    assert 'filename="test-export.zip"' in content_disposition


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


def test_multi_doc_export_returns_zip(
    client: TestClient,
    sample_sdoc: str,
    mocker: MockFixture,
) -> None:
    """Test that exporting multiple documents returns a ZIP archive (bulk-ZIP branch)."""
    mocker.patch(
        "app.strictdoc_controller.export_bulk_to_format",
        return_value=None,
    )

    response = client.post(
        "/export",
        json={
            "content": {
                "doc_a.sdoc": sample_sdoc,
                "doc_b.sdoc": sample_sdoc,
            },
            "format": "sdoc",
            "file_name": "test-multi-export",
        },
    )

    assert response.status_code == HTTPStatus.OK
    assert "application/zip" in response.headers["Content-Type"]
    content_disposition = response.headers.get("Content-Disposition", "")
    assert 'filename="test-multi-export.zip"' in content_disposition


def test_multi_doc_filename_collision_rejected(
    client: TestClient,
    sample_sdoc: str,
) -> None:
    """Test that multi-doc export is rejected when two names collide after sanitization.

    'a/b.sdoc' and 'a_b.sdoc' both sanitize to 'a_b.sdoc', triggering the
    collision guard in sanitize_sdoc_content_filenames.
    """
    response = client.post(
        "/export",
        json={
            "content": {
                "a/b.sdoc": sample_sdoc,
                "a_b.sdoc": sample_sdoc,
            },
            "format": "sdoc",
            "file_name": "test-export",
        },
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "Multi-export filename collision" in response.text


def test_single_doc_export_includes_version_headers(
    client: TestClient,
    sample_sdoc: str,
    mocker: MockFixture,
) -> None:
    """Test that a single-document export response includes version info headers."""
    mocker.patch(
        "app.strictdoc_controller.export_bulk_to_format",
        return_value=None,
    )

    expected_version = client.get("/version").json()

    response = client.post(
        "/export",
        json={"content": {"doc.sdoc": sample_sdoc}, "format": "html", "file_name": "test-export"},
    )

    assert response.status_code == HTTPStatus.OK
    for key, value in expected_version.items():
        assert response.headers[__version_key_to_header_key(key)] == value


def test_multi_doc_export_includes_version_headers(
    client: TestClient,
    sample_sdoc: str,
    mocker: MockFixture,
) -> None:
    """Test that a bulk (multi-document) export response includes version info headers."""
    mocker.patch(
        "app.strictdoc_controller.export_bulk_to_format",
        return_value=None,
    )

    expected_version = client.get("/version").json()

    response = client.post(
        "/export",
        json={
            "content": {
                "doc_a.sdoc": sample_sdoc,
                "doc_b.sdoc": sample_sdoc,
            },
            "format": "sdoc",
            "file_name": "test-multi-export",
        },
    )

    assert response.status_code == HTTPStatus.OK
    for key, value in expected_version.items():
        assert response.headers[__version_key_to_header_key(key)] == value
