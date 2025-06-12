"""Test configuration and fixtures."""

import logging
import time
from collections.abc import Generator
from dataclasses import dataclass
from http import HTTPStatus

import docker
import pytest
import requests
from _pytest.fixtures import FixtureRequest
from docker.errors import DockerException
from fastapi.testclient import TestClient

from app.strictdoc_controller import app

# Create a custom logger
logger = logging.getLogger(__name__)


@dataclass
class TestParameters:
    """Test parameters for integration tests."""

    base_url: str
    request_session: requests.Session
    __test__ = False  # Tell pytest this is not a test class


@pytest.fixture(scope="session")
def docker_setup() -> Generator[bool]:
    """Set up Docker container for testing.

    Checks if container is already running before creating a new one.

    Yields:
        True if setup was successful

    """
    client = docker.from_env()
    container_name = "strictdoc-service-test"
    container = None
    container_running = False

    try:
        # Check for existing container
        existing_containers = client.containers.list(all=True, filters={"name": container_name})
        if existing_containers:
            container = existing_containers[0]
            logger.info("Found existing container %s with status: %s", container_name, container.status)

            if container.status == "running":
                container_running = True
                logger.info("Using existing running container %s", container_name)
            else:
                # Remove the stopped container
                logger.info("Removing existing stopped container %s", container_name)
                container.remove(force=True)
    except DockerException as e:
        logger.exception("Error checking for existing container: %s", str(e))
        raise

    # Build and start the container if it's not already running
    if not container_running:
        try:
            # Build the image
            client.images.build(
                path=".",
                dockerfile="Dockerfile",
                tag="strictdoc-service:test",
                rm=True,
                forcerm=True,
            )

            # Start the container
            container = client.containers.run(
                "strictdoc-service:test",
                name=container_name,
                ports={"9083/tcp": 9083},
                detach=True,
            )

            # Wait for the service to start
            max_retries = 30
            retry_interval = 1
            for _ in range(max_retries):
                time.sleep(retry_interval)
                try:
                    response = requests.get("http://localhost:9083/version", timeout=2)
                    if response.status_code == HTTPStatus.OK:
                        logger.info("StrictDoc service started successfully")
                        break
                except requests.RequestException:
                    continue
            else:
                if container:
                    logs = container.logs().decode("utf-8")
                    logger.error("Container logs: %s", logs)
                    container.stop()
                pytest.skip("StrictDoc service failed to start")
        except DockerException as e:
            logger.exception("Failed to start docker container: %s", str(e))
            pytest.skip(f"Failed to start docker container: {e}")

    yield True

    # Cleanup after tests
    if container:
        try:
            if container:
                logger.info("Stopping container %s", container_name)
                container.stop()

            # Remove the test image
            logger.info("Removing test image")
            client.images.remove("strictdoc-service:test", force=True)
        except DockerException as e:
            logger.exception("Error during cleanup: %s", str(e))
            raise


@pytest.fixture(scope="session")
def test_parameters(docker_setup: bool, request: FixtureRequest) -> Generator[TestParameters]:
    """Set up test parameters and request session.

    Args:
        docker_setup: Docker setup fixture
        request: Pytest fixture request object

    Yields:
        The setup test parameters

    """
    base_url = "http://localhost:9083"
    session = requests.Session()
    test_params = TestParameters(base_url=base_url, request_session=session)

    yield test_params

    session.close()


@pytest.fixture
def valid_sdoc_content() -> str:
    """Provide a minimal valid SDOC document for testing."""
    return """[DOCUMENT]
TITLE: Test Document

[SECTION]
TITLE: Test Section

[REQUIREMENT]
UID: REQ-001
STATEMENT: >>>
This is a test requirement
<<<
"""


@pytest.fixture
def test_client() -> TestClient:
    """Create a test client for FastAPI application."""
    return TestClient(app)
