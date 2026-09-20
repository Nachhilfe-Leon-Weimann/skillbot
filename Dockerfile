# syntax=docker/dockerfile:1.7

FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder

ENV GIT_TERMINAL_PROMPT=0 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock README.md ./

# skillcore is a private git dependency: the token is only there while this layer builds. --locked fails the
# build on a stale uv.lock instead of producing an image that cannot start.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=secret,id=github_token,required=true \
    set -eu; \
    github_token="$(cat /run/secrets/github_token)"; \
    git config --global url."https://x-access-token:${github_token}@github.com/".insteadOf "https://github.com/"; \
    uv sync --locked --no-dev --no-install-project; \
    git config --global --unset-all url."https://x-access-token:${github_token}@github.com/".insteadOf

COPY src ./src

FROM python:3.13-slim-bookworm AS runtime

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONPATH="/app/src" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN useradd --create-home --shell /usr/sbin/nologin skillbot

COPY --from=builder --chown=skillbot:skillbot /app/.venv ./.venv
COPY --from=builder --chown=skillbot:skillbot /app/src ./src

RUN mkdir -p /app/logs && chown -R skillbot:skillbot /app

USER skillbot

CMD ["python", "-m", "skillbot"]
