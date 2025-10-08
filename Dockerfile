# Red Hat Universal Base Image (UBI) - glibc-based, pre-compiled wheels work!
FROM registry.access.redhat.com/ubi9/ubi-minimal:9.6-1758184547@sha256:7c5495d5fad59aaee12abc3cbbd2b283818ee1e814b00dbc7f25bf2d14fa4f0c

ARG APP_IMAGE_VERSION=0.0.0
ENV WORKING_DIR="/opt/strictdoc" \
    STRICTDOC_SERVICE_VERSION=${APP_IMAGE_VERSION} \
    PYTHONUNBUFFERED=1 \
    PORT=9083 \
    LOG_LEVEL=INFO

WORKDIR ${WORKING_DIR}

# Copy uv from official image
COPY --from=ghcr.io/astral-sh/uv:latest@sha256:8f926a80debadba6f18442030df316c0e2b28d6af62d1292fb44b1c874173dc0 /uv /usr/local/bin/uv

# Install runtime dependencies using microdnf (UBI minimal)
# Note: curl-minimal is already installed, shadow-utils provides useradd
# hadolint ignore=DL3041
RUN microdnf install -y \
        ca-certificates \
        shadow-utils \
    && microdnf clean all

# Copy Python version file and dependency files
COPY .python-version pyproject.toml uv.lock ./

# Install Python via uv to /opt/python (version from .python-version file)
ENV UV_PYTHON_INSTALL_DIR=/opt/python
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
RUN PYTHON_VERSION=$(cat .python-version) && \
    uv python install "${PYTHON_VERSION}"

# Install dependencies with cache mount
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Create build timestamp
RUN BUILD_TIMESTAMP="$(date -u +'%Y-%m-%dT%H:%M:%SZ')" && \
    echo "${BUILD_TIMESTAMP}" > "${WORKING_DIR}/.build_timestamp"

# Copy application code
COPY ./app/*.py ${WORKING_DIR}/app/
COPY entrypoint.sh ${WORKING_DIR}/entrypoint.sh
RUN chmod +x ${WORKING_DIR}/entrypoint.sh

# Add venv to PATH
ENV PATH="/opt/strictdoc/.venv/bin:$PATH" \
    PYTHONPATH=${WORKING_DIR}

# Verify StrictDoc is installed and working
RUN strictdoc --version

# Create and configure non-root user
# Make Python installation readable by all users
RUN chmod -R a+rX /opt/python && \
    chmod -R a+rx ${WORKING_DIR}/.venv/bin && \
    useradd -u 1000 -m -s /bin/bash appuser && \
    chown -R appuser:appuser ${WORKING_DIR} && \
    mkdir -p /tmp/strictdoc && \
    chown -R appuser:appuser /tmp/strictdoc

# Switch to non-root user
USER appuser

EXPOSE ${PORT}

# Healthcheck
HEALTHCHECK --interval=5s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:${PORT}/version || exit 1

ENTRYPOINT ["./entrypoint.sh"]

# Security and metadata labels
LABEL maintainer="SBB Polarion Team <polarion-opensource@sbb.ch>" \
      org.opencontainers.image.title="StrictDoc Service (UBI)" \
      org.opencontainers.image.description="API service for StrictDoc document processing" \
      org.opencontainers.image.vendor="SBB" \
      org.opencontainers.image.security.caps.drop="ALL" \
      org.opencontainers.image.security.no-new-privileges="true"
