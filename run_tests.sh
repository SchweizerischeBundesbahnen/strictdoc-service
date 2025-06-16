#!/bin/bash
set -e

# Install dependencies if needed
poetry install --no-root

# Run the tests with optimized settings for speed
# --tb=short: short traceback format
# -v: verbose output
poetry run pytest tests --tb=short -v "$@"

# Clean up Docker resources after tests
echo "Tests completed. Cleaning up Docker resources..."
./clean_docker.sh
