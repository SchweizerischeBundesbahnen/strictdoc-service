"""Tests for Prometheus metrics collectors."""

import pytest

from app.prometheus_metrics import (
    active_exports,
    avg_strictdoc_export_time_seconds,
    increment_export_failure,
    increment_export_success,
    observe_export_duration,
    observe_request_body_size,
    observe_response_body_size,
    strictdoc_export_duration_seconds,
    strictdoc_export_error_rate_percent,
    strictdoc_export_failures_total,
    strictdoc_exports_total,
    strictdoc_request_body_bytes,
    strictdoc_response_body_bytes,
    update_gauges_from_strictdoc_metrics,
    uptime_seconds,
)
from app.strictdoc_metrics import get_strictdoc_metrics, reset_strictdoc_metrics


@pytest.fixture(autouse=True)
def reset_metrics():
    """Reset internal metrics before each test."""
    reset_strictdoc_metrics()
    yield
    reset_strictdoc_metrics()


class TestCounters:
    """Tests for Prometheus counters."""

    def test_increment_export_success(self):
        """Test incrementing successful export counter."""
        # Get initial values
        initial_total = strictdoc_exports_total.labels(format="html")._value.get()
        initial_failures = strictdoc_export_failures_total.labels(format="html")._value.get()

        increment_export_success("html")

        # Check incremented
        assert strictdoc_exports_total.labels(format="html")._value.get() == initial_total + 1
        assert strictdoc_export_failures_total.labels(format="html")._value.get() == initial_failures

    def test_increment_export_failure(self):
        """Test incrementing failed export counter."""
        # Get initial values
        initial_total = strictdoc_exports_total.labels(format="pdf")._value.get()
        initial_failures = strictdoc_export_failures_total.labels(format="pdf")._value.get()

        increment_export_failure("pdf")

        # Both counters should increment for failures
        assert strictdoc_exports_total.labels(format="pdf")._value.get() == initial_total + 1
        assert strictdoc_export_failures_total.labels(format="pdf")._value.get() == initial_failures + 1


class TestHistograms:
    """Tests for Prometheus histograms."""

    def test_observe_export_duration(self):
        """Test observing export duration."""
        # This should not raise any errors
        observe_export_duration("html", 1.5)
        observe_export_duration("json", 0.5)

        # Verify the histogram is properly labeled
        assert strictdoc_export_duration_seconds.labels(format="html") is not None
        assert strictdoc_export_duration_seconds.labels(format="json") is not None

    def test_observe_request_body_size(self):
        """Test observing request body size."""
        observe_request_body_size(1000)
        observe_request_body_size(50000)

        # Verify the histogram exists and can be queried
        assert strictdoc_request_body_bytes is not None

    def test_observe_response_body_size(self):
        """Test observing response body size."""
        observe_response_body_size(5000)
        observe_response_body_size(100000)

        # Verify the histogram exists and can be queried
        assert strictdoc_response_body_bytes is not None


class TestGauges:
    """Tests for Prometheus gauges."""

    def test_update_gauges_from_strictdoc_metrics(self):
        """Test updating gauges from internal metrics."""
        metrics = get_strictdoc_metrics()

        # Simulate some activity
        metrics.record_export_start()
        metrics.record_export_success(1000.0)
        metrics.record_export_start()
        metrics.record_export_failure()

        # Update gauges
        update_gauges_from_strictdoc_metrics()

        # Check gauge values
        assert strictdoc_export_error_rate_percent._value.get() == 50.0
        assert avg_strictdoc_export_time_seconds._value.get() == 1.0
        assert uptime_seconds._value.get() > 0
        assert active_exports._value.get() == 0  # Both exports completed

    def test_update_gauges_with_active_exports(self):
        """Test that active exports gauge reflects in-progress work."""
        metrics = get_strictdoc_metrics()

        metrics.record_export_start()
        metrics.record_export_start()

        update_gauges_from_strictdoc_metrics()

        assert active_exports._value.get() == 2


class TestMetricLabels:
    """Tests for metric label handling."""

    def test_different_format_labels(self):
        """Test that different formats have separate counters."""
        # Get initial values
        html_initial = strictdoc_exports_total.labels(format="html")._value.get()
        json_initial = strictdoc_exports_total.labels(format="json")._value.get()

        increment_export_success("html")
        increment_export_success("html")
        increment_export_success("json")

        assert strictdoc_exports_total.labels(format="html")._value.get() == html_initial + 2
        assert strictdoc_exports_total.labels(format="json")._value.get() == json_initial + 1
