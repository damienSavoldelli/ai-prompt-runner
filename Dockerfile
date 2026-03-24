FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

FROM base AS runtime

COPY pyproject.toml README.md LICENSE ./
COPY src ./src

RUN python3 -m pip install --upgrade pip && \
    python3 -m pip install .

RUN useradd --create-home --shell /bin/bash appuser && \
    mkdir -p /app/outputs && \
    chown -R appuser:appuser /app

USER appuser

ENTRYPOINT ["ai-prompt-runner"]
CMD ["--help"]

FROM base AS dev

COPY . .

RUN python3 -m pip install --upgrade pip && \
    python3 -m pip install -e ".[dev]"

CMD ["python3", "-m", "pytest"]
