"""Prometheus metrics collectors for StrictDoc service.

This module provides Prometheus metric collectors including counters, histograms,
gauges, and info metrics for monitoring export operations.
"""

import os

from prometheus_client import Counter, Gauge, Histogram, Info

from app.strictdoc_metrics import get_strictdoc_metrics

# Get service version from environment
SERVICE_VERSION = os.getenv("STRICTDOC_SERVICE_VERSION", "dev")

# Valid export formats (used for label validation to prevent cardinality explosion)
VALID_EXPORT_FORMATS = frozenset({"doxygen", "excel", "html", "html2pdf", "json", "reqif-sdoc", "reqifz-sdoc", "rst", "sdoc", "spdx"})


def _sanitize_format_label(export_format: str) -> str:
    """Sanitize export format for use as Prometheus label.

    Validates the format against the allowlist to prevent label cardinality explosion
    from malicious or invalid input.

    Args:
        export_format: The export format string.

    Returns:
        The format if valid, otherwise "unknown".
    """
    return export_format if export_format in VALID_EXPORT_FORMATS else "unknown"


# Import StrictDoc version
try:
    from strictdoc import __version__ as strictdoc_version  # type: ignore[import-untyped]
except ImportError:
    strictdoc_version = "unknown"

# Counters
strictdoc_exports_total = Counter(
    "strictdoc_exports_total",
    "Total number of successful StrictDoc export operations",
    ["format"],
)

strictdoc_export_failures_total = Counter(
    "strictdoc_export_failures_total",
    "Total number of failed StrictDoc export operations",
    ["format"],
)

# Histograms
strictdoc_export_duration_seconds = Histogram(
    "strictdoc_export_duration_seconds",
    "Duration of StrictDoc export operations in seconds",
    ["format"],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0),
)

strictdoc_request_body_bytes = Histogram(
    "strictdoc_request_body_bytes",
    "Size of request body in bytes",
    buckets=(100, 1000, 10000, 100000, 1000000, 10000000),
)

strictdoc_response_body_bytes = Histogram(
    "strictdoc_response_body_bytes",
    "Size of response body in bytes",
    buckets=(1000, 10000, 100000, 1000000, 10000000, 100000000),
)

# Gauges
strictdoc_export_error_rate_percent = Gauge(
    "strictdoc_export_error_rate_percent",
    "Current error rate of StrictDoc export operations as percentage",
)

avg_strictdoc_export_time_seconds = Gauge(
    "avg_strictdoc_export_time_seconds",
    "Average StrictDoc export time in seconds",
)

uptime_seconds = Gauge(
    "uptime_seconds",
    "Service uptime in seconds",
)

active_exports = Gauge(
    "active_exports",
    "Number of currently active export operations",
)

# Info
strictdoc_info = Info(
    "strictdoc",
    "StrictDoc service information",
)

# Set static info values
strictdoc_info.info(
    {
        "version": strictdoc_version,
        "service_version": SERVICE_VERSION,
    }
)


def increment_export_success(export_format: str) -> None:
    """Increment the successful export counter.

    Args:
        export_format: The export format (e.g., 'html', 'pdf').
    """
    safe_format = _sanitize_format_label(export_format)
    strictdoc_exports_total.labels(format=safe_format).inc()


def increment_export_failure(export_format: str) -> None:
    """Increment the failed export counter.

    Args:
        export_format: The export format (e.g., 'html', 'pdf').
    """
    safe_format = _sanitize_format_label(export_format)
    strictdoc_export_failures_total.labels(format=safe_format).inc()


def observe_export_duration(export_format: str, duration_seconds: float) -> None:
    """Observe export duration in the histogram.

    Args:
        export_format: The export format (e.g., 'html', 'pdf').
        duration_seconds: The duration in seconds.
    """
    safe_format = _sanitize_format_label(export_format)
    strictdoc_export_duration_seconds.labels(format=safe_format).observe(duration_seconds)


def observe_request_body_size(size_bytes: int) -> None:
    """Observe request body size in the histogram.

    Args:
        size_bytes: The size of the request body in bytes.
    """
    strictdoc_request_body_bytes.observe(size_bytes)


def observe_response_body_size(size_bytes: int) -> None:
    """Observe response body size in the histogram.

    Args:
        size_bytes: The size of the response body in bytes.
    """
    strictdoc_response_body_bytes.observe(size_bytes)


def update_gauges_from_strictdoc_metrics() -> None:
    """Update gauge values from internal StrictDoc metrics."""
    metrics = get_strictdoc_metrics()
    strictdoc_export_error_rate_percent.set(metrics.get_error_rate_percent())
    avg_strictdoc_export_time_seconds.set(metrics.get_avg_export_time_seconds())
    uptime_seconds.set(metrics.get_uptime_seconds())
    active_exports.set(metrics.get_active_exports())
