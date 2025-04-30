"""StrictDoc service controller module."""

import logging
import os
import shutil
import tempfile
from http import HTTPStatus
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union, Awaitable

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
from strictdoc import __version__ as strictdoc_version  # type: ignore
from strictdoc.backend.sdoc.pickle_cache import PickleCache  # type: ignore
from strictdoc.backend.sdoc.reader import SDReader  # type: ignore
from strictdoc.cli.main import ProjectConfig  # type: ignore
from strictdoc.core.environment import SDocRuntimeEnvironment  # type: ignore

# Create a custom logger
logger = logging.getLogger(__name__)

app = FastAPI(
    title="StrictDoc Service API",
    description="API for StrictDoc document generation and export",
    version="1.0.0",
)


# Custom middleware for format validation
class FormatValidationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Any]) -> JSONResponse:
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
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Convert 422 validation errors to 400 Bad Request for format validation."""
    error_details = []
    format_validation_error = False

    # Check each error to see if it's related to format parameter
    for error in exc.errors():
        # Format error handling - if format is in the error path, it's a format error
        if error.get("loc") and len(error["loc"]) >= 2 and error["loc"][0] == "query" and error["loc"][1] == "format":
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
    "csv",  # We add CSV as a custom format that we'll handle ourselves
]

# Monkey patch PickleCache.get_cached_file_path to handle Path objects
original_get_cached_file_path = PickleCache.get_cached_file_path


def patched_get_cached_file_path(file_path: Union[str, Path], project_config: Any, content_kind: str) -> str:
    # Convert file_path to str if it's a Path
    if hasattr(file_path, "absolute"):  # It's likely a Path object
        file_path = str(file_path.absolute())
    return original_get_cached_file_path(file_path, project_config, content_kind)


# Apply the monkey patch
PickleCache.get_cached_file_path = patched_get_cached_file_path


# Request and response models
class VersionInfo(BaseModel):
    python: str
    strictdoc: str
    platform: str
    timestamp: str
    strictdocService: str | None = None


class ErrorResponse(BaseModel):
    error: str
    details: str | None = None


# Middleware for logging
@app.middleware("http")
async def log_requests(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    logging.info(
        "Request: %s %s",
        request.method,
        request.url.path,
    )
    response = await call_next(request)
    logging.info(
        "Response: %s %s, Status: %s",
        request.method,
        request.url.path,
        response.status_code,
    )
    return response


@app.get("/version", response_model=VersionInfo)
async def version() -> dict:
    """Get version information.

    Returns:
        dict: Version information

    """
    import platform
    import sys
    import time
    import strictdoc

    # Get Python version
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    # Get StrictDoc version
    strictdoc_version = strictdoc.__version__

    # Get platform info
    platform_info = platform.platform()

    # Get timestamp
    build_timestamp = os.getenv("STRICTDOC_SERVICE_BUILD_TIMESTAMP", time.strftime("%Y-%m-%dT%H:%M:%SZ"))

    # Get service version
    service_version = os.getenv("STRICTDOC_SERVICE_VERSION", "dev")

    return {
        "python": python_version,
        "strictdoc": strictdoc_version,
        "platform": platform_info,
        "timestamp": build_timestamp,
        "strictdocService": service_version,
    }


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
        content: SDOC content to process
        input_file: Path to write content to

    Raises:
        HTTPException: If content is invalid

    """
    # Normalize line endings to Unix style
    content = content.replace("\r\n", "\n").replace("\r", "\n")

    # Very basic validation of SDOC content
    if "[DOCUMENT]" not in content:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="Missing [DOCUMENT] section in SDOC content")

    # Write content to file
    with input_file.open("w", encoding="utf-8") as f:
        f.write(content)

    # Parse the document using StrictDoc's reader to validate
    try:
        reader = SDReader()
        # Create environment and config with explicit paths
        environment = SDocRuntimeEnvironment(str(input_file.parent))
        project_config = ProjectConfig(
            environment=environment,
            project_title=ProjectConfig.DEFAULT_PROJECT_TITLE,
            dir_for_sdoc_assets=str(input_file.parent),
            dir_for_sdoc_cache=str(input_file.parent / "cache"),
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
        project_config.output_dir = str(input_file.parent) + "/"

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
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=error_msg)


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
    import csv
    import subprocess

    try:
        if format_name == "csv":
            # For CSV, we'll bypass StrictDoc and generate it ourselves
            # since this is just for testing
            from strictdoc.backend.sdoc.reader import SDReader

            # Create simple environment and config
            environment = SDocRuntimeEnvironment(str(input_file.parent))
            project_config = ProjectConfig(
                environment=environment,
                project_title=ProjectConfig.DEFAULT_PROJECT_TITLE,
                dir_for_sdoc_assets=str(input_file.parent),
                dir_for_sdoc_cache=str(input_file.parent),
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

            # Read document with SDReader
            reader = SDReader()
            document = reader.read_from_file(str(input_file), project_config)

            # Extract requirements data
            requirements_data = []
            for section in document.section_contents:
                if hasattr(section, "parts"):
                    for part in section.parts:
                        if hasattr(part, "requirements"):
                            for req in part.requirements:
                                row = {
                                    "UID": req.uid if hasattr(req, "uid") else "",
                                    "Status": req.status if hasattr(req, "status") else "",
                                    "Title": req.title if hasattr(req, "title") else "",
                                    "Statement": req.statement if hasattr(req, "statement") else "",
                                    "Rationale": req.rationale if hasattr(req, "rationale") else "",
                                }
                                requirements_data.append(row)
                        elif hasattr(part, "uid"):  # Part is a requirement
                            req = part
                            row = {
                                "UID": req.uid if hasattr(req, "uid") else "",
                                "Status": req.status if hasattr(req, "status") else "",
                                "Title": req.title if hasattr(req, "title") else "",
                                "Statement": req.statement if hasattr(req, "statement") else "",
                                "Rationale": req.rationale if hasattr(req, "rationale") else "",
                            }
                            requirements_data.append(row)
                elif hasattr(section, "requirements"):
                    for req in section.requirements:
                        row = {
                            "UID": req.uid if hasattr(req, "uid") else "",
                            "Status": req.status if hasattr(req, "status") else "",
                            "Title": req.title if hasattr(req, "title") else "",
                            "Statement": req.statement if hasattr(req, "statement") else "",
                            "Rationale": req.rationale if hasattr(req, "rationale") else "",
                        }
                        requirements_data.append(row)
                elif hasattr(section, "uid"):  # Section is a requirement
                    req = section
                    row = {
                        "UID": req.uid if hasattr(req, "uid") else "",
                        "Status": req.status if hasattr(req, "status") else "",
                        "Title": req.title if hasattr(req, "title") else "",
                        "Statement": req.statement if hasattr(req, "statement") else "",
                        "Rationale": req.rationale if hasattr(req, "rationale") else "",
                    }
                    requirements_data.append(row)

            # Write to CSV
            file_name = input_file.stem + ".csv"
            csv_file_path = output_dir / file_name

            with open(csv_file_path, "w", newline="") as csvfile:
                fieldnames = ["UID", "Status", "Title", "Statement", "Rationale"]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for row in requirements_data:
                    writer.writerow(row)

            logging.info(f"Created CSV file at {csv_file_path}")

            # Debug: check file contents
            with open(csv_file_path) as f:
                header = f.readline().strip()
                logging.info(f"CSV header: {header}")
        else:
            # For other formats, use subprocess to call the strictdoc command line
            cmd = ["strictdoc", "export", "--formats", format_name, "--output-dir", str(output_dir), str(input_file)]
            logging.info(f"Running command: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            if result.stderr:
                logging.warning(f"StrictDoc CLI warnings: {result.stderr}")
    except Exception as e:
        logging.exception(f"Export failed: {e!s}")
        raise RuntimeError(f"Export failed: {e!s}")


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
    elif export_format == "csv":
        extension = "csv"
        mime_type = "text/csv"
    else:
        extension = export_format
        mime_type = "text/plain"

    # Export the document
    try:
        # Call export_with_action for the actual export
        export_with_action(input_file, output_dir, export_format)
    except Exception as e:
        logging.exception(f"Export failed: {e!s}")
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=f"Export to {export_format} failed: {e!s}")

    # For HTML, we need to zip the output directory
    if export_format == "html":
        output_zip = input_file.parent / "output.zip"
        shutil.make_archive(str(output_zip).replace(".zip", ""), "zip", output_dir)
        return output_zip, extension, mime_type

    # For CSV, find the exact file since the filename is based on the document name
    if export_format == "csv":
        # The CSV exporter in export_with_action creates a file with the document's base name
        document_base_name = input_file.stem
        csv_file = output_dir / f"{document_base_name}.csv"

        if not csv_file.exists():
            # Try looking for any CSV file as fallback
            csv_files = list(output_dir.glob("*.csv"))
            if csv_files:
                csv_file = csv_files[0]
            else:
                raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="No CSV file found in output after export")

        logging.info(f"Found CSV file at {csv_file}")
        return csv_file, extension, mime_type

    # For other formats, find the exported file
    pattern = "**/*.pdf" if export_format == "pdf" else f"*.{extension}"
    exported_files = list(output_dir.glob(pattern))

    if not exported_files:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=f"No {extension} file found in output after export")

    logging.info(f"Found exported file: {exported_files[0]}")
    return exported_files[0], extension, mime_type


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
    logging.info(f"Export requested for format: '{format}', filename: '{file_name}'")

    # Format is already validated by middleware, just make it lowercase
    format = format.lower()

    # Basic validation of SDOC content
    if not sdoc_content or "[DOCUMENT]" not in sdoc_content:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="Invalid SDOC content: Missing [DOCUMENT] section")

    try:
        # Special handling for CSV which isn't directly supported by StrictDoc CLI
        if format == "csv":
            return await export_csv(sdoc_content, file_name)

        # Create temporary directories for processing
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir_path = Path(temp_dir)
            input_dir = temp_dir_path / "input"
            output_dir = temp_dir_path / "output"
            input_dir.mkdir()
            output_dir.mkdir()

            # Save SDOC content to file
            input_file = input_dir / "input.sdoc"
            with open(input_file, "w", encoding="utf-8") as f:
                f.write(sdoc_content)

            logging.info(f"Saved SDOC content to {input_file}")

            # Run StrictDoc export using the CLI
            import subprocess

            cmd = ["strictdoc", "export", "--formats", format, "--output-dir", str(output_dir), str(input_file)]

            logging.info(f"Running StrictDoc export command: {' '.join(cmd)}")

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
                if format == "reqif-sdoc" or format == "reqifz-sdoc":
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
                    if format == "reqif-sdoc":
                        media_type = "application/xml"
                    else:  # reqifz-sdoc
                        media_type = "application/zip"
                    extension = format.split("-")[0]
                else:
                    # Default for other formats
                    media_type = "text/plain"
                    extension = format

            if not export_file:
                raise RuntimeError(f"No {format} file found in output after export")

            # Copy to a persistent location
            persistent_temp_file = Path(tempfile.gettempdir()) / f"{file_name}.{extension}"
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
            return FileResponse(path=persistent_temp_file, media_type=media_type, filename=f"{file_name}.{extension}", background=BackgroundTask(cleanup_temp_file))

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logging.exception(f"Export failed: {e!s}")
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=f"Export failed: {e!s}")


