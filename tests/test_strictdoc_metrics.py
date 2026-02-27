"""Tests for internal StrictDoc metrics tracking."""

import threading
import time

import pytest

from app.strictdoc_metrics import StrictDocMetrics, get_strictdoc_metrics, reset_strictdoc_metrics


@pytest.fixture(autouse=True)
def reset_metrics():
    """Reset metrics before and after each test."""
    reset_strictdoc_metrics()
    yield
    reset_strictdoc_metrics()


class TestStrictDocMetrics:
    """Tests for StrictDocMetrics class."""

    def test_initial_state(self):
        """Test that metrics start with correct initial values."""
        metrics = StrictDocMetrics()
        assert metrics.total_exports == 0
        assert metrics.failed_exports == 0
        assert metrics.active_exports == 0
        assert metrics.total_export_time_ms == 0.0

    def test_record_export_start(self):
        """Test recording export start increments active exports."""
        metrics = StrictDocMetrics()
        metrics.record_export_start()
        assert metrics.active_exports == 1

        metrics.record_export_start()
        assert metrics.active_exports == 2

    def test_record_export_success(self):
        """Test recording successful export updates metrics correctly."""
        metrics = StrictDocMetrics()
        metrics.record_export_start()
        metrics.record_export_success(100.0)

        assert metrics.total_exports == 1
        assert metrics.failed_exports == 0
        assert metrics.active_exports == 0
        assert metrics.total_export_time_ms == 100.0

    def test_record_export_failure(self):
        """Test recording failed export updates metrics correctly."""
        metrics = StrictDocMetrics()
        metrics.record_export_start()
        metrics.record_export_failure()

        assert metrics.total_exports == 1
        assert metrics.failed_exports == 1
        assert metrics.active_exports == 0

    def test_active_exports_never_negative(self):
        """Test that active exports never goes below zero."""
        metrics = StrictDocMetrics()
        metrics.record_export_success(100.0)  # Without calling record_export_start
        assert metrics.active_exports == 0

        metrics.record_export_failure()
        assert metrics.active_exports == 0

    def test_error_rate_calculation(self):
        """Test error rate percentage calculation."""
        metrics = StrictDocMetrics()

        # No exports yet
        assert metrics.get_error_rate_percent() == 0.0

        # 1 success, 0 failures = 0%
        metrics.record_export_start()
        metrics.record_export_success(100.0)
        assert metrics.get_error_rate_percent() == 0.0

        # 1 success, 1 failure = 50%
        metrics.record_export_start()
        metrics.record_export_failure()
        assert metrics.get_error_rate_percent() == 50.0

        # 1 success, 2 failures = 66.67%
        metrics.record_export_start()
        metrics.record_export_failure()
        assert abs(metrics.get_error_rate_percent() - 66.67) < 0.1

    def test_avg_export_time_calculation(self):
        """Test average export time calculation."""
        metrics = StrictDocMetrics()

        # No exports yet
        assert metrics.get_avg_export_time_seconds() == 0.0

        # 1 export at 1000ms
        metrics.record_export_start()
        metrics.record_export_success(1000.0)
        assert metrics.get_avg_export_time_seconds() == 1.0

        # 2 exports, total 3000ms = avg 1.5s
        metrics.record_export_start()
        metrics.record_export_success(2000.0)
        assert metrics.get_avg_export_time_seconds() == 1.5

    def test_avg_export_time_excludes_failures(self):
        """Test that failed exports don't affect average time."""
        metrics = StrictDocMetrics()
        metrics.record_export_start()
        metrics.record_export_success(1000.0)
        metrics.record_export_start()
        metrics.record_export_failure()  # This shouldn't affect timing

        # Only 1 successful export with 1000ms
        assert metrics.get_avg_export_time_seconds() == 1.0

    def test_uptime_seconds(self):
        """Test uptime calculation."""
        metrics = StrictDocMetrics()
        time.sleep(0.1)  # Sleep for 100ms
        uptime = metrics.get_uptime_seconds()
        assert uptime >= 0.1
        assert uptime < 1.0  # Should be less than 1 second

    def test_get_snapshot(self):
        """Test snapshot returns all expected fields."""
        metrics = StrictDocMetrics()
        metrics.record_export_start()
        metrics.record_export_success(500.0)

        snapshot = metrics.get_snapshot()

        assert "total_exports" in snapshot
        assert "failed_exports" in snapshot
        assert "active_exports" in snapshot
        assert "total_export_time_ms" in snapshot
        assert "error_rate_percent" in snapshot
        assert "avg_export_time_seconds" in snapshot
        assert "uptime_seconds" in snapshot

        assert snapshot["total_exports"] == 1
        assert snapshot["failed_exports"] == 0
        assert snapshot["error_rate_percent"] == 0.0
        assert snapshot["avg_export_time_seconds"] == 0.5

    def test_thread_safety(self):
        """Test that metrics operations are thread-safe."""
        metrics = StrictDocMetrics()
        num_threads = 10
        iterations_per_thread = 100

        def worker():
            for _ in range(iterations_per_thread):
                metrics.record_export_start()
                metrics.record_export_success(1.0)

        threads = [threading.Thread(target=worker) for _ in range(num_threads)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        expected_total = num_threads * iterations_per_thread
        assert metrics.total_exports == expected_total
        assert metrics.active_exports == 0
        assert metrics.total_export_time_ms == expected_total * 1.0


class TestSingletonMetrics:
    """Tests for singleton pattern."""

    def test_get_strictdoc_metrics_returns_singleton(self):
        """Test that get_strictdoc_metrics returns the same instance."""
        metrics1 = get_strictdoc_metrics()
        metrics2 = get_strictdoc_metrics()
        assert metrics1 is metrics2

    def test_reset_strictdoc_metrics_creates_new_instance(self):
        """Test that reset creates a new instance."""
        metrics1 = get_strictdoc_metrics()
        metrics1.record_export_start()
        metrics1.record_export_success(100.0)

        reset_strictdoc_metrics()

        metrics2 = get_strictdoc_metrics()
        assert metrics2.total_exports == 0
        assert metrics1 is not metrics2
