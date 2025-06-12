#!/bin/bash
set -e

echo "Cleaning up Docker resources for StrictDoc service..."

# Stop and remove container
echo "Stopping and removing strictdoc_service_test container..."
docker stop strictdoc_service_test 2>/dev/null || echo "No container to stop"
docker rm strictdoc_service_test 2>/dev/null || echo "No container to remove"

# Remove test image
echo "Removing strictdoc-service:test image..."
docker rmi strictdoc-service:test 2>/dev/null || echo "No image to remove"

# Optional: Remove dangling images (uncomment if needed)
# echo "Removing dangling images..."
# docker image prune -f

echo "Cleanup complete!"
