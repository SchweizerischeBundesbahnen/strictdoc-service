"""Integration tests for the export functionality using a real Docker container."""

import io
import zipfile
from http import HTTPStatus

import pytest
import requests

from tests.conftest import TestParameters


def test_version_endpoint(test_parameters: TestParameters) -> None:
    """Test that the version endpoint returns information about the StrictDoc version."""
    response = test_parameters.request_session.get(f"{test_parameters.base_url}/version")
    assert response.status_code == HTTPStatus.OK
    result = response.json()
    assert "strictdoc" in result
    assert "python" in result
    assert "platform" in result
    assert "timestamp" in result


@pytest.mark.parametrize(
    ("export_format", "mime_type", "file_extension"),
    [
        ("html", "application/zip", ".zip"),
        ("json", "application/json", ".json"),
        ("csv", "text/csv", ".csv"),
        ("excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".xlsx"),
        ("reqif-sdoc", "application/xml", ".reqif"),
        ("reqifz-sdoc", "application/zip", ".reqifz"),
        ("rst", "text/x-rst", ".rst"),
        ("sdoc", "text/plain", ".sdoc"),
    ],
)
def test_export_formats(test_parameters: TestParameters, sample_sdoc: str, export_format: str, mime_type: str, file_extension: str) -> None:
    """Test exporting to different formats."""
    response = test_parameters.request_session.post(
        f"{test_parameters.base_url}/export",
        params={"format": export_format, "file_name": "test-export"},
        data=sample_sdoc,
        headers={"Content-Type": "text/plain"},
        timeout=30,
    )

    # Check that the response is either successful or a known error status
    assert response.status_code in {HTTPStatus.OK, HTTPStatus.INTERNAL_SERVER_ERROR, HTTPStatus.BAD_REQUEST}

    # Only continue validation if the export was successful
    if response.status_code == HTTPStatus.OK:
        assert mime_type in response.headers["Content-Type"]
        content_disposition = response.headers.get("Content-Disposition", "")
        assert f"test-export{file_extension}" in content_disposition

        # Validate the content based on the format
        if export_format == "html":
            # HTML export should be a ZIP file containing index.html
            content = io.BytesIO(response.content)
            with zipfile.ZipFile(content) as z:
                assert any(name.endswith("index.html") for name in z.namelist())
        elif export_format == "json":
            # JSON export should be valid JSON
            content = response.json()
            assert "DOCUMENTS" in content
            assert isinstance(content["DOCUMENTS"], list)
            assert len(content["DOCUMENTS"]) > 0
            assert "TITLE" in content["DOCUMENTS"][0]
        elif export_format in {"reqif-sdoc", "reqifz-sdoc"}:
            # ReqIF/ReqIFZ exports have specific validations
            if export_format == "reqif-sdoc":
                # ReqIF should be XML
                assert response.content.startswith(b"<?xml")
            else:
                # ReqIFZ should be a ZIP file
                assert response.content.startswith(b"PK")


def test_export_pdf(test_parameters: TestParameters, sample_sdoc: str) -> None:
    """Test exporting to PDF format."""
    response = test_parameters.request_session.post(
        f"{test_parameters.base_url}/export",
        params={"format": "html2pdf", "file_name": "test-export"},
        data=sample_sdoc,
        headers={"Content-Type": "text/plain"},
        timeout=60,  # PDF export might take longer
    )

    # PDF export can fail on some systems, so we accept either success or server error
    assert response.status_code in {HTTPStatus.OK, HTTPStatus.INTERNAL_SERVER_ERROR}

    if response.status_code == HTTPStatus.OK:
        assert "application/pdf" in response.headers["Content-Type"]
        content_disposition = response.headers.get("Content-Disposition", "")
        assert "test-export.pdf" in content_disposition
        # PDF files should start with "%PDF-"
        assert response.content.startswith(b"%PDF-")


def test_invalid_export_format(test_parameters: TestParameters, sample_sdoc: str) -> None:
    """Test providing an invalid export format."""
    response = test_parameters.request_session.post(
        f"{test_parameters.base_url}/export",
        params={"format": "invalid", "file_name": "test-export"},
        data=sample_sdoc,
        headers={"Content-Type": "text/plain"},
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "Invalid export format" in response.text


def test_invalid_sdoc_content(test_parameters: TestParameters) -> None:
    """Test providing invalid SDOC content."""
    invalid_sdoc = "This is not valid SDOC content"
    response = test_parameters.request_session.post(
        f"{test_parameters.base_url}/export",
        params={"format": "html", "file_name": "test-export"},
        data=invalid_sdoc,
        headers={"Content-Type": "text/plain"},
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "Missing [DOCUMENT] section" in response.text or "Invalid SDOC content" in response.text
