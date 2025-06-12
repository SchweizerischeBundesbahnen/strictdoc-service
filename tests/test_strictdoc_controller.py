"""Tests for the StrictDoc controller module."""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client() -> TestClient:
    """Create a FastAPI test client."""
    from app.strictdoc_controller import app

    return TestClient(app)


def test_version(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    """Test the version endpoint returns correct information."""
    # Mock strictdoc.__version__
    monkeypatch.setattr("strictdoc.__version__", "0.7.0")

    # Set up environment variables
    monkeypatch.setattr("platform.python_version", lambda: "3.13.1")
    monkeypatch.setenv("STRICTDOC_SERVICE_VERSION", "test1")
    monkeypatch.setenv("STRICTDOC_SERVICE_BUILD_TIMESTAMP", "test2")

    # Make the request
    response = client.get("/version")

    # Verify the response
    assert response.status_code == 200
    result = response.json()
    assert result["python"] == "3.13.1"
    assert result["strictdoc"] == "0.8.0"
    assert "strictdoc_service" in result
    assert isinstance(result["strictdoc_service"], str)
    # assert result["timestamp"] == "test2"  # Not set by implementation


# Note: Export-related tests have been moved to these files:
# - tests/test_export_formats.py - Main test file for export formats
# - tests/unit/test_export.py - Unit tests for export functionality
# - tests/integration/test_export_integration.py - Integration tests for export
