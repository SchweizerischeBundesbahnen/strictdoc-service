"""Internal metrics tracking for StrictDoc service.

This module provides thread-safe metrics tracking for export operations,
including counters, timing, and error rate calculations.
"""

import threading
import time
from dataclasses import dataclass, field


@dataclass
class StrictDocMetrics:
    """Thread-safe metrics tracking for StrictDoc export operations.

    Tracks total exports, failures, active exports, timing, and uptime.
    All operations are thread-safe using a lock.
    """

    total_exports: int = 0
    failed_exports: int = 0
    active_exports: int = 0
    total_export_time_ms: float = 0.0
    start_time: float = field(default_factory=time.time)
    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False)

    def record_export_start(self) -> None:
        """Record the start of an export operation."""
        with self._lock:
            self.active_exports += 1

    def record_export_success(self, duration_ms: float) -> None:
        """Record a successful export operation.

        Args:
            duration_ms: Duration of the export in milliseconds.
        """
        with self._lock:
            self.total_exports += 1
            self.active_exports = max(0, self.active_exports - 1)
            self.total_export_time_ms += duration_ms

    def record_export_failure(self) -> None:
        """Record a failed export operation."""
        with self._lock:
            self.total_exports += 1
            self.failed_exports += 1
            self.active_exports = max(0, self.active_exports - 1)

    def get_error_rate_percent(self) -> float:
        """Calculate the error rate as a percentage.

        Returns:
            Error rate percentage (0-100). Returns 0 if no exports have been made.
        """
        with self._lock:
            if self.total_exports == 0:
                return 0.0
            return (self.failed_exports / self.total_exports) * 100

    def get_avg_export_time_seconds(self) -> float:
        """Calculate the average export time in seconds.

        Returns:
            Average export time in seconds. Returns 0 if no exports have been made.
        """
        with self._lock:
            successful_exports = self.total_exports - self.failed_exports
            if successful_exports == 0:
                return 0.0
            return (self.total_export_time_ms / successful_exports) / 1000.0

    def get_uptime_seconds(self) -> float:
        """Get the uptime in seconds since the metrics were initialized.

        Returns:
            Uptime in seconds.
        """
        return time.time() - self.start_time

    def get_active_exports(self) -> int:
        """Get the current number of active exports (thread-safe).

        Returns:
            Number of active export operations.
        """
        with self._lock:
            return self.active_exports

    def get_snapshot(self) -> dict[str, float | int]:
        """Get a snapshot of current metrics.

        Returns:
            Dictionary containing all current metric values.
        """
        with self._lock:
            return {
                "total_exports": self.total_exports,
                "failed_exports": self.failed_exports,
                "active_exports": self.active_exports,
                "total_export_time_ms": self.total_export_time_ms,
                "error_rate_percent": self.get_error_rate_percent() if self.total_exports > 0 else 0.0,
                "avg_export_time_seconds": self.get_avg_export_time_seconds() if self.total_exports > 0 else 0.0,
                "uptime_seconds": self.get_uptime_seconds(),
            }


# Singleton instance
_strictdoc_metrics: StrictDocMetrics | None = None
_metrics_lock = threading.Lock()


def get_strictdoc_metrics() -> StrictDocMetrics:
    """Get the singleton StrictDocMetrics instance.

    Returns:
        The singleton StrictDocMetrics instance.
    """
    global _strictdoc_metrics
    with _metrics_lock:
        if _strictdoc_metrics is None:
            _strictdoc_metrics = StrictDocMetrics()
        return _strictdoc_metrics


def reset_strictdoc_metrics() -> None:
    """Reset the singleton metrics instance.

    Useful for testing to ensure a clean state.
    """
    global _strictdoc_metrics
    with _metrics_lock:
        _strictdoc_metrics = None
