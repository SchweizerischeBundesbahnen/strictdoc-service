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

A Dockerized service providing a REST API interface to leverage [StrictDoc](https://github.com/strictdoc-project/strictdoc)'s functionality for documentation and requirements management.

Built on **Red Hat Universal Base Image (UBI)** for enterprise-grade security, stability, and OpenShift compatibility.

## Features

- Simple REST API to access [StrictDoc](https://github.com/strictdoc-project/strictdoc) **0.14.0**
- **Red Hat UBI 9 base image** - Enterprise-grade security and OpenShift compatibility
- **Fast builds** - Pre-compiled wheels, millisecond dependency installation with uv
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
  - PDF - **Not available** (requires Chromium/ChromeDriver, which significantly increases image size)

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
  --init \
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

### Prerequisites

This project uses [uv](https://github.com/astral-sh/uv) for fast and modern Python dependency management.

Install uv:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Local Development Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/SchweizerischeBundesbahnen/strictdoc-service.git
   cd strictdoc-service
   ```

2. Install dependencies:
   ```bash
   uv sync --all-groups
   ```

3. Run the service locally:
   ```bash
   uv run python -m app.strictdoc_service_application --port 9083
   ```

### Code Quality

```bash
# Format and lint code
uv run ruff format
uv run ruff check

# Type checking
uv run mypy .

# Run all linting
uv run tox -e lint
```

### Testing

```bash
# Run all tests with coverage
uv run pytest --cov=app tests/ --cov-report=term-missing

# Run tests with tox
uv run tox
```

See [tests/README.md](tests/README.md) for detailed test organization and instructions.

### Building the Docker Image

**IMPORTANT:** Always use Docker BuildKit for optimal build performance:

```bash
# Enable BuildKit for cache mount support (REQUIRED)
DOCKER_BUILDKIT=1 docker build \
  --build-arg APP_IMAGE_VERSION=0.0.0 \
  --tag strictdoc-service:0.0.0 .
```

Replace 0.0.0 with the desired version number.

#### About the Base Image

This service uses **Red Hat Universal Base Image (UBI) 9 Minimal** for optimal performance and compatibility:

- **Image size**: ~604MB (optimized for enterprise deployment)
- **Python installation**: Python 3.13 via uv (installed to `/opt/python` for non-root access)
- **Dependency management**: Ultra-fast installation with pre-compiled wheels (milliseconds vs minutes)
- **Security**: Regular security updates from Red Hat, enterprise-grade support
- **Compatibility**: OpenShift ready, glibc-based for maximum package compatibility

**Why not Alpine?** While Alpine Linux produces smaller images, it uses musl libc which causes compilation issues with some Python packages (tree-sitter) on arm64 architecture. UBI provides the best balance of size, speed, and compatibility.

### Running the Development Container

To start the Docker container with your custom-built image:

```bash
docker run --detach \
  --init \
  --publish 9083:9083 \
  --name strictdoc-service \
  strictdoc-service:0.0.0
```

### Stopping the Container

To stop the running container, execute:

```bash
docker container stop strictdoc-service
```

## Access service

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
> | `200`     | `application/json` | `{ "python": "3.13.7", "strictdoc": "0.14.0", "strictdocService": "0.0.0", "timestamp": "2025-10-08T12:23:09Z" }` |

##### Example cURL

> ```bash
>  curl -X GET -H "Content-Type: application/json" http://localhost:9083/version
> ```

</details>

## Monitoring

### Prometheus & Grafana Integration

The service exposes Prometheus-compatible metrics for comprehensive monitoring and observability through Grafana dashboards.

**Metrics Endpoint:** `/metrics` on port 9183 (dedicated metrics port)

> **Security:** The metrics endpoint is served on a separate port (9183) from the main API (9083). This allows network-level isolation using security groups or firewall rules to restrict metrics access to your Prometheus server only.

**Available Metrics:**

**Export Metrics:**
- `strictdoc_exports_total{format}` - Total successful exports (labeled by format: html, json, excel, etc.)
- `strictdoc_export_failures_total{format}` - Total failed exports (labeled by format)
- `strictdoc_export_error_rate_percent` - Export error rate as percentage

**Performance Metrics:**
- `strictdoc_export_duration_seconds{format}` - Export duration histogram (labeled by format)
- `avg_strictdoc_export_time_seconds` - Average export time in seconds
- `strictdoc_request_body_bytes` - Input document size histogram
- `strictdoc_response_body_bytes` - Output document size histogram

**Service Metrics:**
- `uptime_seconds` - Service uptime
- `active_exports` - Current number of active export operations
- `strictdoc_info{version, service_version}` - Version information

**HTTP Metrics (via prometheus-fastapi-instrumentator):**
- `http_request_duration_seconds` - HTTP request duration histogram
- `http_requests_total` - Total HTTP requests
- `http_requests_inprogress` - Current in-progress requests

**Prometheus Configuration Example:**

```yaml
scrape_configs:
  - job_name: 'strictdoc-service'
    static_configs:
      - targets: ['strictdoc-service:9183']  # Metrics on dedicated port
    metrics_path: '/metrics'
    scrape_interval: 15s
    scrape_timeout: 10s
```

**Grafana Dashboard Queries:**

```promql
# Export rate by format (requests per second)
sum(rate(strictdoc_exports_total[5m])) by (format)

# Error rate percentage
rate(strictdoc_export_failures_total[5m]) / rate(strictdoc_exports_total[5m]) * 100

# 95th percentile export duration
histogram_quantile(0.95, rate(strictdoc_export_duration_seconds_bucket[5m]))

# Average export time
avg_strictdoc_export_time_seconds
```

**Docker Compose Example with Prometheus & Grafana:**

```yaml
services:
  strictdoc-service:
    image: ghcr.io/schweizerischebundesbahnen/strictdoc-service:latest
    init: true
    ports:
      - "9083:9083"   # Main API
      - "9183:9183"   # Metrics endpoint

  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus-data:/prometheus

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    volumes:
      - grafana-data:/var/lib/grafana
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin

volumes:
  prometheus-data:
  grafana-data:
```

**Quick Start with Monitoring Stack:**

A complete monitoring setup is provided in the `monitoring/` directory:

```bash
# Start StrictDoc service with Prometheus and Grafana
./monitoring/start-monitoring.sh

# Generate test load
./monitoring/generate-load.sh 100 20

# Stop monitoring stack
./monitoring/stop-monitoring.sh
```

**Access URLs:**
| Service | URL | Credentials |
|---------|-----|-------------|
| StrictDoc Service | http://localhost:9083 | - |
| API Docs | http://localhost:9083/docs | - |
| Raw Metrics | http://localhost:9183/metrics | - |
| Prometheus | http://localhost:9090 | - |
| Grafana Dashboard | http://localhost:3000/d/strictdoc-service | admin/admin |

See [monitoring/README.md](monitoring/README.md) for detailed setup instructions.


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

**Note on PDF Export:** The `html2pdf` format is currently **not available** in this service. PDF generation requires Chromium/ChromeDriver, which would increase the Docker image size by ~300MB+. If you need PDF output, consider:
1. Using the `html` format and converting to PDF externally
2. Using a separate PDF conversion service
3. Building a custom image with Chromium installed

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
