"""StrictDoc service controller module."""

import logging
import os
import re
import shutil
import tempfile
from collections.abc import Awaitable, Callable
from http import HTTPStatus
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from starlette.background import BackgroundTask
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Import StrictDoc version directly
from strictdoc import __version__ as strictdoc_version  # type: ignore[import]
from strictdoc.backend.sdoc.pickle_cache import PickleCache  # type: ignore[import]
from strictdoc.backend.sdoc.reader import SDReader  # type: ignore[import]
from strictdoc.cli.main import ProjectConfig  # type: ignore[import]
from strictdoc.core.environment import SDocRuntimeEnvironment  # type: ignore[import]

# Create a custom logger
logger = logging.getLogger(__name__)

# Service version
SERVICE_VERSION = os.getenv("STRICTDOC_SERVICE_VERSION", "dev")

app = FastAPI(
    title="StrictDoc Service API",
    description="API for StrictDoc document generation and export",
    version="1.0.0",
)


# Custom middleware for format validation
class FormatValidationMiddleware(BaseHTTPMiddleware):
    """Middleware for validating export format parameter.

    This middleware intercepts requests to the export endpoint and validates
    that the format parameter is one of the supported export formats.
    """

    async def dispatch(self, request: Request, call_next: Callable[[Request], Any]) -> JSONResponse:
        """Process the request and validate the format parameter.

        Args:
            request: The incoming request
            call_next: The next middleware in the chain

        Returns:
            JSONResponse: The response from the next middleware or an error response

        """
        # Only intercept requests to the export endpoint
        if request.url.path == "/export" and request.method == "POST":
            format_param = request.query_params.get("format")
            if format_param and format_param.lower() not in EXPORT_FORMATS:
                return JSONResponse(status_code=HTTPStatus.BAD_REQUEST, content={"detail": f"Invalid export format: {format_param}. Must be one of: {', '.join(EXPORT_FORMATS)}"})
        return await call_next(request)


# Add our custom middleware
app.add_middleware(FormatValidationMiddleware)


