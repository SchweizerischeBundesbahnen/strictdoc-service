[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=SchweizerischeBundesbahnen_strictdoc-service&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=SchweizerischeBundesbahnen_strictdoc-service)
[![Bugs](https://sonarcloud.io/api/project_badges/measure?project=SchweizerischeBundesbahnen_strictdoc-service&metric=bugs)](https://sonarcloud.io/summary/new_code?id=SchweizerischeBundesbahnen_strictdoc-service)
[![Code Smells](https://sonarcloud.io/api/project_badges/measure?project=SchweizerischeBundesbahnen_strictdoc-service&metric=code_smells)](https://sonarcloud.io/summary/new_code?id=SchweizerischeBundesbahnen_strictdoc-service)
[![Coverage](https://sonarcloud.io/api/project_badges/measure?project=SchweizerischeBundesbahnen_strictdoc-service&metric=coverage)](https://sonarcloud.io/summary/new_code?id=SchweizerischeBundesbahnen_strictdoc-service)
[![Duplicated Lines (%)](https://sonarcloud.io/api/project_badges/measure?project=SchweizerischeBundesbahnen_strictdoc-service&metric=duplicated_lines_density)](https://sonarcloud.io/summary/new_code?id=SchweizerischeBundesbahnen_strictdoc-service)
[![Lines of Code](https://sonarcloud.io/api/project_badges/measure?project=SchweizerischeBundesbahnen_strictdoc-service&metric=ncloc)](https://sonarcloud.io/summary/new_code?id=SchweizerischeBundesbahnen_strictdoc-service)
[![Reliability Rating](https://sonarcloud.io/api/project_badges/measure?project=SchweizerischeBundesbahnen_strictdoc-service&metric=reliability_rating)](https://sonarcloud.io/summary/new_code?id=SchweizerischeBundesbahnen_strictdoc-service)
[![Security Rating](https://sonarcloud.io/api/project_badges/measure?project=SchweizerischeBundesbahnen_strictdoc-service&metric=security_rating)](https://sonarcloud.io/summary/new_code?id=SchweizerischeBundesbahnen_strictdoc-service)
[![Maintainability Rating](https://sonarcloud.io/api/project_badges/measure?project=SchweizerischeBundesbahnen_strictdoc-service&metric=sqale_rating)](https://sonarcloud.io/summary/new_code?id=SchweizerischeBundesbahnen_strictdoc-service)
[![Vulnerabilities](https://sonarcloud.io/api/project_badges/measure?project=SchweizerischeBundesbahnen_strictdoc-service&metric=vulnerabilities)](https://sonarcloud.io/summary/new_code?id=SchweizerischeBundesbahnen_strictdoc-service)

# StrictDoc Service

A Dockerized service providing a REST API interface to leverage StrictDoc's functionality for documentation and requirements management.

## Features

- Simple REST API to access StrictDoc
- Compatible with amd64 and arm64 architectures
- Easily deployable via Docker or Docker Compose
- Configurable port and logging level
- Support for multiple export formats:
  - HTML (default) - Web-based documentation
  - JSON - Structured data for programmatic access
  - Excel - Native Microsoft Excel format
  - ReqIF/ReqIFZ - Requirements Interchange Format (XML/compressed)
  - RST - ReStructured Text for documentation
  - SDOC - StrictDoc native format
  - PDF (experimental) - Printable document format

## Getting Started

### Installation

To install the latest version of the StrictDoc Service, run the following command:

```bash
docker pull ghcr.io/schweizerischebundesbahnen/strictdoc-service:latest
```

### Running the Service

#### Using Docker

To start the StrictDoc service container, execute:

```bash
docker run --detach \
  --publish 9083:9083 \
  --name strictdoc-service \
  ghcr.io/schweizerischebundesbahnen/strictdoc-service:latest
```

The service will be accessible on port 9083.

#### Using Docker Compose

A production-ready docker-compose.yml file is provided with the repository. To use it:

```bash
# Start the service
docker-compose up -d

# Check logs
docker-compose logs -f

# Stop the service
docker-compose down
```

You can customize the environment variables by creating a `.env` file:

```bash
# .env example
APP_VERSION=1.0.0
LOG_LEVEL=DEBUG
```

### Using as a Base Image

To extend or customize the service, use it as a base image in the Dockerfile:

```Dockerfile
FROM ghcr.io/schweizerischebundesbahnen/strictdoc-service:latest
```

## Development

### Building the Docker Image

To build the Docker image from the source with a custom version, use:

```bash
docker build \
  --build-arg APP_IMAGE_VERSION=0.0.0 \
  --file Dockerfile \
  --tag strictdoc-service:0.0.0 .
```

Replace 0.0.0 with the desired version number.

### Running the Development Container

To start the Docker container with your custom-built image:

```bash
docker run --detach \
  --publish 9083:9083 \
  --name strictdoc-service \
  strictdoc-service:0.0.0
```

### Stopping the Container

To stop the running container, execute:

```bash
docker container stop strictdoc-service
```

### Testing

The project has a comprehensive test suite organized into several categories:

#### Quick Start

```bash
# Run all tests
poetry run pytest
```
```bash
# Run with coverage
poetry run pytest --cov=src tests/ --cov-report=term-missing
```
```bash
# Run pre-commit hooks
poetry run pre-commit run --all
```

#### Test Categories

1. **Export Tests** (`tests/export/`)
   - Unit tests with mocked responses
   - Integration tests with real Docker container
   - Comprehensive format testing (HTML, JSON, Excel, ReqIF, etc.)

2. **Docker Tests**
   ```bash
   # Full test suite in Docker environment
   ./test_with_docker.sh
   ```
   ```bash
   # Container structure tests
   container-structure-test test --image strictdoc-service:0.0.0 --config ./tests/container/container-structure-test.yaml
   ```

3. **Development Testing**
   ```bash
   # Run tox environments
   poetry run tox
   ```
   ```bash
   # Run specific test file
   poetry run pytest tests/export/test_unit.py -v
   ```

#### Shell Tests

The project includes shell-based tests for validating the StrictDoc service API functionality:

```bash
# Run the shell-based API test suite
./tests/shell/test_strictdoc_service.sh
```

This script will:
1. Build a test Docker image
2. Start the StrictDoc service container
3. Test the version endpoint
4. Test all supported export formats (JSON, HTML, ReqIF, Excel, RST, SDOC, ReqIFZ)
5. Validate format-specific responses
6. Test error handling scenarios
7. Clean up all resources when complete

The shell test is especially useful for end-to-end validation of the service's export functionality with real HTTP requests. It creates sample files for each export format that can be manually inspected if needed.

### Access service

StrictDoc Service provides the following endpoints:

------------------------------------------------------------------------------------------

#### Getting version info

<details>
  <summary>
    <code>GET</code> <code>/version</code>
  </summary>

##### Responses

> | HTTP code | Content-Type       | Response                                                                                                                            |
> |-----------|--------------------|-------------------------------------------------------------------------------------------------------------------------------------|
> | `200`     | `application/json` | `{ "python": "3.13.0", "strictdoc": "0.7.0", "strictdocService": "0.0.0", "timestamp": "2024-09-23T12:23:09Z" }` |

##### Example cURL

> ```bash
>  curl -X GET -H "Content-Type: application/json" http://localhost:9083/version
> ```

</details>


------------------------------------------------------------------------------------------

#### Export StrictDoc Document

<details>
  <summary>
    <code>POST</code> <code>/export</code>
  </summary>

##### Parameters

> | Parameter name | Type     | Data type | Description                                                                                                   |
> |----------------|----------|-----------|---------------------------------------------------------------------------------------------------------------|
> | format         | optional | string    | Export format: html, html2pdf, rst, json, excel, reqif-sdoc, reqifz-sdoc, sdoc, doxygen, spdx (default: html) |
> | file_name      | optional | string    | Base name for the output file (default: exported-document)                                                    |

##### Responses

> | HTTP code | Content-Type             | Response                      |
> |-----------|--------------------------|-------------------------------|
> | `200`     | Varies by export format  | Exported document (file)      |
> | `400`     | `plain/text`             | Error message with exception  |
> | `500`     | `plain/text`             | Error message with exception  |

##### Example cURL

> ```bash
> curl -X POST -H "Content-Type: text/plain" --data-binary @input.sdoc "http://localhost:9083/export?format=reqif-sdoc&file_name=requirements" --output requirements.reqif
> ```

</details>

## Test Organization

The test suite is organized as follows:

### Export Tests (`tests/export/`)

- `conftest.py`: Shared fixtures and utilities for export tests
  - Docker container setup/teardown
  - Test parameters and session management
  - Common test data (sample SDOC content)

- `test_unit.py`: Unit tests with mocked responses
  - Export format tests (HTML, JSON, Excel, ReqIF, ReqIFZ, RST, SDOC)
  - PDF export tests
  - Error handling tests
  - Input validation tests

- `test_integration.py`: Integration tests using real Docker container
  - Version endpoint test
  - Export format tests with real responses
  - Format-specific content validation
  - Error handling with real service
  - Connection error handling

### Running Tests

```bash
# Run all tests
poetry run pytest
```
```bash
# Run only unit tests
poetry run pytest tests/export/test_unit.py
```
```bash
# Run only integration tests
poetry run pytest tests/export/test_integration.py
```
```bash
# Run with verbose output
poetry run pytest -v
```
```bash
# Run with coverage
poetry run pytest --cov=app tests/
```
