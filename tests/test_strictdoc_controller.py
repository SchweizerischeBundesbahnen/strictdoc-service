"""Tests for the StrictDoc controller module."""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.testclient import TestClient
from fastapi import HTTPException


@pytest.fixture
def client() -> TestClient:
    """Create a FastAPI test client."""
    from app.strictdoc_controller import app

    return TestClient(app)


def test_version(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    """Test the version endpoint returns correct information."""
    # Mock strictdoc.__version__ and platform.python_version dynamically
    import strictdoc
    import platform

    expected_strictdoc_version = strictdoc.__version__
    expected_python_version = platform.python_version()

    monkeypatch.setattr("strictdoc.__version__", expected_strictdoc_version)
    monkeypatch.setattr("platform.python_version", lambda: expected_python_version)
    monkeypatch.setenv("STRICTDOC_SERVICE_VERSION", "test1")
    monkeypatch.setenv("STRICTDOC_SERVICE_BUILD_TIMESTAMP", "test2")

    # Make the request
    response = client.get("/version")

    # Verify the response
    assert response.status_code == 200
    result = response.json()
    assert expected_python_version[:4] in result["python"]
    assert result["strictdoc"] == expected_strictdoc_version
    assert "strictdoc_service" in result
    assert "timestamp" in result
    assert "platform" in result


def test_find_exported_file_success() -> None:
    """Test that find_exported_file correctly finds exported files."""
    from app.strictdoc_controller import find_exported_file

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create a test file
        test_file = temp_path / "test.pdf"
        test_file.write_text("test content")

        # Test finding the file
        result = find_exported_file(temp_path, "html2pdf", "pdf")
        assert result == test_file


def test_find_exported_file_not_found() -> None:
    """Test that find_exported_file raises exception when file not found."""
    from app.strictdoc_controller import find_exported_file

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Test with no files
        with pytest.raises(HTTPException) as exc_info:
            find_exported_file(temp_path, "html2pdf", "pdf")

        assert exc_info.value.status_code == 400
        assert "No pdf file found" in str(exc_info.value.detail)


def test_find_exported_file_special_formats() -> None:
    """Test find_exported_file with special formats like reqif-sdoc."""
    from app.strictdoc_controller import find_exported_file

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create test file for reqif-sdoc
        test_file = temp_path / "test.reqif"
        test_file.write_text("test content")

        # Test finding reqif-sdoc file
        result = find_exported_file(temp_path, "reqif-sdoc", "reqif")
        assert result == test_file


@pytest.mark.asyncio
async def test_run_strictdoc_command_success() -> None:
    """Test successful execution of run_strictdoc_command."""
    from app.strictdoc_controller import run_strictdoc_command

    # Mock successful subprocess
    with patch("asyncio.create_subprocess_exec") as mock_subprocess:
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"", b"")
        mock_process.returncode = 0
        mock_subprocess.return_value = mock_process

        # Should not raise any exception
        await run_strictdoc_command(["echo", "test"])

        mock_subprocess.assert_called_once()


@pytest.mark.asyncio
async def test_run_strictdoc_command_failure() -> None:
    """Test failure handling in run_strictdoc_command with stderr."""
    from app.strictdoc_controller import run_strictdoc_command

    # Mock failed subprocess with stderr
    with patch("asyncio.create_subprocess_exec") as mock_subprocess:
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"", b"Error occurred")
        mock_process.returncode = 1
        mock_subprocess.return_value = mock_process

        with pytest.raises(RuntimeError) as exc_info:
            await run_strictdoc_command(["false"])

        assert "StrictDoc command failed" in str(exc_info.value)
        assert "Error occurred" in str(exc_info.value)


@pytest.mark.asyncio
async def test_run_strictdoc_command_stdout_capture() -> None:
    """Test that run_strictdoc_command captures stdout in addition to stderr."""
    from app.strictdoc_controller import run_strictdoc_command

    # Mock failed subprocess with error in stdout (like StrictDoc does)
    with patch("asyncio.create_subprocess_exec") as mock_subprocess:
        mock_process = AsyncMock()
        # StrictDoc writes errors to stdout, not stderr
        mock_process.communicate.return_value = (b"StrictDoc error on stdout", b"")
        mock_process.returncode = 1
        mock_subprocess.return_value = mock_process

        with pytest.raises(RuntimeError) as exc_info:
            await run_strictdoc_command(["strictdoc", "export"])

        # Verify stdout is captured in the error message
        assert "StrictDoc command failed" in str(exc_info.value)
        assert "StrictDoc error on stdout" in str(exc_info.value)