# Add exception handler for FastAPI's validation errors
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(exc: RequestValidationError) -> JSONResponse:
    """Convert 422 validation errors to 400 Bad Request for format validation.

    Args:
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
        return JSONResponse(status_code=HTTPStatus.BAD_REQUEST, content={"detail": f"Invalid export format. Must be one of: {', '.join(EXPORT_FORMATS)}"})

    # For other validation errors, use standard 422 response
    return JSONResponse(status_code=HTTPStatus.UNPROCESSABLE_ENTITY, content={"detail": error_details if error_details else exc.errors()})


# Define supported export formats (based on StrictDoc 0.7.0)
EXPORT_FORMATS = [
    "html",
    "html2pdf",
    "rst",
    "json",
    "excel",
    "reqif-sdoc",
    "reqifz-sdoc",
    "sdoc",
    "doxygen",
    "spdx",
]

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


# Function to sanitize file names
def sanitize_filename(filename: str) -> str:
    """Sanitize a filename to prevent path traversal attacks.

    Args:
        filename: The filename to sanitize

    Returns:
        str: The sanitized filename
    """
    # Remove any path components, only keep the base filename
    sanitized = os.path.basename(filename)

    # Additional sanitization - keep only alphanumeric chars, underscore, hyphen, and dot
    sanitized = re.sub(r"[^\w.-]", "_", sanitized)

    # Ensure the filename is not empty or starts with a dot
    if not sanitized or sanitized.startswith("."):
        sanitized = "document" + sanitized

    return sanitized


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
    logger.info(
        "Request: %s %s",
        request.method,
        request.url.path,
    )
    response = await call_next(request)
    logger.info(
        "Response: %s %s, Status: %s",
        request.method,
        request.url.path,
        response.status_code,
    )
    return response


@app.get("/version")
async def get_version() -> VersionInfo:
    """Get version information about the service and its dependencies.

    Returns:
        VersionInfo: Version information about Python, StrictDoc, and the platform.

    """
    import platform
    import sys
    import time

    # Get Python version
    python_version = sys.version.split()[0]

    # Get platform info
    platform_info = platform.platform()

    # Get current timestamp
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S %Z", time.localtime())

    return VersionInfo(python=python_version, strictdoc=strictdoc_version, platform=platform_info, timestamp=timestamp, strictdoc_service=SERVICE_VERSION)


def validate_export_format(export_format: str) -> None:
    """Validate the export format.

    Args:
        export_format: Format to validate

    Raises:
        HTTPException: If format is invalid

    """
    if export_format not in EXPORT_FORMATS:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=f"Invalid export format: {export_format}. Must be one of: {', '.join(EXPORT_FORMATS)}")


def process_sdoc_content(content: str, input_file: Path) -> None:
    """Process and validate SDOC content.

    Args:
        sdoc_content: The SDOC content to validate
        input_file: Path to the input file

    Raises:
        HTTPException: If the content is invalid

    """
    # Normalize line endings to Unix style
    content = content.replace("\r\n", "\n").replace("\r", "\n")

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
        )

        # Monkey patch the config to avoid TypeError in pickle_cache.py
        # PickleCache uses project_config.output_dir + full_path_to_file
        project_config.output_dir = input_parent + "/"

        reader.read_from_file(input_file, project_config)
    except Exception as e:
        # Clean up and raise a more user-friendly error
        error_msg = str(e)
        # Extract the most relevant part of the error message
        if "TextXSyntaxError" in error_msg:
            # Extract the error location and message
            import re

            match = re.search(r"([^:]+):(\d+):(\d+):(.*?)(?=\s*$)", error_msg)
            if match:
                file, line, col, message = match.groups()
                error_msg = f"Syntax error in SDOC document at line {line}, column {col}: {message.strip()}"
            else:
                error_msg = "Syntax error in SDOC document. Please check your document structure."

        logging.exception("SDOC parsing error: %s", error_msg)
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=error_msg) from e


def export_with_action(input_file: Path, output_dir: Path, format_name: str) -> None:
    """Export a document using ExportAction.

    Args:
        input_file: Path to input .sdoc file
        output_dir: Path to output directory
        format_name: Export format name

    """
    # Create output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)

    # Set up command
    import subprocess

    try:
        # For other formats, use subprocess to call the strictdoc command line
        # S603: subprocess call is safe here because input is controlled and not user-supplied
        cmd = ["strictdoc", "export", "--formats", format_name, "--output-dir", str(output_dir), str(input_file)]
        logging.info(f"Running command: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        if result.stderr:
            logging.warning(f"StrictDoc CLI warnings: {result.stderr}")
    except Exception as e:
        logging.exception(f"Export failed: {e!s}")
        raise RuntimeError(f"Export failed: {e!s}") from e


# ruff: noqa: C901 the function is too complex
def export_to_format(input_file: Path, output_dir: Path, export_format: str) -> tuple[Path, str, str]:
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

    # Handle format-specific configurations
    if export_format == "html":
        extension = "zip"
        mime_type = "application/zip"
    elif export_format == "html2pdf":
        extension = "pdf"
        mime_type = "application/pdf"
    elif export_format == "excel":
        extension = "xlsx"
        mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif export_format == "json":
        extension = "json"
        mime_type = "application/json"
    elif export_format == "rst":
        extension = "rst"
        mime_type = "text/x-rst"
    elif export_format == "reqif-sdoc":
        extension = "reqif"
        mime_type = "application/xml"
    elif export_format == "reqifz-sdoc":
        extension = "reqifz"
        mime_type = "application/zip"
    else:
        extension = export_format
        mime_type = "text/plain"

    # Export the document
    try:
        # Call export_with_action for the actual export
        export_with_action(input_file, output_dir, export_format)
    except Exception as e:
        logging.exception(f"Export failed: {e!s}")
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=f"Export to {export_format} failed: {e!s}") from e

    # For HTML, we need to zip the output directory
    if export_format == "html":
        # Use a secure path for the zip output
        zip_base_name = os.path.join(str(input_file.parent), "output")
        output_zip = Path(f"{zip_base_name}.zip")
        shutil.make_archive(zip_base_name, "zip", output_dir)
        return output_zip, extension, mime_type

    # Find the exported file
    pattern = "**/*.pdf" if export_format == "pdf" else f"*.{extension}"
    exported_files = list(output_dir.glob(pattern))

    if not exported_files:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=f"No {extension} file found in output after export")

    logging.info(f"Found exported file: {exported_files[0]}")
    return exported_files[0], extension, mime_type


@app.post("/export", response_class=FileResponse)
# ruff: noqa: PLR0912, PLR0915, C901  # Too many branches/statements, function is too complex
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
    logging.info(f"Export requested for format: '{format}', filename: '{file_name}'")

    # Format is already validated by middleware, just make it lowercase
    format = format.lower()

    # Sanitize filename to prevent path traversal
    sanitized_file_name = sanitize_filename(file_name)
    if sanitized_file_name != file_name:
        logging.warning(f"Sanitized filename from '{file_name}' to '{sanitized_file_name}'")
        file_name = sanitized_file_name

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

            logging.info(f"Saved SDOC content to {input_file}")

            # Run StrictDoc export using the CLI
            import subprocess

            # S603: subprocess call is safe here because input is controlled and not user-supplied
            cmd = ["strictdoc", "export", "--formats", format, "--output-dir", str(output_dir), str(input_file)]

            logging.info(f"Running StrictDoc export command: {' '.join(cmd)}")

            # ruff: noqa: S603  # subprocess call is safe here because input is controlled and not user-supplied
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if result.returncode != 0:
                logging.error(f"StrictDoc export failed: {result.stderr}")
                raise RuntimeError(f"StrictDoc export failed: {result.stderr}")

            # Determine the exported file path based on format
            export_file = None
            media_type = "application/octet-stream"
            extension = format

            if format == "html":
                # For HTML, create a zip of the output directory
                output_zip = temp_dir_path / "output.zip"
                shutil.make_archive(str(output_zip).replace(".zip", ""), "zip", output_dir)
                export_file = output_zip
                media_type = "application/zip"
                extension = "zip"
            elif format == "html2pdf":
                # PDF files can be in output directory
                pdf_files = list(output_dir.glob("**/*.pdf"))
                if not pdf_files:
                    raise RuntimeError("No PDF file found in output after export")
                export_file = pdf_files[0]
                media_type = "application/pdf"
                extension = "pdf"
            elif format == "excel":
                # Excel files have .xlsx extension
                excel_files = list(output_dir.glob("**/*.xlsx"))
                if not excel_files:
                    raise RuntimeError("No Excel file found in output after export")
                export_file = excel_files[0]
                media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                extension = "xlsx"
            elif format in ["json", "rst", "reqif-sdoc", "reqifz-sdoc", "sdoc", "doxygen", "spdx"]:
                # Search for any file with the format's extension
                search_pattern = f"**/*.{format}"
                if format in {"reqif-sdoc", "reqifz-sdoc"}:
                    # These have different extension patterns
                    search_pattern = "**/*.reqif" if format == "reqif-sdoc" else "**/*.reqifz"

                found_files = list(output_dir.glob(search_pattern))
                if not found_files:
                    # Try with just the extension
                    found_files = list(output_dir.glob(f"**/*.{format.split('-')[0]}"))

                if not found_files:
                    raise RuntimeError(f"No {format} file found in output after export")

                export_file = found_files[0]

                # Set media type based on format
                if format == "json":
                    media_type = "application/json"
                elif format == "rst":
                    media_type = "text/x-rst"
                    extension = "rst"
                elif format in ["reqif-sdoc", "reqifz-sdoc"]:
                    media_type = "application/xml" if format == "reqif-sdoc" else "application/zip"
                    extension = format.split("-")[0]
                else:
                    # Default for other formats
                    media_type = "text/plain"
                    extension = format

            if not export_file:
                raise RuntimeError(f"No {format} file found in output after export")

            # Create a secure path for the temporary file in a controlled directory
            temp_dir_obj = tempfile.gettempdir()
            secure_filename = f"{sanitized_file_name}.{extension}"
            persistent_temp_file = Path(temp_dir_obj) / secure_filename

            # Copy the file
            shutil.copy2(export_file, persistent_temp_file)

            logging.info(f"Exported {format} file to {persistent_temp_file}")

            # Create cleanup function
            def cleanup_temp_file() -> None:
                try:
                    if persistent_temp_file.exists():
                        persistent_temp_file.unlink()
                except Exception as e:
                    logging.exception(f"Failed to clean up temporary file: {e!s}")

            # Return the exported file
            return FileResponse(path=persistent_temp_file, media_type=media_type, filename=secure_filename, background=BackgroundTask(cleanup_temp_file))

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logging.exception(f"Export failed: {e!s}")
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=f"Export failed: {e!s}") from e


def start_server(port: int) -> None:
    """Start the FastAPI server."""
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
