set shell := ["bash", "-cu"]
set quiet := true


# --- Aliases ---

s: start


# --- Config ---

BUILD_IMAGE := "skillbot"
BUILD_TAG   := "local"

# A local skillcore checkout, for working on both at once (`start-local-core`).
SKILLCORE := "../skillcore"

_default:
  just -l


# --- Quality ---

lint:
  uv run ruff check

format-check:
  uv run ruff format --check

test:
  uv run pytest

# Everything that must be green before a push; CI's `check` job runs the same.
check: lint format-check test


# --- Distributing ---

# Builds the Docker image for production locally. skillcore is private: needs SKILLPLATFORM_READ_TOKEN.
build:
  test -n "${SKILLPLATFORM_READ_TOKEN:-}" || (echo 'Set SKILLPLATFORM_READ_TOKEN, for example: export SKILLPLATFORM_READ_TOKEN=$(gh auth token)' >&2; exit 1)

  echo "Building Docker image '{{BUILD_IMAGE}}:{{BUILD_TAG}}' ..."
  docker build --secret id=github_token,env=SKILLPLATFORM_READ_TOKEN -t {{BUILD_IMAGE}}:{{BUILD_TAG}} .

  echo "Docker image build complete."

# Removes the locally built Docker image.
clean-image:
  echo "Removing Docker image '{{BUILD_IMAGE}}:{{BUILD_TAG}}' ..."
  docker rmi {{BUILD_IMAGE}}:{{BUILD_TAG}} || true

  echo "Docker image removal complete."

# Cleans up everything created by the build process.
clean: clean-image
  echo "Cleanup complete."


# --- Development Helpers ---

# Start bot in development mode.
start:
  echo "Starting bot in development mode ..."
  echo ""

  uv run -m skillbot

# Start bot in development mode with command sync enabled.
start-synced:
  DISCORD__SYNC_COMMANDS=true just start

# Start bot in development mode with the local skillcore checkout instead of the pinned release.
start-local-core:
  echo "Starting bot in development mode with editable skillcore ..."
  echo ""

  uv run --with-editable {{SKILLCORE}} -m skillbot