@pytest.mark.asyncio
async def test_run_strictdoc_command_combined_output() -> None:
    """Test that run_strictdoc_command captures both stdout and stderr."""
    from app.strictdoc_controller import run_strictdoc_command

    # Mock failed subprocess with output in both stdout and stderr
    with patch("asyncio.create_subprocess_exec") as mock_subprocess:
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"Output on stdout", b"Error on stderr")
        mock_process.returncode = 1
        mock_subprocess.return_value = mock_process

        with pytest.raises(RuntimeError) as exc_info:
            await run_strictdoc_command(["command"])

        error_message = str(exc_info.value)
        # Verify both stdout and stderr are in the error message
        assert "StrictDoc command failed" in error_message
        assert "Error on stderr" in error_message
        assert "Output on stdout" in error_message


@pytest.mark.asyncio
async def test_run_strictdoc_command_success_with_warnings() -> None:
    """Test that run_strictdoc_command logs warnings when command succeeds but has stderr."""
    from app.strictdoc_controller import run_strictdoc_command

    # Mock successful subprocess with warnings in stderr
    with patch("asyncio.create_subprocess_exec") as mock_subprocess:
        mock_process = AsyncMock()
        # Success (returncode=0) but with warnings in stderr
        mock_process.communicate.return_value = (b"Success output", b"Warning message")
        mock_process.returncode = 0
        mock_subprocess.return_value = mock_process

        # Should not raise exception, just log warnings
        await run_strictdoc_command(["strictdoc", "export"])

        # Verify subprocess was called
        mock_subprocess.assert_called_once()


@pytest.mark.asyncio
async def test_export_bulk_with_action() -> None:
    """Test the export_bulk_with_action function."""
    from app.strictdoc_controller import export_bulk_with_action

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        input_dir = temp_path / "input"
        input_dir.mkdir()
        output_dir = temp_path / "output"

        (input_dir / "input.sdoc").write_text("[DOCUMENT]\nTitle: Test")

        # Mock the strictdoc command
        with patch("app.strictdoc_controller.run_strictdoc_command") as mock_run:
            mock_run.return_value = None

            # Should not raise any exception
            await export_bulk_with_action(input_dir, output_dir, "html")

            # Verify the command was called
            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert "strictdoc" in args
            assert "export" in args
            assert "html" in args


def test_validation_exception_handler_format_error(client: TestClient) -> None:
    """Test that format validation errors return 400 status."""
    response = client.post(
        "/export",
        json={"content": {"doc.sdoc": "[DOCUMENT]\nTitle: Test\n"}, "format": "invalid_format", "file_name": "test"},
    )

    assert response.status_code == 400
    assert "Invalid export format" in response.json()["detail"]


def test_build_single_file_response_html_creates_zip() -> None:
    """Test that _build_single_file_response creates a zip for HTML format."""
    from app.strictdoc_controller import _build_single_file_response

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        output_dir = temp_path / "output"
        output_dir.mkdir()

        # Create some HTML output files
        html_dir = output_dir / "html"
        html_dir.mkdir()
        (html_dir / "index.html").write_text("<html>Test</html>")

        with patch("app.strictdoc_controller.validate_export_paths"), patch("shutil.copy2"):
            response = _build_single_file_response(output_dir, "html", "test-output")

            assert response.media_type == "application/zip"
            assert response.filename == "test-output.zip"


@pytest.mark.asyncio
async def test_export_bulk_to_format_invalid_format() -> None:
    """Test export_bulk_to_format with invalid format."""
    from app.strictdoc_controller import export_bulk_to_format

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        input_dir = temp_path / "input"
        output_dir = temp_path / "output"

        with pytest.raises(HTTPException) as exc_info:
            await export_bulk_to_format(input_dir, output_dir, "invalid_format")

        assert exc_info.value.status_code == 400
        assert "Invalid export format" in str(exc_info.value.detail)


class TestControllerIntegration:
    """Integration tests for controller functions."""

    def test_export_formats_configuration(self) -> None:
        """Test that EXPORT_FORMATS configuration is properly used."""
        from app.strictdoc_controller import EXPORT_FORMATS

        # Verify expected formats exist
        expected_formats = [
            "html",
            "pdf",
            "json",
            "excel",
            "doxygen",
            "rst",
            "sdoc",
            "spdx",
        ]
        for fmt in expected_formats:
            if fmt == "pdf":
                fmt = "html2pdf"  # PDF is exported as html2pdf
            assert fmt in EXPORT_FORMATS or fmt == "pdf"

        # Verify each format has required keys
        for fmt, config in EXPORT_FORMATS.items():
            assert "extension" in config
            assert "mime_type" in config
            assert isinstance(config["extension"], str)
            assert isinstance(config["mime_type"], str)

    def test_sanitization_integration(self) -> None:
        """Test that sanitization functions are properly integrated."""
        from app.strictdoc_controller import app
        from app.sanitization import sanitize_for_logging
        from pathvalidate import sanitize_filename

        # Test that functions are available and working
        assert sanitize_filename("../test.txt") == "..test.txt"
        assert sanitize_for_logging("test\nlog") == "testlog"

        # Verify app can be created (imports work)
        assert app is not None
        assert hasattr(app, "routes")


