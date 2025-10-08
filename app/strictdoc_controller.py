"""StrictDoc service controller module."""

import asyncio
import logging
import os
import platform
import re
import shutil
import sys
import tempfile
from collections.abc import Awaitable, Callable
from http import HTTPStatus
from pathlib import Path

import uvicorn
from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from pathvalidate import sanitize_filename
from pydantic import BaseModel
from starlette.background import BackgroundTask
from starlette.requests import Request
from starlette.responses import Response

# Import StrictDoc version directly
from strictdoc import __version__ as strictdoc_version  # type: ignore[import]
from strictdoc.backend.sdoc.pickle_cache import PickleCache  # type: ignore[import]
from strictdoc.backend.sdoc.reader import SDReader  # type: ignore[import]
from strictdoc.cli.main import ProjectConfig  # type: ignore[import]
from strictdoc.core.environment import SDocRuntimeEnvironment  # type: ignore[import]

from app.sanitization import normalize_line_endings, sanitize_for_logging

# Create a custom logger
logger = logging.getLogger(__name__)

# Define supported export formats with their file extensions and mime types
EXPORT_FORMATS = {
    "doxygen": {"extension": "xml", "mime_type": "application/xml"},
    "excel": {"extension": "xlsx", "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
    "html": {"extension": "zip", "mime_type": "application/zip"},
    "html2pdf": {"extension": "pdf", "mime_type": "application/pdf"},
    "json": {"extension": "json", "mime_type": "application/json"},
    "reqif-sdoc": {"extension": "reqif", "mime_type": "application/xml"},
    "reqifz-sdoc": {"extension": "reqifz", "mime_type": "application/zip"},
    "rst": {"extension": "rst", "mime_type": "text/x-rst"},
    "sdoc": {"extension": "sdoc", "mime_type": "text/plain"},
    "spdx": {"extension": "spdx", "mime_type": "text/plain"},
}

app = FastAPI(
    title="StrictDoc Service API",
    description="API for StrictDoc document generation and export",
    version="1.0.0",
)


# Add exception handler for FastAPI's validation errors
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Convert 422 validation errors to 400 Bad Request for format validation.

    Args:
        request: The request that caused the exception
        exc: The validation error

    Returns:
        JSONResponse: The error response

    """
    MIN_LOC_LENGTH = 2
    error_details = []
    format_validation_error = False

    # Check each error to see if it's related to format parameter
    for error in exc.errors():
        # Format error handling - if format is in the error path, it's a format error
        if error.get("loc") and len(error["loc"]) >= MIN_LOC_LENGTH and error["loc"][0] == "query" and error["loc"][1] == "format":
            format_validation_error = True
            break
        error_details.append(error)

    # If it's a format validation error, return a 400 Bad Request
    if format_validation_error:
        return JSONResponse(status_code=HTTPStatus.BAD_REQUEST, content={"detail": f"Invalid export format. Must be one of: {', '.join(EXPORT_FORMATS.keys())}"})

    # For other validation errors, use standard 422 response
    return JSONResponse(status_code=HTTPStatus.UNPROCESSABLE_ENTITY, content={"detail": error_details if error_details else exc.errors()})


# Monkey patch PickleCache.get_cached_file_path to handle Path objects
original_get_cached_file_path = PickleCache.get_cached_file_path


def patched_get_cached_file_path(file_path: str | Path, project_config: ProjectConfig, content_kind: str) -> str:
    """Get the cached file path, handling Path objects.

    This is a monkey-patched version of PickleCache.get_cached_file_path that
    handles Path objects correctly.

    Args:
        file_path: The path to the file, as string or Path
        project_config: The project configuration
        content_kind: The kind of content being cached

    Returns:
        str: The path to the cached file

    """
    # Convert file_path to str if it's a Path
    if hasattr(file_path, "absolute"):  # It's likely a Path object
        file_path = str(file_path.absolute())
    return original_get_cached_file_path(file_path, project_config, content_kind)


# Apply the monkey patch
PickleCache.get_cached_file_path = patched_get_cached_file_path


# Request and response models
class VersionInfo(BaseModel):
    """Version information response model.

    Contains version information about Python, StrictDoc, and the platform.
    """

    python: str
    strictdoc: str
    platform: str
    timestamp: str
    strictdoc_service: str | None = None


class ErrorResponse(BaseModel):
    """Error response model.

    Contains error information and optional details.
    """

    error: str
    details: str | None = None


# Middleware for logging
@app.middleware("http")
async def log_requests(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    """Log incoming requests and their responses.

    Args:
        request: The incoming request
        call_next: The next middleware in the chain

    Returns:
        Response: The response from the next middleware

    """
    logger.info("Request: %s %s", request.method, request.url.path)
    response = await call_next(request)
    logger.info("Response: %s %s, Status: %s", request.method, request.url.path, response.status_code)
    return response


@app.get("/version")
async def get_version() -> VersionInfo:
    """Get version information about the service and its dependencies.

    Returns:
        VersionInfo: Version information about Python, StrictDoc, and the platform.

    """
    service_version = os.getenv("STRICTDOC_SERVICE_VERSION", "dev")
    python_version = sys.version.split()[0]
    platform_info = platform.platform()

    # Use the build timestamp from the Docker image build time
    timestamp = ""
    timestamp_file = Path("/opt/strictdoc/.build_timestamp")
    if timestamp_file.exists():
        try:
            timestamp = timestamp_file.read_text().strip()
        except Exception as e:
            logging.warning(f"Failed to read build timestamp: {e}")

    return VersionInfo(python=python_version, strictdoc=strictdoc_version, platform=platform_info, timestamp=timestamp, strictdoc_service=service_version)


def process_sdoc_content(content: str, input_file: Path) -> None:
    """Process and validate SDOC content.

    Args:
        content: The SDOC content to validate
        input_file: Path to the input file

    Raises:
        HTTPException: If the content is invalid

    """
    # Normalize line endings to Unix style
    content = normalize_line_endings(content)

    # Very basic validation of SDOC content
    if "[DOCUMENT]" not in content:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="Missing [DOCUMENT] section in SDOC content")

    # Write content to file - input_file is created within the controlled temp directory
    with input_file.open("w", encoding="utf-8") as f:
        f.write(content)

    # Parse the document using StrictDoc's reader to validate
    try:
        reader = SDReader()
        # Create environment and config with explicit paths
        input_parent = str(input_file.parent)
        environment = SDocRuntimeEnvironment(input_parent)
        project_config = ProjectConfig(
            environment=environment,
            project_title=ProjectConfig.DEFAULT_PROJECT_TITLE,
            dir_for_sdoc_assets=input_parent,
            dir_for_sdoc_cache=str(Path(input_parent) / "cache"),
            project_features=ProjectConfig.DEFAULT_FEATURES,
            server_host=ProjectConfig.DEFAULT_SERVER_HOST,
            server_port=ProjectConfig.DEFAULT_SERVER_PORT,
            include_doc_paths=[],
            exclude_doc_paths=[],
            source_root_path=None,
            include_source_paths=[],
            exclude_source_paths=[],
            test_report_root_dict={},
            source_nodes=[],
            html2pdf_strict=False,
            html2pdf_template=None,
            bundle_document_version=None,
            bundle_document_date=None,
            traceability_matrix_relation_columns=None,
            reqif_profile="",
            reqif_multiline_is_xhtml=False,
            reqif_enable_mid=False,
            reqif_import_markup=None,
            config_last_update=None,
            chromedriver=None,
            section_behavior={},
            statistics_generator=None,
        )

        # Monkey patch the config to avoid TypeError in pickle_cache.py
        # PickleCache uses project_config.output_dir + full_path_to_file
        project_config.output_dir = input_parent + "/"

        reader.read_from_file(str(input_file), project_config)
    except Exception as e:
        # Clean up and raise a more user-friendly error
        error_msg = str(e)
        # Extract the most relevant part of the error message
        if "TextXSyntaxError" in error_msg:
            # Extract the error location and message
            match = re.match(r"^([^:]{1,256}):(\d{1,6}):(\d{1,6}):(.*)$", error_msg, re.DOTALL)
            if match:
                _, line, col, message = match.groups()
                error_msg = f"Syntax error in SDOC document at line {line}, column {col}: {message.strip()}"
            else:
                error_msg = "Syntax error in SDOC document. Please check your document structure."

        logging.exception("SDOC parsing error: %s", error_msg)
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=error_msg) from e


async def run_strictdoc_command(cmd: list[str]) -> None:
    """Run a StrictDoc command asynchronously.

    Args:
        cmd: The command to run as a list of strings

    Raises:
        RuntimeError: If the command fails or returns non-zero exit code
    """
    sanitized_cmd = [sanitize_for_logging(arg) for arg in cmd]
    logging.info("Running command: %s", " ".join(sanitized_cmd))

    try:
        # Use asyncio.create_subprocess_exec for non-blocking execution
        process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)

        _, stderr = await process.communicate()

        if process.returncode != 0:
            stderr_text = stderr.decode("utf-8") if stderr else "Unknown error"
            logging.error("StrictDoc CLI error: %s", stderr_text)
            raise RuntimeError(f"StrictDoc command failed: {stderr_text}")

        if stderr:
            stderr_text = stderr.decode("utf-8")
            logging.warning("StrictDoc CLI warnings: %s", stderr_text)

    except Exception as e:
        logging.exception("Command execution failed: %s", str(e))
        raise RuntimeError(f"Command execution failed: {e!s}") from e


async def export_with_action(input_file: Path, output_dir: Path, format_name: str) -> None:
    """Export a document using ExportAction.

    Args:
        input_file: Path to input .sdoc file
        output_dir: Path to output directory
        format_name: Export format name

    """
    # Create output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        cmd = ["strictdoc", "export", "--formats", format_name, "--output-dir", str(output_dir), str(input_file)]
        await run_strictdoc_command(cmd)
    except Exception as e:
        logging.exception("Export failed: %s", str(e))
        raise RuntimeError(f"Export failed: {e!s}") from e


async def export_to_format(input_file: Path, output_dir: Path, export_format: str) -> tuple[Path, str, str]:
    """Export SDOC to specified format.

    Args:
        input_file: Path to input file
        output_dir: Path to output directory
        export_format: Format to export to

    Returns:
        Tuple of (file_path, extension, mime_type)

    Raises:
        HTTPException: If exported file not found or other error

    """
    # Check if export_format is in the list of supported formats
    if export_format not in EXPORT_FORMATS:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=f"Invalid export format: {export_format}")

    # Get format-specific configuration from EXPORT_FORMATS
    extension = EXPORT_FORMATS[export_format]["extension"]
    mime_type = EXPORT_FORMATS[export_format]["mime_type"]

    # Export the document
    try:
        # Call export_with_action for the actual export
        await export_with_action(input_file, output_dir, export_format)
    except Exception as e:
        logging.exception("Export failed: %s", str(e))
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=f"Export to {export_format} failed: {e!s}") from e

    # For HTML, we need to zip the output directory
    if export_format == "html":
        # Use a secure path for the zip output - place it in the output_dir instead of input file's parent
        zip_base_name = output_dir / "output"
        output_zip = Path(f"{zip_base_name}.zip")
        shutil.make_archive(str(zip_base_name), "zip", output_dir)
        return output_zip, extension, mime_type

    # Find the exported file - handle special cases
    exported_file = find_exported_file(output_dir, export_format, extension)

    return exported_file, extension, mime_type


def find_exported_file(output_dir: Path, export_format: str, extension: str) -> Path:
    """Find the exported file in the output directory.

    Args:
        output_dir: Directory where exported files are located
        export_format: The export format name
        extension: The expected file extension from EXPORT_FORMATS

    Returns:
        Path: Path to the found exported file

    Raises:
        HTTPException: If no exported file is found

    """
    # Handle special cases for file search patterns
    if export_format in {"reqif-sdoc", "reqifz-sdoc"}:
        # These formats have different extension patterns from their format names
        search_pattern = "**/*.reqif" if export_format == "reqif-sdoc" else "**/*.reqifz"
        exported_files = list(output_dir.glob(search_pattern))
        if not exported_files:
            # Try with the extension from EXPORT_FORMATS
            exported_files = list(output_dir.glob(f"**/*.{extension}"))
    else:
        # Use the extension from EXPORT_FORMATS for all formats (including html2pdf -> pdf)
        exported_files = list(output_dir.glob(f"**/*.{extension}"))

    if not exported_files:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=f"No {extension} file found in output after export")

    logging.info("Found exported file: %s", exported_files[0])
    return exported_files[0]


@app.post("/export", response_class=FileResponse)
async def export_document(
    sdoc_content: str = Body(..., media_type="text/plain", description="SDOC content to export"),
    format: str = Query("html", description="Export format"),
    file_name: str = Query("exported-document", description="Name for the exported file"),
) -> FileResponse:
    """Export StrictDoc document to various formats.

    Args:
        sdoc_content: The SDOC content to export
        format: The export format
        file_name: The name for the exported file

    Returns:
        FileResponse: The exported file

    """
    # Sanitize user input for logging
    sanitized_format = sanitize_for_logging(format)
    sanitized_file_name = sanitize_for_logging(file_name)
    logging.info("Export requested for format: %r, filename: %r", sanitized_format, sanitized_file_name)

    # Validate format against allowlist
    export_format = format.lower()
    # Note: format validation is handled in export_to_format function

    # Sanitize filename using pathvalidate to prevent path traversal
    sanitized_file_name = sanitize_filename(file_name, replacement_text="_")
    if sanitized_file_name != file_name:
        # Log both the original (but sanitized for logging) and sanitized filenames
        safe_original_name = sanitize_for_logging(file_name)
        safe_sanitized_name = sanitize_for_logging(sanitized_file_name)
        logging.warning("Sanitized filename from %r to %r", safe_original_name, safe_sanitized_name)

    # Basic validation of SDOC content
    if not sdoc_content or "[DOCUMENT]" not in sdoc_content:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="Invalid SDOC content: Missing [DOCUMENT] section")

    try:
        # Create temporary directories for processing
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir_path = Path(temp_dir)
            input_dir = temp_dir_path / "input"
            output_dir = temp_dir_path / "output"
            input_dir.mkdir()
            output_dir.mkdir()

            # Save SDOC content to file
            input_file = input_dir / "input.sdoc"
            with input_file.open("w", encoding="utf-8") as f:
                f.write(sdoc_content)

            logging.info("Saved SDOC content to %s", input_file)

            # Use the consolidated export_to_format function
            export_file, extension, media_type = await export_to_format(input_file, output_dir, export_format)

            # Create a secure path for the temporary file in a controlled directory
            temp_dir_obj = Path(tempfile.gettempdir())
            secure_filename = f"{sanitized_file_name}.{extension}"

            # Build the path without further sanitization
            persistent_temp_file = temp_dir_obj / secure_filename

            # Ensure the parent directory exists
            persistent_temp_file.parent.mkdir(parents=True, exist_ok=True)

            # Resolve the temporary directory path once
            temp_dir_resolved = temp_dir_obj.resolve()

            # Validate all paths to prevent path traversal
            validate_export_paths(persistent_temp_file, temp_dir_resolved, export_file, output_dir)

            # Copy the file
            shutil.copy2(export_file, persistent_temp_file)

            sanitized_format = sanitize_for_logging(export_format)
            sanitized_persistent_temp_file = sanitize_for_logging(str(persistent_temp_file))
            logging.info("Exported %s file to %s", sanitized_format, sanitized_persistent_temp_file)

            # Create cleanup function
            def cleanup_temp_file() -> None:
                try:
                    if persistent_temp_file.exists():
                        persistent_temp_file.unlink()
                except Exception as e:
                    logging.exception("Failed to clean up temporary file: %s", str(e))

            # Return the exported file
            return FileResponse(path=str(persistent_temp_file), media_type=media_type, filename=secure_filename, background=BackgroundTask(cleanup_temp_file))

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logging.exception(f"Export failed: {e!s}")
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=f"Export failed: {e!s}") from e


def validate_export_paths(persistent_temp_file: Path, temp_dir_resolved: Path, export_file: Path, output_dir: Path) -> None:
    """Validate file paths to prevent path traversal attacks.

    Args:
        persistent_temp_file: Path to where the file will be stored temporarily
        temp_dir_resolved: Resolved path of the temporary directory
        export_file: Path to the exported file
        output_dir: Path to the output directory

    Raises:
        HTTPException: If any of the paths are invalid
    """
    # Normalize and validate the paths
    persistent_temp_file_resolved = persistent_temp_file.resolve()
    export_file_resolved = export_file.resolve()
    output_dir_resolved = output_dir.resolve()

    # Convert paths to strings and sanitize them for potential logging
    safe_persistent_temp_file = sanitize_for_logging(str(persistent_temp_file_resolved))
    safe_temp_dir_resolved = sanitize_for_logging(str(temp_dir_resolved))
    safe_export_file_resolved = sanitize_for_logging(str(export_file_resolved))
    safe_output_dir_resolved = sanitize_for_logging(str(output_dir_resolved))

    # For debugging - use sanitized path strings
    logging.debug("Validating paths: temp_file=%s, temp_dir=%s", safe_persistent_temp_file, safe_temp_dir_resolved)

    # Check if persistent_temp_file is within temp_dir
    if not persistent_temp_file_resolved.is_relative_to(temp_dir_resolved):
        logging.warning("Invalid file path detected: %s not in %s", safe_persistent_temp_file, safe_temp_dir_resolved)
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="Invalid file path detected.")

    # Check if export_file is within output_dir
    if not export_file_resolved.is_relative_to(output_dir_resolved):
        logging.warning("Invalid export path detected: %s not in %s", safe_export_file_resolved, safe_output_dir_resolved)
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="Invalid export file path detected.")


def start_server(port: int) -> None:
    """Start the FastAPI server.

    Args:
        port: The port number to run the server on
    """
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
