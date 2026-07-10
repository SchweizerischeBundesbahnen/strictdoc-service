"""StrictDoc service controller module."""

import asyncio
import logging
import os
import platform
import shutil
import sys
import tempfile
import time
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from http import HTTPStatus
from pathlib import Path
from typing import TYPE_CHECKING

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from pathvalidate import sanitize_filename
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask

# Import StrictDoc version directly
from strictdoc import __version__ as strictdoc_version  # type: ignore[import]

from app.constants import EXPORT_FORMATS
from app.metrics_server import METRICS_SERVER_ENABLED, MetricsServer
from app.prometheus_metrics import increment_export_failure, increment_export_success, observe_export_duration
from app.sanitization import sanitize_for_logging
from app.strictdoc_metrics import get_strictdoc_metrics

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Awaitable, Callable

    from starlette.requests import Request
    from starlette.responses import Response

    from app.strictdoc_metrics import StrictDocMetrics

# Create a custom logger
logger = logging.getLogger(__name__)

# Default values for StrictDoc ProjectConfig (v0.14.0+)
# These replace the removed DEFAULT_* class constants
DEFAULT_PROJECT_TITLE = "Untitled Project"
DEFAULT_PROJECT_FEATURES = None
DEFAULT_SERVER_HOST = "127.0.0.1"
DEFAULT_SERVER_PORT = 5111
DEFAULT_SECTION_BEHAVIOR = "[SECTION]"

