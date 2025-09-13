# Builder stage
FROM python:3.13.7-slim@sha256:58c30f5bfaa718b5803a53393190b9c68bd517c44c6c94c1b6c8c172bcfad040 AS builder
WORKDIR /app

# Install build dependencies
COPY requirements.txt .
# hadolint ignore=DL3008
RUN apt-get update && \
    apt-get install --no-install-recommends -y \
        gcc \
        python3-dev \
        libffi-dev \
        libssl-dev \
    && pip install --no-cache-dir -r requirements.txt \
    && poetry config virtualenvs.create false \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy only dependency files
COPY pyproject.toml poetry.lock ./
RUN poetry install --no-root --only main

# Final stage
FROM python:3.13.7-slim@sha256:58c30f5bfaa718b5803a53393190b9c68bd517c44c6c94c1b6c8c172bcfad040
LABEL maintainer="SBB Polarion Team <polarion-opensource@sbb.ch>" \
      org.opencontainers.image.title="StrictDoc Service" \
      org.opencontainers.image.description="API service for StrictDoc document processing" \
      org.opencontainers.image.vendor="SBB"

# hadolint ignore=DL3008
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install --no-install-recommends --yes \
    curl \
    && apt-get clean autoclean \
    && apt-get --yes autoremove \
    && rm -rf /var/lib/apt/lists/*

ARG APP_IMAGE_VERSION=0.0.0
ENV WORKING_DIR="/opt/strictdoc" \
    STRICTDOC_SERVICE_VERSION=${APP_IMAGE_VERSION}
ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=${WORKING_DIR} \
    PORT=9083 \
    LOG_LEVEL=INFO

WORKDIR ${WORKING_DIR}

RUN BUILD_TIMESTAMP="$(date -u +'%Y-%m-%dT%H:%M:%SZ')" && \
    echo "${BUILD_TIMESTAMP}" > "${WORKING_DIR}/.build_timestamp"

# Copy Python dependencies from builder stage
COPY --from=builder /usr/local/lib/python3.13/site-packages/ /usr/local/lib/python3.13/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/

# Copy application code
COPY ./app/*.py ${WORKING_DIR}/app/
COPY entrypoint.sh ${WORKING_DIR}/entrypoint.sh
RUN chmod +x ${WORKING_DIR}/entrypoint.sh

# Create and use non-root user
RUN useradd -m appuser && \
    chown -R appuser:appuser ${WORKING_DIR} && \
    mkdir -p /tmp/strictdoc && \
    chown -R appuser:appuser /tmp/strictdoc
USER appuser

# Verify StrictDoc is installed and working
RUN strictdoc --version

EXPOSE ${PORT}

# Add healthcheck
HEALTHCHECK --interval=5s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:${PORT}/version || exit 1

ENTRYPOINT ["./entrypoint.sh"]

# Security labels
LABEL org.opencontainers.image.security.caps.drop="ALL"
LABEL org.opencontainers.image.security.no-new-privileges="true"
