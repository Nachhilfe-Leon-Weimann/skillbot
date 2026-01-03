# syntax=docker/dockerfile:1

ARG PYTHON_VERSION=3.13-slim

# --- builder: installs deps deterministically via uv.lock ---
FROM python:${PYTHON_VERSION} AS builder
WORKDIR /app

# Install uv (build-time only)
RUN pip install --no-cache-dir uv

# Copy only dependency metadata first (better layer caching)
COPY pyproject.toml uv.lock README.md ./

# Copy vendored private deps (comes from GH Actions checkout)
COPY vendor/skillcore ./vendor/skillcore

# Copy source code
COPY src ./src

# Fix pyproject.toml to use local skillcore path
RUN python - <<'PY'
from pathlib import Path

p = Path("pyproject.toml")
txt = p.read_text(encoding="utf-8")

old = 'skillcore @ git+https://github.com/Nachhilfe-Leon-Weimann/skillcore.git@main'
new = 'skillcore @ file:///app/vendor/skillcore'

if old in txt:
    p.write_text(txt.replace(old, new), encoding="utf-8")
    print("Patched skillcore dependency to local path.")
else:
    print("No patch applied (pattern not found).")
PY

# Create venv at /app/.venv and install prod deps
RUN uv sync --no-dev

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