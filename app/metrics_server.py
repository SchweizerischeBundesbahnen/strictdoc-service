"""Dedicated metrics server for Prometheus scraping.

This module provides a separate FastAPI server for serving Prometheus metrics
on a dedicated port, keeping metrics separate from the main application.
"""

import asyncio
import contextlib
import logging
import os

import uvicorn
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.prometheus_metrics import update_gauges_from_strictdoc_metrics

logger = logging.getLogger(__name__)

# Environment variables for configuration
DEFAULT_METRICS_PORT = 9183
METRICS_SERVER_ENABLED = os.getenv("METRICS_SERVER_ENABLED", "true").lower() == "true"

# Parse METRICS_PORT with error handling for non-integer values
MIN_PORT = 1
MAX_PORT = 65535

try:
    METRICS_PORT = int(os.getenv("METRICS_PORT", str(DEFAULT_METRICS_PORT)))
except ValueError:
    logger.warning("Invalid METRICS_PORT value, using default %d", DEFAULT_METRICS_PORT)
    METRICS_PORT = DEFAULT_METRICS_PORT

# Validate port range
if not MIN_PORT <= METRICS_PORT <= MAX_PORT:
    logger.warning("Invalid METRICS_PORT %d, using default %d", METRICS_PORT, DEFAULT_METRICS_PORT)
    METRICS_PORT = DEFAULT_METRICS_PORT

# Create a minimal FastAPI app for metrics only
metrics_app = FastAPI(
    title="StrictDoc Metrics",
    description="Prometheus metrics endpoint",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


@metrics_app.get("/metrics", response_class=PlainTextResponse)
async def get_metrics() -> PlainTextResponse:
    """Serve Prometheus metrics.

    Returns:
        PlainTextResponse: Prometheus metrics in text format.
    """
    # Update gauge values from internal metrics before generating output
    update_gauges_from_strictdoc_metrics()
    return PlainTextResponse(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@metrics_app.get("/health")
async def health_check() -> dict[str, str]:
    """Simple health check endpoint.

    Returns:
        dict: Health status.
    """
    return {"status": "healthy"}


class MetricsServer:
    """Manages the lifecycle of the dedicated metrics server."""

    def __init__(self, port: int = METRICS_PORT) -> None:
        """Initialize the metrics server.

        Args:
            port: Port to run the metrics server on.
        """
        self.port = port
        self._server: uvicorn.Server | None = None
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Start the metrics server asynchronously."""
        if not METRICS_SERVER_ENABLED:
            logger.info("Metrics server disabled via METRICS_SERVER_ENABLED=false")
            return

        try:
            config = uvicorn.Config(
                metrics_app,
                host="0.0.0.0",  # noqa: S104 - Intentional binding for container environments
                port=self.port,
                log_level="warning",
            )
            self._server = uvicorn.Server(config)

            # Start server in background task
            self._task = asyncio.create_task(self._server.serve())
            # Yield control to allow the server task to start
            await asyncio.sleep(0)
            logger.info("Metrics server started on port %d", self.port)

        except OSError as e:
            logger.exception("Failed to start metrics server on port %d: %s", self.port, e)
            raise

    async def stop(self) -> None:
        """Stop the metrics server gracefully."""
        if self._server is not None:
            # Signal uvicorn to exit gracefully (allows proper cleanup)
            self._server.should_exit = True

        if self._task is not None:
            try:
                # Wait for the server to shut down with a timeout
                await asyncio.wait_for(self._task, timeout=5.0)
            except TimeoutError:
                # Force cancel if graceful shutdown takes too long
                self._task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    _ = await self._task  # type: ignore[func-returns-value]  # noqa: B905, F841
            self._task = None
            self._server = None
            logger.info("Metrics server stopped")
