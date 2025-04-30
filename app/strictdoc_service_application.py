"""StrictDoc service application module."""

import argparse
import logging
import os
import sys

# Create a custom logger
logger = logging.getLogger(__name__)

# Constants
DEFAULT_PORT = 9083


def configure_logging() -> None:
    """Configure logging based on environment variable."""
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stdout,
    )
    logger.info("Log level set to %s", log_level)


# Configure logging when this module is imported
configure_logging()
logger.info("StrictDoc service initialized")

# The app variable is imported from strictdoc_controller
from app.strictdoc_controller import start_server  # noqa: E402


def start_service(port: int) -> None:
    """Start the StrictDoc service."""
    logger.info("Starting StrictDoc service on port %s", port)
    start_server(port)


def main() -> None:
    """Start the StrictDoc service.

    Parses command line arguments and starts the service with the specified port.
    """
    parser = argparse.ArgumentParser(description="StrictDoc service")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port to run the service on")
    parser.add_argument("--log-level", type=str, default="INFO", help="Logging level")
    args = parser.parse_args()

    start_service(args.port)
