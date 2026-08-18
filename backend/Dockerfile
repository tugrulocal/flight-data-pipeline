FROM python:3.14.7-alpine3.23@sha256:6b8f06d04d5305c1d1288435388df9165ab41e681fae6439d6349d8053cc3f83 AS wheel-builder

WORKDIR /build

COPY requirements-build.txt ./requirements-build.txt
COPY backend/requirements.txt ./requirements.txt

RUN apk add --no-cache gcc musl-dev librdkafka-dev=2.12.1-r0 \
    && pip install --disable-pip-version-check --root-user-action=ignore \
        --no-cache-dir --require-hashes -r requirements-build.txt \
    && pip wheel --disable-pip-version-check --no-cache-dir \
        --no-build-isolation --require-hashes -r requirements.txt \
        --wheel-dir /wheels

FROM python:3.14.7-alpine3.23@sha256:6b8f06d04d5305c1d1288435388df9165ab41e681fae6439d6349d8053cc3f83

ARG APP_VERSION=dev
ARG VCS_REF=unknown
LABEL org.opencontainers.image.title="Flight Data Pipeline Backend" \
      org.opencontainers.image.version="${APP_VERSION}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.source="https://github.com/tugrulocal/flight-data-pipeline"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY backend/requirements.txt ./requirements.txt

RUN --mount=type=bind,from=wheel-builder,source=/wheels,target=/wheels \
    apk add --no-cache librdkafka=2.12.1-r0 \
    && pip install --disable-pip-version-check --root-user-action=ignore \
        --no-cache-dir --no-index --no-deps /wheels/*.whl \
    && addgroup -g 10001 appgroup \
    && adduser -D -u 10001 -G appgroup appuser

COPY --chown=appuser:appuser backend/app ./app
COPY --chown=appuser:appuser flight_common ./flight_common

USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
