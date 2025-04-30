#!/bin/sh
set -e

# Use environment variables with defaults already set in Dockerfile
BUILD_TIMESTAMP="$(cat /opt/strictdoc/.build_timestamp)"
export STRICTDOC_SERVICE_BUILD_TIMESTAMP=${BUILD_TIMESTAMP}

echo "Starting StrictDoc service on port $PORT with log level $LOG_LEVEL"

# Convert log level to lowercase for uvicorn
LOG_LEVEL_LOWER=$(echo "$LOG_LEVEL" | tr '[:upper:]' '[:lower:]')

# Execute the service application with uvicorn for FastAPI
exec uvicorn app.strictdoc_controller:app --host 0.0.0.0 --port $PORT --log-level $LOG_LEVEL_LOWER
