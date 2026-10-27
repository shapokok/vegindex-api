# syntax=docker/dockerfile:1

ARG PYTHON_IMAGE=python:3.12-slim
ARG UV_VERSION=0.12.16

FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv

# --- base: production dependencies + the package, installed into /opt/venv ----
FROM ${PYTHON_IMAGE} AS base

COPY --from=uv /uv /usr/local/bin/uv

ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_PYTHON_DOWNLOADS=never \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencies first so this layer is cached until uv.lock changes.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project

# Then the package itself, installed non-editable so the venv is self-contained.
COPY README.md LICENSE ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable

# --- test: dev dependencies, lint and test suite ------------------------------
FROM base AS test

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-editable

COPY tests ./tests

RUN ruff check . \
    && ruff format --check . \
    && mkdir -p /reports \
    && pytest --junitxml=/reports/junit.xml

# --- runtime: only the virtualenv, non-root ------------------------------------
FROM ${PYTHON_IMAGE} AS runtime

RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app

COPY --from=base /opt/venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Declared late so a new commit does not invalidate the layers above.
ARG GIT_COMMIT=unknown
ENV GIT_COMMIT=${GIT_COMMIT}
LABEL org.opencontainers.image.source="https://github.com/shapokok/vegindex-api" \
      org.opencontainers.image.revision="${GIT_COMMIT}" \
      org.opencontainers.image.licenses="MIT"

USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"]

CMD ["uvicorn", "vegindex.api:app", "--host", "0.0.0.0", "--port", "8000"]
