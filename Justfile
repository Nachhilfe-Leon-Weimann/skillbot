set shell := ["bash", "-cu"]
set quiet := true


# --- Aliases ---

s: start


# --- Config ---

BUILD_IMAGE := "skillbot"
BUILD_TAG   := "local"

_default:
  just -l


# --- Distributing ---

# Sets up the vendor directory.
vendor:
  set -euo pipefail

  echo "Removing existing vendor directory ..."
  rm -rf vendor

  echo "Cloning latest skillcore release from GitHub ..."
  git clone -q --depth 1 git@github.com:Nachhilfe-Leon-Weimann/skillcore.git vendor/skillcore

  echo "Vendor setup complete."

# Cleans up the vendor directory.
clean-vendor:
  set -euo pipefail

  echo "Removing vendor directory ..."
  rm -rf vendor

  echo "Vendor directory removal complete."

# Creates the production and development lockfile ('uv.lock.prod', 'uv.lock').
lock: _lock-core
  set -euo pipefail

  echo "Cleaning up vendor ..."
  just clean-vendor

  echo "Lock cleanup complete."

# Builds the Docker image for production locally.
build: _lock-core
  set -euo pipefail

  echo "Building Docker image '{{BUILD_IMAGE}}:{{BUILD_TAG}}' ..."
  docker build -t {{BUILD_IMAGE}}:{{BUILD_TAG}} .

  echo "Docker image build complete."

# Removes the locally built Docker image.
clean-image:
  set -euo pipefail

  echo "Removing Docker image '{{BUILD_IMAGE}}:{{BUILD_TAG}}' ..."
  docker rmi {{BUILD_IMAGE}}:{{BUILD_TAG}} || true

  echo "Docker image removal complete."

# Cleans up everything created by the build process.
clean: clean-image clean-vendor
  echo "Cleanup complete."


# --- Internal Tasks ---

# Core lock workflow: creates uv.lock.prod and restores uv.lock.
# Leaves vendor in place (useful for build).
_lock-core: vendor
  set -euo pipefail

  echo "Creating production lockfile ..."
  echo ""

  echo "Generating production lockfile (no sources) ..."
  uv lock --no-sources

  echo "Saving production lockfile to uv.lock.prod ..."
  mv uv.lock uv.lock.prod

  echo "Restoring development lockfile ..."
  uv lock

  echo ""
  echo "Done."


# --- Development Helpers ---

# Start bot in development mode.
start:
  set -euo pipefail

  echo "Starting bot in development mode ..."
  echo ""

  uv run -m skillbot