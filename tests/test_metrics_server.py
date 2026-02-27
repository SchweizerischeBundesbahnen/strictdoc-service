"""Tests for the dedicated metrics server."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.metrics_server import MetricsServer, get_metrics, health_check, metrics_app
from app.strictdoc_metrics import get_strictdoc_metrics, reset_strictdoc_metrics


@pytest.fixture(autouse=True)
def reset_metrics():
    """Reset internal metrics before each test."""
    reset_strictdoc_metrics()
    yield
    reset_strictdoc_metrics()


@pytest.fixture
def metrics_client():
    """Create a test client for the metrics app."""
    return TestClient(metrics_app)


class TestMetricsEndpoint:
    """Tests for the /metrics endpoint."""

    def test_metrics_endpoint_returns_prometheus_format(self, metrics_client):
        """Test that /metrics returns Prometheus-formatted metrics."""
        response = metrics_client.get("/metrics")
        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]

        # Check for expected metric names in output
        content = response.text
        assert "strictdoc_exports_total" in content
        assert "strictdoc_export_failures_total" in content
        assert "strictdoc_export_duration_seconds" in content
        assert "uptime_seconds" in content

    def test_metrics_endpoint_updates_gauges(self, metrics_client):
        """Test that metrics endpoint updates gauge values."""
        metrics = get_strictdoc_metrics()
        metrics.record_export_start()
        metrics.record_export_success(500.0)

        response = metrics_client.get("/metrics")
        content = response.text

        # Gauges should reflect the recorded metrics
        assert "avg_strictdoc_export_time_seconds 0.5" in content
        assert "strictdoc_export_error_rate_percent 0.0" in content


class TestHealthEndpoint:
    """Tests for the /health endpoint."""

    def test_health_endpoint_returns_healthy(self, metrics_client):
        """Test that /health returns healthy status."""
        response = metrics_client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}


class TestMetricsServer:
    """Tests for MetricsServer class."""

    @pytest.mark.asyncio
    async def test_server_initialization(self):
        """Test that MetricsServer initializes with correct port."""
        server = MetricsServer(port=9999)
        assert server.port == 9999
        assert server._task is None

    @pytest.mark.asyncio
    async def test_server_start_disabled(self):
        """Test that server doesn't start when disabled."""
        with patch("app.metrics_server.METRICS_SERVER_ENABLED", False):
            server = MetricsServer()
            await server.start()
            assert server._task is None

    @pytest.mark.asyncio
    async def test_server_stop_when_not_started(self):
        """Test that stopping a non-started server doesn't raise errors."""
        server = MetricsServer()
        await server.stop()  # Should not raise

    @pytest.mark.asyncio
    async def test_server_lifecycle(self):
        """Test server start and stop lifecycle."""
        with patch("app.metrics_server.METRICS_SERVER_ENABLED", True):
            with patch("uvicorn.Server") as mock_server_class:
                mock_server = AsyncMock()
                mock_server_class.return_value = mock_server

                server = MetricsServer(port=19183)

                # Start server
                await server.start()
                assert server._task is not None

                # Stop server
                await server.stop()
                assert server._task is None


class TestMetricsServerConfiguration:
    """Tests for metrics server configuration."""

    def test_default_port(self):
        """Test default metrics port."""
        from app.metrics_server import DEFAULT_METRICS_PORT
        assert DEFAULT_METRICS_PORT == 9183

    def test_port_validation(self):
        """Test that invalid port falls back to default."""
        with patch.dict("os.environ", {"METRICS_PORT": "70000"}):
            # Re-import to pick up new env var
            import importlib
            import app.metrics_server
            importlib.reload(app.metrics_server)

            # Port should be validated to default
            assert app.metrics_server.METRICS_PORT == 9183

            # Reload again to restore normal state
            importlib.reload(app.metrics_server)


class TestAsyncEndpoints:
    """Tests for async endpoint behavior."""

    @pytest.mark.asyncio
    async def test_get_metrics_async(self):
        """Test get_metrics endpoint directly."""
        response = await get_metrics()
        assert response.status_code == 200
        assert b"strictdoc" in response.body

    @pytest.mark.asyncio
    async def test_health_check_async(self):
        """Test health_check endpoint directly."""
        result = await health_check()
        assert result == {"status": "healthy"}
