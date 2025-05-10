FROM python:3.13.3-alpine@sha256:452682e4648deafe431ad2f2391d726d7c52f0ff291be8bd4074b10379bb89ff
LABEL maintainer="SBB Polarion Team <polarion-opensource@sbb.ch>"

ARG WORKING_DIR=/app
ARG APP_IMAGE_VERSION=0.0.0

WORKDIR ${WORKING_DIR}

COPY requirements.txt ${WORKING_DIR}/requirements.txt
COPY ./app/ ${WORKING_DIR}/app/
COPY ./poetry.lock ${WORKING_DIR}
COPY ./pyproject.toml ${WORKING_DIR}

RUN pip install --no-cache-dir -r "${WORKING_DIR}"/requirements.txt && \
    poetry install --no-root && \
    poetry env activate

ENTRYPOINT [ "poetry", "run", "python", "-m", "app.app" ]
