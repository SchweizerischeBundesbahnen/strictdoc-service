# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

StrictDoc Service is a Dockerized REST API that provides access to [StrictDoc](https://github.com/strictdoc-project/strictdoc) functionality for documentation and requirements management. It accepts SDOC content and exports it to various formats (HTML, Excel, ReqIF, etc.). **Note:** PDF export is not available as it requires Chromium/ChromeDriver.

**Base Image**: Red Hat Universal Base Image (UBI) 9 Minimal for enterprise-grade security, stability, and OpenShift compatibility.

## Architecture

### Core Components

- **`app/strictdoc_service_application.py`**: Main application entry point with logging configuration and CLI argument parsing
- **`app/strictdoc_controller.py`**: FastAPI application with REST endpoints (`/version`, `/export`), request handling, and StrictDoc integration
- **`app/sanitization.py`**: Input sanitization utilities for secure logging and content processing

### Key Features

- FastAPI-based REST API with two main endpoints
- Input validation and sanitization for security
- Temporary file handling with automatic cleanup
- Support for 10 export formats with proper MIME type handling
- Comprehensive error handling and logging
- Monkey-patched StrictDoc integration for Path object compatibility

## Development Commands

### Environment Setup
```bash
# Install dependencies with uv
uv sync

# Install development dependencies
uv sync --group dev --group test
```

### Code Quality
```bash
# Format and lint code
uv run ruff format
uv run ruff check

# Type checking
uv run mypy .

# Run all linting (uses tox)
uv run tox -e lint
```

### Testing
```bash
# Run all tests with coverage
uv run pytest --cov=app tests/ --cov-report=term-missing

# Run specific test file
uv run pytest tests/export/test_unit.py -v

# Run tests with tox (includes coverage check with 80% minimum)
uv run tox -e py313

# Run integration tests (requires Docker)
./tests/shell/test_strictdoc_service.sh

# Container structure tests
container-structure-test test --image strictdoc-service:local --config ./tests/container/container-structure-test.yaml
```

### Docker Operations

**IMPORTANT:** Always use Docker BuildKit for cache mount support and faster builds:

```bash
# Build Docker image with BuildKit (REQUIRED)
DOCKER_BUILDKIT=1 docker build --build-arg APP_IMAGE_VERSION=0.0.0 -t strictdoc-service:0.0.0 .

# Or set as default in your environment
export DOCKER_BUILDKIT=1

# Run service
docker run --detach --init --publish 9083:9083 --name strictdoc-service strictdoc-service:0.0.0

# Development with Docker Compose
docker-compose up -d
docker-compose logs -f
docker-compose down
```

**Why BuildKit is required:**
- Enables `RUN --mount=type=cache` for persistent uv cache across builds
- Reduces dependency installation from minutes to **milliseconds** on rebuilds
- GitHub Actions uses BuildKit by default via `docker/setup-buildx-action`

**About the Dockerfile:**
- **Base**: Red Hat UBI 9 Minimal (`registry.access.redhat.com/ubi9/ubi-minimal:latest`)
- **Size**: ~604MB (optimized for enterprise, smaller than Debian)
- **Python**: 3.13 installed via uv to `/opt/python` (accessible by non-root user)
- **Package Manager**: microdnf (UBI minimal)
- **Dependencies**: Pre-compiled wheels for fast installation (milliseconds)
- **User**: Runs as non-root user `appuser` (UID 1000)
- **Why UBI?**: Enterprise support, OpenShift compatibility, glibc for pre-compiled wheels
- **Why not Alpine?**: tree-sitter compilation fails on Alpine arm64 (musl libc incompatibility)

### Running the Service
```bash
# Direct Python execution
uv run python -m app.strictdoc_service_application --port 9083

# Using uvicorn directly
uv run uvicorn app.strictdoc_controller:app --host 127.0.0.1 --port 9083
```

## Important Technical Details

### Security Considerations
- All user inputs are sanitized using `sanitize_for_logging()` before logging
- Filenames are sanitized using `pathvalidate.sanitize_filename()`
- Path traversal protection via `validate_export_paths()`
- Temporary files are cleaned up automatically via `BackgroundTask`

### StrictDoc Integration
- Uses monkey patching to fix Path object handling in `PickleCache.get_cached_file_path`
- Validates SDOC content by requiring `[DOCUMENT]` section
- Parses documents using StrictDoc's `SDReader` for validation
- Handles TextXSyntaxError exceptions with user-friendly error messages

### Export Format Handling
- Supports 10 formats: html, html2pdf, rst, json, excel, reqif-sdoc, reqifz-sdoc, sdoc, doxygen, spdx
- **PDF (html2pdf) is NOT functional** - requires Chromium/ChromeDriver which is not installed to keep image size small
- HTML exports are automatically zipped
- Format validation occurs at multiple levels (query parameter validation, export function)
- MIME types and extensions are defined in `EXPORT_FORMATS` dictionary

### Configuration
- Uses uv for dependency management
- Python 3.13+ required
- Ruff for linting with line length 240
- MyPy for type checking with strict settings
- Pytest with asyncio support
- Coverage minimum threshold: 80%

### Test Organization
- Unit tests: `tests/export/test_unit.py` (mocked responses)
- Integration tests: `tests/export/test_integration.py` (real Docker container)
- Controller tests: `test_strictdoc_controller.py`
- Shell tests: `tests/shell/test_strictdoc_service.sh`
- Container tests: `tests/container/container-structure-test.yaml`

## Task Tracking

**Use `/TODO.md` as a working scratchpad during development** (NOT committed to git)
- Update task checkboxes when completing work
- Add new tasks as discovered during implementation
- Helps track progress within a single issue/PR
- Link to GitHub issues for context (e.g., "Issue #59")

**TODO.md is NOT committed to git** - use PR descriptions and commit messages for permanent record

**DO NOT use the TodoWrite tool** - it's ephemeral and less useful than TODO.md