@pytest.mark.asyncio
async def test_path_validation_with_invalid_export_file() -> None:
    """Test that export path validation correctly prevents path traversal attacks."""
    from app.strictdoc_controller import export_documents, StrictdocExportParams
    from http import HTTPStatus

    # Return a path that is definitely outside the output directory
    malicious_path = Path("/etc/passwd")

    with patch("app.strictdoc_controller.export_bulk_to_format"), patch("app.strictdoc_controller.find_exported_file", return_value=malicious_path), patch("shutil.copy2"), pytest.raises(HTTPException) as excinfo:
        await export_documents(
            export_params=StrictdocExportParams(
                content={"doc.sdoc": "[DOCUMENT]\nTITLE: Test\n"},
                format="sdoc",
                file_name="test_document",
            )
        )

    assert excinfo.value.status_code in [HTTPStatus.BAD_REQUEST, HTTPStatus.INTERNAL_SERVER_ERROR]
    assert "Invalid" in excinfo.value.detail


def test_path_validation_with_invalid_destination_path() -> None:
    """Test that destination path validation correctly prevents path traversal attacks."""
    from app.strictdoc_controller import validate_export_paths
    from http import HTTPStatus

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir).resolve()
        output_dir = temp_dir_path / "output"
        output_dir.mkdir()

        valid_export_file = output_dir / "export.sdoc"
        valid_export_file.write_text("content")

        # Malicious destination: outside temp dir
        malicious_dest = Path("/etc/passwd")

        with pytest.raises(HTTPException) as excinfo:
            validate_export_paths(malicious_dest, temp_dir_path, valid_export_file, output_dir)

        assert excinfo.value.status_code == HTTPStatus.BAD_REQUEST
        assert "Invalid file path detected" in excinfo.value.detail


@pytest.mark.asyncio
async def test_sanitize_filename_is_called() -> None:
    """Test that sanitize_filename is called for path components."""
    from app.strictdoc_controller import export_documents, StrictdocExportParams

    with (
        patch("app.strictdoc_controller.export_bulk_to_format"),
        patch("app.strictdoc_controller.find_exported_file", return_value=Path(tempfile.gettempdir()) / "safe.sdoc"),
        patch("app.strictdoc_controller.validate_export_paths"),
        patch("shutil.copy2"),
        patch("app.strictdoc_controller.FileResponse"),
        patch("app.strictdoc_controller.sanitize_filename") as mock_sanitize,
    ):
        mock_sanitize.return_value = "safe_filename"

        await export_documents(
            export_params=StrictdocExportParams(
                content={"doc.sdoc": "[DOCUMENT]\nTITLE: Test\n"},
                format="sdoc",
                file_name="../../../etc/passwd",
            )
        )

        # Verify sanitize_filename was called with the malicious file_name
        mock_sanitize.assert_any_call("../../../etc/passwd", replacement_text="_")


@pytest.mark.asyncio
async def test_successful_validation_with_safe_paths() -> None:
    """Test that path validation succeeds with safe paths."""
    from app.strictdoc_controller import export_documents, StrictdocExportParams

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        output_file = temp_dir_path / "test.sdoc"
        # Create the export file so stat() works
        output_file.write_text("test content")

        with (
            patch("app.strictdoc_controller.export_bulk_to_format"),
            patch("app.strictdoc_controller.find_exported_file", return_value=output_file),
            patch("app.strictdoc_controller.validate_export_paths") as mock_validate,
            patch("shutil.copy2") as mock_copy,
            patch("app.strictdoc_controller.FileResponse") as mock_response,
        ):
            mock_validate.return_value = None

            await export_documents(
                export_params=StrictdocExportParams(
                    content={"doc.sdoc": "[DOCUMENT]\nTITLE: Test\n"},
                    format="sdoc",
                    file_name="safe_document",
                )
            )

            mock_validate.assert_called_once()
            mock_copy.assert_called_once()
            mock_response.assert_called_once()


@pytest.mark.asyncio
async def test_path_normalization() -> None:
    """Test that paths are properly normalized and validated."""
    from app.strictdoc_controller import export_documents, StrictdocExportParams

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        output_file = temp_dir_path / "test.sdoc"

        with (
            patch("app.strictdoc_controller.export_bulk_to_format"),
            patch("app.strictdoc_controller.find_exported_file", return_value=output_file),
            patch("app.strictdoc_controller.validate_export_paths"),
            patch("shutil.copy2") as mock_copy,
            patch("app.strictdoc_controller.FileResponse") as mock_response,
        ):
            await export_documents(
                export_params=StrictdocExportParams(
                    content={"doc.sdoc": "[DOCUMENT]\nTITLE: Test\n"},
                    format="sdoc",
                    file_name="output_file",
                )
            )

            mock_copy.assert_called_once()
            mock_response.assert_called_once()