async def export_csv(sdoc_content: str, file_name: str) -> FileResponse:
    """Export document to CSV format.

    Args:
        sdoc_content: SDOC content to export
        file_name: Name for the exported file

    Returns:
        FileResponse: CSV file

    """
    logging.info("CSV export requested - using custom CSV generator")

    # Basic validation of SDOC content
    if not sdoc_content or "[DOCUMENT]" not in sdoc_content:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="Invalid SDOC content: Missing [DOCUMENT] section")

    # Create a temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)

        # Save the SDOC content
        input_file = temp_dir_path / "input.sdoc"
        with open(input_file, "w", encoding="utf-8") as f:
            f.write(sdoc_content)

        logging.info(f"Saved SDOC content to {input_file}")

        # Create a CSV file with the expected format
        csv_file = temp_dir_path / f"{file_name}.csv"

        # Parse the SDOC content manually to extract requirements
        with open(csv_file, "w", newline="", encoding="utf-8") as f:
            import csv
            import re

            # Create CSV writer
            writer = csv.writer(f)

            # Write header
            writer.writerow(["UID", "Status", "Title", "Statement", "Rationale"])

            # Extract data using regex
            uid_pattern = r"\[REQUIREMENT\][\r\n]+UID: ([^\r\n]+)"
            status_pattern = r"STATUS: ([^\r\n]+)"
            title_pattern = r"TITLE: ([^\r\n]+)"
            statement_pattern = r"STATEMENT: >>>(.*?)<<<"
            rationale_pattern = r"RATIONALE: >>>(.*?)<<<"

            # Find all requirements data
            uids = re.findall(uid_pattern, sdoc_content, re.DOTALL)
            statuses = re.findall(status_pattern, sdoc_content, re.DOTALL)
            titles = re.findall(title_pattern, sdoc_content, re.DOTALL)
            statements = re.findall(statement_pattern, sdoc_content, re.DOTALL)
            rationales = re.findall(rationale_pattern, sdoc_content, re.DOTALL)

            logging.info(f"Found {len(uids)} UIDs in SDOC: {uids}")

            # Write rows
            for i in range(len(uids)):
                uid = uids[i] if i < len(uids) else ""
                status = statuses[i] if i < len(statuses) else ""
                title = titles[i] if i < len(titles) else ""
                statement = statements[i].strip() if i < len(statements) else ""
                rationale = rationales[i].strip() if i < len(rationales) else ""

                writer.writerow([uid, status, title, statement, rationale])

        logging.info(f"Created CSV file at {csv_file}")

        # Debug: Print first line of CSV
        with open(csv_file, encoding="utf-8") as f:
            first_line = f.readline().strip()
            logging.info(f"CSV first line: {first_line}")

        # Create a persistent copy of the CSV file
        persistent_temp_file = Path(tempfile.gettempdir()) / f"{file_name}.csv"
        shutil.copy2(csv_file, persistent_temp_file)

        logging.info(f"Copied CSV file to persistent location: {persistent_temp_file}")

        # Create cleanup function
        def cleanup_temp_file() -> None:
            try:
                if persistent_temp_file.exists():
                    persistent_temp_file.unlink()
            except Exception as e:
                logging.exception(f"Failed to clean up temporary file: {e!s}")

        # Return the CSV file
        return FileResponse(path=persistent_temp_file, media_type="text/csv", filename=f"{file_name}.csv", background=BackgroundTask(cleanup_temp_file))


def start_server(port: int) -> None:
    """Start the FastAPI server."""
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
