"""Tests for the StrictDoc service application module."""

import logging
from argparse import Namespace
from typing import Protocol

import pytest

from app.strictdoc_service_application import DEFAULT_PORT


class ArgumentParser(Protocol):
    """Protocol for argument parser."""

    def __init__(self, description: str) -> None:
        """Initialize argument parser."""
        ...

    def add_argument(self, option_string: str, **kwargs: dict) -> None:
        """Add argument to parser."""
        ...

    def parse_args(self) -> Namespace:
        """Parse arguments."""
        ...


def test_main_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the main function runs and starts the server."""

    # Mock argparse
    class MockArgumentParser:
        def __init__(self, description: str) -> None:
            pass

        def add_argument(self, option_string: str, **kwargs: dict) -> None:
            pass

        def parse_args(self) -> Namespace:
            class Args:
                port = DEFAULT_PORT
                log_level = "DEBUG"

            return Args()

    # Mock uvicorn.run
    server_started = False

    def mock_start_server(port: int) -> None:
        nonlocal server_started
        server_started = True
        assert port == DEFAULT_PORT

    monkeypatch.setattr("argparse.ArgumentParser", MockArgumentParser)
    monkeypatch.setattr("app.strictdoc_service_application.start_server", mock_start_server)

    # Run the main function
    from app.strictdoc_service_application import main

    main()

    # Verify that the server was started
    assert server_started


def test_configure_logging(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that logging is configured correctly."""
    # Import the module first to get access to the logger
    from app.strictdoc_service_application import logger

    # Mock environment variable
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")

    # Mock logging functions
    basicconfig_called = False
    logger_info_called = False

    def mock_basicconfig(level: int, **kwargs: dict) -> None:
        nonlocal basicconfig_called
        basicconfig_called = True
        assert level == logging.DEBUG

    def mock_logger_info(message_format: str, *args: list) -> None:
        nonlocal logger_info_called
        logger_info_called = True
        assert "Log level set to" in message_format

    monkeypatch.setattr("logging.basicConfig", mock_basicconfig)
    monkeypatch.setattr(logger, "info", mock_logger_info)

    # Configure logging
    from app.strictdoc_service_application import configure_logging

    configure_logging()

    # Verify that logging was configured correctly
    assert basicconfig_called
    assert logger_info_called

    # Test with ERROR level
    monkeypatch.setenv("LOG_LEVEL", "ERROR")
    basicconfig_called = False
    logger_info_called = False

    # Override mock functions for the ERROR level test
    def mock_basicconfig_error(level: int, **kwargs: dict) -> None:
        nonlocal basicconfig_called
        basicconfig_called = True
        assert level == logging.ERROR

    def mock_logger_info_error(message_format: str, *args: list) -> None:
        nonlocal logger_info_called
        logger_info_called = True
        assert "Log level set to" in message_format

    monkeypatch.setattr("logging.basicConfig", mock_basicconfig_error)
    monkeypatch.setattr(logger, "info", mock_logger_info_error)

    # Configure logging again with ERROR level
    configure_logging()

    # Verify that logging was configured correctly with ERROR level
    assert basicconfig_called
    assert logger_info_called


def test_start_service(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test starting the StrictDoc service."""
    server_started = False

    def mock_uvicorn_run(app, host, port, log_level):
        """Mock the uvicorn.run function."""
        nonlocal server_started
        server_started = True
        assert port == DEFAULT_PORT
        assert host == "0.0.0.0"
        assert log_level == "info"

    monkeypatch.setattr("uvicorn.run", mock_uvicorn_run)

    from app.strictdoc_service_application import start_service

    start_service(DEFAULT_PORT)
    assert server_started
