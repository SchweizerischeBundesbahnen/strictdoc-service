FROM python:3.13.4-alpine@sha256:b4d299311845147e7e47c970566906caf8378a1f04e5d3de65b5f2e834f8e3bf
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
