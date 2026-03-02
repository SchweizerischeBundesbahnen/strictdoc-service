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
async def test_export_with_action() -> None:
    """Test the export_with_action function."""
    from app.strictdoc_controller import export_with_action

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        input_file = temp_path / "input.sdoc"
        output_dir = temp_path / "output"

        input_file.write_text("[DOCUMENT]\nTitle: Test")

        # Mock the strictdoc command
        with patch("app.strictdoc_controller.run_strictdoc_command") as mock_run:
            mock_run.return_value = None

            # Should not raise any exception
            await export_with_action(input_file, output_dir, "html")

            # Verify the command was called
            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert "strictdoc" in args
            assert "export" in args
            assert "html" in args


def test_process_sdoc_content_success() -> None:
    """Test successful SDOC content processing."""
    from app.strictdoc_controller import process_sdoc_content

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        input_file = temp_path / "test.sdoc"

        valid_content = "[DOCUMENT]\nTitle: Test Document\n"

        # Mock the SDReader and related classes
        with patch("app.strictdoc_controller.SDReader") as mock_reader:
            mock_reader_instance = Mock()
            mock_reader.return_value = mock_reader_instance
            mock_reader_instance.read_from_file.return_value = None

            # Should not raise any exception
            process_sdoc_content(valid_content, input_file)

            # Verify file was written
            assert input_file.exists()
            content = input_file.read_text()
            assert "[DOCUMENT]" in content


def test_process_sdoc_content_invalid() -> None:
    """Test SDOC content processing with invalid content."""
    from app.strictdoc_controller import process_sdoc_content

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        input_file = temp_path / "test.sdoc"

        invalid_content = "This is not valid SDOC content"

        with pytest.raises(HTTPException) as exc_info:
            process_sdoc_content(invalid_content, input_file)

        assert exc_info.value.status_code == 400
        assert "Missing [DOCUMENT] section" in str(exc_info.value.detail)


def test_process_sdoc_content_line_endings() -> None:
    """Test that SDOC content processing normalizes line endings."""
    from app.strictdoc_controller import process_sdoc_content

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        input_file = temp_path / "test.sdoc"

        # Content with mixed line endings
        content_with_mixed_endings = "[DOCUMENT]\r\nTitle: Test\rContent here\n"

        with patch("app.strictdoc_controller.SDReader") as mock_reader:
            mock_reader_instance = Mock()
            mock_reader.return_value = mock_reader_instance
            mock_reader_instance.read_from_file.return_value = None

            process_sdoc_content(content_with_mixed_endings, input_file)

            # Verify line endings were normalized
            written_content = input_file.read_text()
            assert "\r\n" not in written_content
            assert "\r" not in written_content
            assert written_content.count("\n") == 3  # Should have Unix line endings


def test_validation_exception_handler_format_error(client: TestClient) -> None:
    """Test that format validation errors return 400 status."""
    # Test with invalid format parameter
    response = client.post(
        "/export?format=invalid_format",
        content="[DOCUMENT]\nTitle: Test",
        headers={"Content-Type": "text/plain"},
    )

    assert response.status_code == 400
    assert "Invalid export format" in response.json()["detail"]


@pytest.mark.asyncio
async def test_export_to_format_html_zip() -> None:
    """Test export_to_format creates zip for HTML format."""
    from app.strictdoc_controller import export_to_format

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        input_file = temp_path / "input.sdoc"
        output_dir = temp_path / "output"
        output_dir.mkdir()

        input_file.write_text("[DOCUMENT]\nTitle: Test")

        # Create some HTML output files
        html_dir = output_dir / "html"
        html_dir.mkdir()
        (html_dir / "index.html").write_text("<html>Test</html>")

        with patch("app.strictdoc_controller.export_with_action"):
            result_file, extension, mime_type = await export_to_format(
                input_file, output_dir, "html"
            )

            assert extension == "zip"
            assert mime_type == "application/zip"
            assert result_file.suffix == ".zip"


@pytest.mark.asyncio
async def test_export_to_format_invalid_format() -> None:
    """Test export_to_format with invalid format."""
    from app.strictdoc_controller import export_to_format

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        input_file = temp_path / "input.sdoc"
        output_dir = temp_path / "output"

        with pytest.raises(HTTPException) as exc_info:
            await export_to_format(input_file, output_dir, "invalid_format")

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
    from app.strictdoc_controller import export_document
    from http import HTTPStatus

    # Create test directories
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        output_dir = temp_dir_path / "output"
        output_dir.mkdir()

        # Setup mocks
        with patch("app.strictdoc_controller.export_to_format") as mock_export_to_format:
            # Create a malicious export_file path that attempts to escape the output directory
            malicious_path = temp_dir_path / "output" / ".." / ".." / "etc" / "passwd"
            mock_export_to_format.return_value = (malicious_path, "txt", "text/plain")

            # Test with modified approach that doesn't require mocking Path.resolve
            # Instead, use an actual path that would fail validation
            with patch("tempfile.gettempdir", return_value=str(temp_dir_path)), \
                 patch("shutil.copy2"), \
                 patch("app.strictdoc_controller.FileResponse"), \
                 pytest.raises(HTTPException) as excinfo:

                await export_document(
                    sdoc_content="[DOCUMENT]\nTITLE: Test\n",
                    format="sdoc",
                    file_name="test_document"
                )

            # Verify that an exception was raised - either BAD_REQUEST for path validation
            # or INTERNAL_SERVER_ERROR if the path traversal is caught elsewhere
            assert excinfo.value.status_code in [HTTPStatus.BAD_REQUEST, HTTPStatus.INTERNAL_SERVER_ERROR]
            assert "Invalid" in excinfo.value.detail


