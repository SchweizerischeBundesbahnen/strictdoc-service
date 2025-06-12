#!/bin/bash
set -e

# Clean up any existing containers first
./clean_docker.sh

# Build and run Docker container
echo "Building and running Docker container for tests..."
docker build -t strictdoc-service:test .
docker run -d --name strictdoc_service_test -p 9083:9083 strictdoc-service:test

# Wait for container to be healthy
echo "Waiting for container to be healthy..."
attempt=1
max_attempts=10
until [ "$attempt" -gt "$max_attempts" ] || docker ps | grep strictdoc_service_test | grep -q "healthy"; do
    echo "Attempt $attempt/$max_attempts - Waiting for container to be healthy..."
    sleep 5
    ((attempt++))
done

if [ "$attempt" -gt "$max_attempts" ]; then
    echo "Container failed to become healthy after $max_attempts attempts"
    docker logs strictdoc_service_test
    ./clean_docker.sh
    exit 1
fi

echo "Container is healthy. Running tests..."

# Run tests
poetry run pytest tests --tb=short -v "$@"

# Clean up after tests
echo "Tests completed. Cleaning up Docker resources..."
./clean_docker.sh

echo "Testing completed successfully!"
