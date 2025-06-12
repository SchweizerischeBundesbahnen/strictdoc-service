"""Export test configuration and fixtures."""

import logging
import time
from collections.abc import Generator
from http import HTTPStatus

import docker
import pytest
import requests
from docker.errors import DockerException
from fastapi.testclient import TestClient

from app.strictdoc_controller import app

# Create a custom logger
logger = logging.getLogger(__name__)


class TestParameters:
    """Test parameters class."""

    __test__ = False  # Prevent pytest from collecting this class as a test

    def __init__(self, base_url: str, request_session: requests.Session) -> None:
        """Initialize test parameters.

        Args:
            base_url: Base URL for the service
            request_session: Session for making HTTP requests

        """
        self.base_url = base_url
        self.request_session = request_session


@pytest.fixture
def client() -> TestClient:
    """Create a FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def sample_sdoc() -> str:
    """Create a sample SDOC document for testing."""
    return """[DOCUMENT]
TITLE: Test Document

[SECTION]
TITLE: Test Section

[REQUIREMENT]
UID: REQ-001
STATUS: Draft
TITLE: First Requirement
STATEMENT: >>>
This is a test requirement
<<<

[REQUIREMENT]
UID: REQ-002
STATUS: Approved
TITLE: Second Requirement
STATEMENT: >>>
This is another test requirement
<<<

[/SECTION]
"""


@pytest.fixture(scope="session")
def docker_setup() -> Generator[bool]:
    """Set up Docker container for testing.

    Checks if container is already running before creating a new one.

    Yields:
        bool: True if setup was successful, False otherwise

    """
    client = None
    container_name = "strictdoc-service-test"
    container = None
    container_running = False

    try:
        client = docker.from_env()
    except DockerException as e:
        raise RuntimeError(f"Failed to connect to Docker: {e!s}") from e

    try:
        # Always stop and remove existing container to get a fresh one
        existing_containers = client.containers.list(all=True, filters={"name": container_name})
        if existing_containers:
            container = existing_containers[0]
            logger.info("Found existing container %s with status: %s", container_name, container.status)

            if container.status == "running":
                logger.info("Stopping existing container %s", container_name)
                container.stop()

            logger.info("Removing existing container %s", container_name)
            container.remove(force=True)
    except DockerException as e:
        logger.exception("Error checking for existing container: %s", str(e))
        raise RuntimeError(f"Error checking for existing container: {e!s}") from e

    # Build and start a new container
    try:
        # Check and remove temporary files that might cause build issues
        from pathlib import Path

        # Clean up any previous test files in the project root
        for temp_file in Path().glob("test-export*"):
            if temp_file.is_file():
                logger.info(f"Removing temporary file: {temp_file}")
                temp_file.unlink()

        # Build the image
        logger.info("Building Docker image strictdoc-service:test")
        try:
            client.images.build(
                path=".",
                dockerfile="Dockerfile",
                tag="strictdoc-service:test",
                rm=True,
                forcerm=True,
                nocache=True,  # Don't use cache to get a fresh build
            )
        except Exception as e:
            logger.error(f"Failed to build Docker image: {e}")
            raise RuntimeError(f"Docker image build failed: {e}") from e

        # Start the container
        logger.info("Starting strictdoc-service container")
        container = client.containers.run(
            "strictdoc-service:test",
            name=container_name,
            ports={"9083/tcp": 9083},
            detach=True,
        )

        # Wait for the service to start
        max_retries = 30
        retry_interval = 1
        for attempt in range(max_retries):
            logger.info("Waiting for service to start (attempt %d/%d)", attempt + 1, max_retries)
            time.sleep(retry_interval)
            try:
                response = requests.get("http://localhost:9083/version", timeout=2)
                if response.status_code == HTTPStatus.OK:
                    logger.info("StrictDoc service started successfully")
                    container_running = True
                    break
            except requests.RequestException:
                continue
        else:
            if container:
                logs = container.logs().decode("utf-8")
                logger.error("Container logs: %s", logs)
                container.stop()
            error_msg = f"StrictDoc service failed to start after {max_retries} attempts"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
    except DockerException as e:
        error_msg = f"Failed to start docker container: {e!s}"
        logger.exception(error_msg)
        raise RuntimeError(error_msg) from e

    yield container_running

    # Cleanup after tests
    if container:
        try:
            logger.info("Stopping container %s", container_name)
            container.stop()

            # Remove the test image
            try:
                logger.info("Removing test image")
                client.images.remove("strictdoc-service:test", force=True)
            except Exception as e:
                logger.warning(f"Failed to remove test image: {e}")
        except DockerException as e:
            logger.exception("Error during cleanup: %s", str(e))
            raise


@pytest.fixture(scope="session")
def test_parameters(docker_setup: bool) -> Generator[TestParameters]:
    """Set up test parameters and request session.

    Args:
        docker_setup: Docker setup fixture that ensures container is running

    Yields:
        TestParameters: The setup test parameters

    """
    # Docker setup must be successful
    assert docker_setup, "Docker setup was not successful"

    # Verify the service is accessible
    base_url = "http://localhost:9083"
    session = requests.Session()

    # Check if the service is actually running
    try:
        response = session.get(f"{base_url}/version", timeout=5)
        assert response.status_code == HTTPStatus.OK, f"StrictDoc service not available (status code: {response.status_code})"
    except requests.RequestException as e:
        raise RuntimeError(f"StrictDoc service not accessible: {e}") from e

    test_params = TestParameters(base_url=base_url, request_session=session)

    yield test_params

    session.close()