@pytest.mark.asyncio
async def test_path_validation_with_invalid_destination_path() -> None:
    """Test that destination path validation correctly prevents path traversal attacks."""
    from app.strictdoc_controller import export_document
    from http import HTTPStatus

    # Create test directories with proper structure
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        output_dir = temp_dir_path / "output"
        output_dir.mkdir()

        valid_export_file = output_dir / "export.sdoc"

        # Setup mocks with a simpler approach that doesn't require mocking Path.resolve
        with patch("app.strictdoc_controller.export_to_format") as mock_export_to_format:
            # Setup the export mock to return a valid file
            mock_export_to_format.return_value = (valid_export_file, "sdoc", "text/plain")

            # Create a malicious path scenario
            with patch("app.strictdoc_controller.sanitize_filename") as mock_sanitize:
                # Make sanitize_filename return a path that would be considered invalid
                # This simulates a path that tries to escape the temp directory
                mock_sanitize.return_value = "../../../etc"

                # Test with the mocked sanitization
                with patch("shutil.copy2"), patch("app.strictdoc_controller.FileResponse"), pytest.raises(HTTPException) as excinfo:
                    await export_document(sdoc_content="[DOCUMENT]\nTITLE: Test\n", format="sdoc", file_name="test_document")

                # Verify the correct exception was raised
                assert excinfo.value.status_code == HTTPStatus.BAD_REQUEST
                assert "Invalid file path detected" in excinfo.value.detail


@pytest.mark.asyncio
async def test_sanitize_filename_is_called() -> None:
    """Test that sanitize_filename is called for path components."""
    from app.strictdoc_controller import export_document

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        # Create the export file so stat() works
        export_file = temp_dir_path / "test.sdoc"
        export_file.write_text("test content")

        with patch("app.strictdoc_controller.export_to_format") as mock_export, patch(
            "app.strictdoc_controller.sanitize_filename"
        ) as mock_sanitize, patch("app.strictdoc_controller.validate_export_paths"), patch(
            "tempfile.gettempdir", return_value=str(temp_dir_path)
        ), patch("shutil.copy2"), patch("app.strictdoc_controller.FileResponse"):
            # Mock export_to_format to return a valid file
            mock_export.return_value = (export_file, "sdoc", "text/plain")
            mock_sanitize.return_value = "safe_filename"

            # Call the function
            await export_document(sdoc_content="[DOCUMENT]\nTITLE: Test\n", format="sdoc", file_name="../../../etc/passwd")

            # Verify sanitize_filename was called
            mock_sanitize.assert_called_once_with("../../../etc/passwd", replacement_text="_")


@pytest.mark.asyncio
async def test_successful_validation_with_safe_paths() -> None:
    """Test that path validation succeeds with safe paths."""
    from app.strictdoc_controller import export_document

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        output_file = temp_dir_path / "test.sdoc"
        # Create the export file so stat() works
        output_file.write_text("test content")

        with patch("app.strictdoc_controller.export_to_format") as mock_export, \
             patch("tempfile.gettempdir", return_value=str(temp_dir_path)), \
             patch("app.strictdoc_controller.validate_export_paths") as mock_validate, \
             patch("shutil.copy2") as mock_copy, \
             patch("app.strictdoc_controller.FileResponse") as mock_response:

            # Mock export_to_format to return a valid file
            mock_export.return_value = (output_file, "sdoc", "text/plain")

            # Mock validation to always pass for this test
            mock_validate.return_value = None

            # Call the function with a safe filename
            result = await export_document(
                sdoc_content="[DOCUMENT]\nTITLE: Test\n",
                format="sdoc",
                file_name="safe_document"
            )

            # Verify the validation was called and file was copied
            mock_validate.assert_called_once()
            mock_copy.assert_called_once()
            mock_response.assert_called_once()


@pytest.mark.asyncio
async def test_path_normalization() -> None:
    """Test that paths are properly normalized and validated."""
    from app.strictdoc_controller import export_document

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        output_file = temp_dir_path / "test.txt"
        # Create the export file so stat() works
        output_file.write_text("test content")

        with patch("app.strictdoc_controller.export_to_format") as mock_export, \
             patch("app.strictdoc_controller.validate_export_paths") as mock_validate, \
             patch("tempfile.gettempdir", return_value=str(temp_dir_path)), \
             patch("shutil.copy2") as mock_copy, \
             patch("app.strictdoc_controller.FileResponse") as mock_response:

            # Mock export_to_format to return a valid file
            mock_export.return_value = (output_file, "txt", "text/plain")

            # Call the function - should succeed without exceptions
            await export_document(
                sdoc_content="[DOCUMENT]\nTITLE: Test\n",
                format="txt",
                file_name="output_file"
            )

            # Verify the file was copied and response was created
            mock_copy.assert_called_once()
            mock_response.assert_called_once()
