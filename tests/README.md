# StrictDoc Service Tests

This directory contains the test suite for the StrictDoc service.

## Directory Structure

- `export/`: Main test directory for export functionality
  - `conftest.py`: Shared fixtures for export tests
  - `test_unit.py`: Unit tests with mocked responses
  - `test_integration.py`: Integration tests with real Docker container

- `shell/`: Shell script tests for service functionality
  - Contains shell-based test scripts

- `container/`: Container configuration tests
  - `container-structure-test.yaml`: Docker container structure tests

- `scripts/`: Test helper scripts

- `test_strictdoc_controller.py`: FastAPI controller tests
- `test_strictdoc_service_application.py`: Service application tests

## Running Tests

### Quick Test Run

Run all tests
```bash
uv run pytest
```
Run specific test file
```bash
uv run pytest tests/export/test_unit.py -v
```
Run with coverage
```bash
uv run pytest --cov=app tests/ --cov-report=term-missing
```
Run all tests with tox
```bash
uv run tox
```

### Docker-based Testing

Smoke test suite in Docker environment
```bash
cd ..
./tests/shell/test_strictdoc_service.sh
```


Container structure tests
```bash
cd ..
container-structure-test test --image strictdoc-service:local --config ./tests/container/container-structure-test.yaml
```

## Test Organization

1. **Export Tests** (`tests/export/`):
   - `conftest.py`: Shared fixtures and utilities
     - Docker container setup/teardown
     - Test parameters
     - Session management
     - Common test data
   - `test_unit.py`: Unit tests
     - Mocked responses
     - Export format tests
     - PDF export tests
     - Error handling tests
     - Input validation
   - `test_integration.py`: Integration tests
     - Real Docker container
     - Version endpoint tests
     - Export format tests
     - Content validation
     - Error handling
     - Connection error handling

2. **Controller Tests** (`test_strictdoc_controller.py`):
   - FastAPI endpoint tests
   - Request validation
   - Response formatting
   - Error handling

3. **Service Tests** (`test_strictdoc_service_application.py`):
   - Application configuration
   - Service lifecycle
   - Environment handling

## Best Practices

1. **Test Organization**:
   - Group tests by functionality
   - Use descriptive test names
   - Follow Arrange-Act-Assert pattern
   - Keep tests independent
   - Use appropriate fixtures
   - Maintain test data separately

2. **Code Quality**:
   - Run pre-commit hooks before commits
   - Maintain high test coverage
   - Address all linter warnings
   - Document test requirements
   - Review test code thoroughly
   - Keep tests simple and readable

3. **Test Data**:
   - Use fixtures for common data
   - Keep test data in separate files
   - Use meaningful sample data
   - Clean up test data after use

4. **Docker Testing**:
   - Use clean containers for tests
   - Test both success and failure cases
   - Verify container health
   - Clean up resources after tests