# Global metrics server instance
_metrics_server: MetricsServer | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Manage application lifecycle including metrics server.

    Args:
        app: The FastAPI application instance.

    Yields:
        None
    """
    global _metrics_server

    # Only create and start metrics server if enabled (avoids port binding in tests)
    if METRICS_SERVER_ENABLED:
        _metrics_server = MetricsServer()
        # Metrics server startup is non-fatal - main service should work without metrics
        try:
            await _metrics_server.start()
            logger.info("Application started with metrics server")
        except Exception:
            logger.exception("Failed to start metrics server - continuing without metrics")
            _metrics_server = None
    else:
        logger.info("Application started (metrics server disabled)")

    try:
        yield
    finally:
        if _metrics_server is not None:
            await _metrics_server.stop()
        logger.info("Application shutdown complete")


app = FastAPI(
    title="StrictDoc Service API",
    description="API for StrictDoc document generation and export",
    version="1.0.0",
    lifespan=lifespan,
)

# Add Prometheus FastAPI Instrumentator for HTTP metrics
ENABLE_METRICS = os.getenv("ENABLE_METRICS", "true").lower() == "true"
if ENABLE_METRICS:
    instrumentator = Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        should_respect_env_var=True,
        should_instrument_requests_inprogress=True,
        excluded_handlers=["/metrics", "/health"],
        env_var_name="ENABLE_METRICS",
        inprogress_name="http_requests_inprogress",
        inprogress_labels=True,
    )
    instrumentator.instrument(app)


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


# Request and response models
class VersionInfo(BaseModel):
    """Version information response model.

    Contains version information about Python, StrictDoc, and the platform.
    """

    python: str = Field(description="Python version")
    strictdoc: str = Field(description="Installed StrictDoc Version")
    platform: str = Field(description="Platform the service runs in")
    timestamp: str = Field(description="Build timestamp")
    strictdoc_service: str | None = Field(description="StrictDoc Service Version", default=None)


class ErrorResponse(BaseModel):
    """Error response model.

    Contains error information and optional details.
    """

    error: str = Field(description="Error message")
    details: str | None = Field(description="Error details", default=None)


class StrictdocExportParams(BaseModel):
    """Strictdoc export model"""

    content: dict[str, str] = Field(description="StrictDoc Content of the form {key.sdoc: content}")
    format: str = Field(description="StrictDoc export format")
    file_name: str = Field(description="Returned file name")


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
    timestamp = os.getenv("STRICTDOC_SERVICE_BUILD_TIMESTAMP", "")
    python_version = sys.version.split()[0]
    platform_info = platform.platform()

    return VersionInfo(python=python_version, strictdoc=strictdoc_version, platform=platform_info, timestamp=timestamp, strictdoc_service=service_version)


async def run_strictdoc_command(cmd: list[str]) -> None:
    """Run a StrictDoc command asynchronously.

    Args:
        cmd: The command to run as a list of strings

    Raises:
        RuntimeError: If the command fails or returns non-zero exit code
    """
    sanitized_cmd = [sanitize_for_logging(arg) for arg in cmd]
    logger.info("Running command: %s", " ".join(sanitized_cmd))

    try:
        # Use asyncio.create_subprocess_exec for non-blocking execution
        process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            # Capture both stdout and stderr for better error messages
            stdout_text = stdout.decode("utf-8") if stdout else ""
            stderr_text = stderr.decode("utf-8") if stderr else ""
            error_output = (stderr_text + "\n" + stdout_text).strip() or "Unknown error"
            logger.error("StrictDoc CLI error (returncode=%d): %s", process.returncode, sanitize_for_logging(error_output))
            raise RuntimeError(f"StrictDoc command failed: {sanitize_for_logging(error_output)}")

        if stderr:
            stderr_text = stderr.decode("utf-8")
            logger.warning("StrictDoc CLI warnings: %s", sanitize_for_logging(stderr_text))

    except Exception as e:
        logger.exception("Command execution failed: %s", str(e))
        raise RuntimeError(f"Command execution failed: {e!s}") from e


async def export_bulk_with_action(input_dir: Path, output_dir: Path, export_format: str) -> None:
    """Export multiple documents using ExportAction.

    Args:
        input_dir: Path to input directory containing .sdoc files
        output_dir: Path to output directory
        export_format: Export format name

    """
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        cmd = ["strictdoc", "export", "--formats", export_format, "--output-dir", str(output_dir), str(input_dir)]
        await run_strictdoc_command(cmd)
    except Exception as e:
        logger.exception("Export command failed: %s", str(e))
        raise RuntimeError(f"Export failed: {e!s}") from e


async def export_bulk_to_format(input_dir: Path, output_dir: Path, export_format: str) -> None:
    """Export multiple SDOC documents to specified format.

    Args:
        input_dir: Path to input directory
        output_dir: Path to output directory
        export_format: Format to export to

    Raises:
        HTTPException: If exported file not found or other error

    """
    if export_format not in EXPORT_FORMATS:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=f"Invalid export format: {export_format}")
    try:
        await export_bulk_with_action(input_dir, output_dir, export_format)
    except Exception as e:
        logger.exception("Bulk export failed: %s", str(e))
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=f"Export to {export_format} failed: {e!s}") from e


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

    logger.info("Found exported file: %s", exported_files[0])
    return exported_files[0]


def _build_single_file_response(
    output_dir: Path,
    export_format: str,
    sanitized_file_name: str,
) -> FileResponse:
    """Build a FileResponse for a single exported document.

    Locates the exported file in output_dir, copies it to a persistent temp path,
    and returns a FileResponse with the correct MIME type for the format.

    Args:
        output_dir: Directory containing the export output.
        export_format: The export format key (e.g. "json", "html").
        sanitized_file_name: Sanitized base name for the response file.

    Returns:
        FileResponse: Response with the exported file.
    """
    extension = EXPORT_FORMATS[export_format]["extension"]
    mime_type = EXPORT_FORMATS[export_format]["mime_type"]

    if export_format == "html":
        zip_base_name = output_dir.parent / "output"
        export_file = Path(f"{zip_base_name}.zip")
        shutil.make_archive(str(zip_base_name), "zip", output_dir)
    else:
        export_file = find_exported_file(output_dir, export_format, extension)

    secure_filename = f"{sanitized_file_name}.{extension}"
    temp_dir_obj = Path(tempfile.gettempdir())
    persistent_temp_file = temp_dir_obj / secure_filename
    persistent_temp_file.parent.mkdir(parents=True, exist_ok=True)
    validate_export_paths(persistent_temp_file, temp_dir_obj.resolve(), export_file, output_dir if export_format != "html" else output_dir.parent)
    shutil.copy2(export_file, persistent_temp_file)
    logger.info("Exported single %s file to %s", sanitize_for_logging(export_format), sanitize_for_logging(str(persistent_temp_file)))

    def cleanup() -> None:
        try:
            if persistent_temp_file.exists():
                persistent_temp_file.unlink()
        except Exception as e:
            logger.exception("Failed to clean up temporary file: %s", str(e))

    return FileResponse(path=str(persistent_temp_file), media_type=mime_type, filename=secure_filename, background=BackgroundTask(cleanup))


def _build_bulk_zip_response(
    temp_dir_path: Path,
    output_dir: Path,
    export_format: str,
    sanitized_file_name: str,
) -> FileResponse:
    """Build a FileResponse for a bulk export as a ZIP archive.

    Zips the entire output_dir, copies the archive to a persistent temp path,
    and returns a FileResponse with application/zip MIME type.

    Args:
        temp_dir_path: Root of the working TemporaryDirectory.
        output_dir: Directory containing the export output.
        export_format: The export format key (used for logging only).
        sanitized_file_name: Sanitized base name for the response file.

    Returns:
        FileResponse: Response with the ZIP archive.
    """
    zip_base_name = temp_dir_path / "bulk-export"
    export_file = Path(f"{zip_base_name}.zip")
    shutil.make_archive(str(zip_base_name), "zip", output_dir)

    secure_filename = f"{sanitized_file_name}.zip"
    temp_dir_obj = Path(tempfile.gettempdir())
    persistent_temp_file = temp_dir_obj / secure_filename
    persistent_temp_file.parent.mkdir(parents=True, exist_ok=True)
    validate_export_paths(persistent_temp_file, temp_dir_obj.resolve(), export_file, temp_dir_path)
    shutil.copy2(export_file, persistent_temp_file)
    logger.info("Exported bulk %s zip to %s", sanitize_for_logging(export_format), sanitize_for_logging(str(persistent_temp_file)))

    def cleanup() -> None:
        try:
            if persistent_temp_file.exists():
                persistent_temp_file.unlink()
        except Exception as e:
            logger.exception("Failed to clean up temporary file: %s", str(e))

    return FileResponse(path=str(persistent_temp_file), media_type="application/zip", filename=secure_filename, background=BackgroundTask(cleanup))


def check_sdoc_content(content: dict[str, str], export_format: str, metrics: StrictDocMetrics) -> None:
    """Basic checks for sdoc content. Raises HTTPException if failed."""
    if len(content) == 0:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="Empty content body")
    for doc_name, doc_content in content.items():
        if not doc_content or "[DOCUMENT]" not in doc_content:
            metrics.record_export_failure()
            increment_export_failure(export_format)
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail=f"Invalid SDOC content in '{sanitize_for_logging(doc_name)}': Missing [DOCUMENT] section",
            )
        if not doc_name.endswith(".sdoc"):
            metrics.record_export_failure()
            increment_export_failure(export_format)
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail=f"Invalid SDOC file name: {sanitize_for_logging(doc_name)}. All file names must end with .sdoc",
            )


async def _export_documents(export_params: StrictdocExportParams, sanitized_file_name: str) -> FileResponse:
    metrics = get_strictdoc_metrics()
    start_time = time.perf_counter()
    export_completed = False
    metrics.record_export_start()

    try:
        export_format = (export_params.format if isinstance(export_params, StrictdocExportParams) else "html").lower()
        if export_format not in EXPORT_FORMATS:
            raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="Invalid export format")
        # Validate all SDOC content entries
        check_sdoc_content(export_params.content, export_format, metrics)
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir_path = Path(temp_dir)
            input_dir = temp_dir_path / "input"
            output_dir = temp_dir_path / "output"
            input_dir.mkdir()
            output_dir.mkdir()

            doc_contents = sanitize_sdoc_content_filenames(export_params.content)

            # Write all documents to input directory
            for doc_name, doc_content in doc_contents.items():
                input_file = input_dir / doc_name
                with input_file.open("w", encoding="utf-8") as f:
                    f.write(doc_content)
                logger.info("Saved SDOC content to %s", input_file)

            # Single export call for all documents

            await export_bulk_to_format(input_dir, output_dir, export_format)
            if (cache_path := (output_dir / "_cache")).exists():
                shutil.rmtree(cache_path)

            response = _build_single_file_response(output_dir, export_format, sanitized_file_name) if len(export_params.content) == 1 else _build_bulk_zip_response(temp_dir_path, output_dir, export_format, sanitized_file_name)
            export_completed = True
            return response

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Export failed: %s", str(e))
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=f"Export failed: {e!s}") from e
    finally:
        # Ensure metrics are recorded even on asyncio.CancelledError (which is a BaseException)
        if not export_completed:
            metrics.record_export_failure()
            increment_export_failure(export_format)
            logger.warning("Export incomplete (client disconnect or timeout)")
        else:
            duration_ms = (time.perf_counter() - start_time) * 1000
            metrics.record_export_success(duration_ms)
            increment_export_success(export_format)
            observe_export_duration(export_format, duration_ms / 1000)


@app.post("/export", response_class=FileResponse)
async def export_documents(export_params: StrictdocExportParams) -> FileResponse:
    """Export one or more StrictDoc documents to the requested format.

    When a single document is provided, returns the file in the requested format.
    When multiple documents are provided, returns a ZIP archive containing all exported files.

    Args:
        export_params: Export parameters including content dict, format, and output filename.

    Returns:
        FileResponse: The exported file or ZIP archive.
    """
    export_format = export_params.format.lower()
    file_name = export_params.file_name

    logger.info(
        "Export requested: format=%r, filename=%r, documents=%d",
        sanitize_for_logging(export_format),
        sanitize_for_logging(file_name),
        len(export_params.content),
    )

    sanitized_file_name = sanitize_filename(file_name, replacement_text="_")
    if sanitized_file_name != file_name:
        logger.warning("Sanitized filename from %r to %r", sanitize_for_logging(file_name), sanitize_for_logging(sanitized_file_name))

    return await _export_documents(export_params, sanitized_file_name)


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
    logger.debug("Validating paths: temp_file=%s, temp_dir=%s", safe_persistent_temp_file, safe_temp_dir_resolved)

    # Check if persistent_temp_file is within temp_dir
    if not persistent_temp_file_resolved.is_relative_to(temp_dir_resolved):
        logger.warning("Invalid file path detected: %s not in %s", safe_persistent_temp_file, safe_temp_dir_resolved)
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="Invalid file path detected.")

    # Check if export_file is within output_dir
    if not export_file_resolved.is_relative_to(output_dir_resolved):
        logger.warning("Invalid export path detected: %s not in %s", safe_export_file_resolved, safe_output_dir_resolved)
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="Invalid export file path detected.")


def sanitize_sdoc_content_filenames(sdoc_contents: dict[str, str]) -> dict[str, str]:
    contents = {sanitize_filename(doc_name, replacement_text="_"): content for doc_name, content in sdoc_contents.items()}
    if len(contents) != len(sdoc_contents):
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="Multi-export filename collision")
    return contents


def start_server(host: str, port: int) -> None:
    """Start the FastAPI server.

    Args:
        port: The port number to run the server on
    """
    uvicorn.run(app, host=host, port=port, log_level="info")
