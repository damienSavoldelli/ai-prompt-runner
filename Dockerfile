ARG PYTHON_BASE_IMAGE=python:3.11-slim@sha256:9358444059ed78e2975ada2c189f1c1a3144a5dab6f35bff8c981afb38946634
FROM ${PYTHON_BASE_IMAGE} AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Use a non-root runtime user with a fixed UID for safer volume permissions.
RUN useradd --create-home --shell /bin/bash --uid 10001 appuser && \
    mkdir -p /app/outputs && \
    chown -R appuser:appuser /app

FROM base AS runtime

COPY pyproject.toml README.md LICENSE ./
COPY src ./src

RUN python3 -m pip install --upgrade pip && \
    python3 -m pip install --no-compile .

USER appuser

ENTRYPOINT ["ai-prompt-runner"]
CMD ["--help"]

FROM base AS dev

COPY . .

RUN python3 -m pip install --upgrade pip && \
    python3 -m pip install -e ".[dev]"

CMD ["python3", "-m", "pytest"]
