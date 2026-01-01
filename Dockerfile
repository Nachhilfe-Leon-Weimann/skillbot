# syntax=docker/dockerfile:1

ARG PYTHON_VERSION=3.13-slim

# --- builder: installs deps deterministically via uv.lock ---
FROM python:${PYTHON_VERSION} AS builder
WORKDIR /app

# Install uv (build-time only)
RUN pip install --no-cache-dir uv

# Copy only dependency metadata first (better layer caching)
COPY pyproject.toml uv.lock ./

# Copy source code
COPY src ./src

# Create venv at /app/.venv and install prod deps
RUN uv sync --frozen --no-dev

# --- runtime: minimal image, no uv needed ---
FROM python:${PYTHON_VERSION} AS runtime
WORKDIR /app

# Copy the virtual environment and app code
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src

# Use the venv by default
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

ENV PYTHONPATH="/app/src"

# Start bot
CMD ["python", "-m", "skillbot"]