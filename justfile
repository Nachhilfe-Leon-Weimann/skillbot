set shell := ["bash", "-cu"]

# --- Quality ---

lint:
    uv run ruff check

format-check:
    uv run ruff format --check

static-checks: lint format-check

# Everything that must be green before a push; CI's `check` job runs the same.
check: static-checks test

# --- Bot ---

skillcore := "../skillcore"

dev:
    @echo "Starting SkillBot..."
    @uv run -m skillbot

# Also sync the slash commands on start.
dev-synced:
    @DISCORD__SYNC_COMMANDS=true just dev

# Run against the local SkillCore checkout instead of the pinned release.
dev-local-core:
    @echo "Starting SkillBot with editable SkillCore..."
    @uv run --with-editable {{ skillcore }} -m skillbot

# --- Testing ---

test:
    uv run pytest

test-v:
    uv run pytest -v

test-file file:
    uv run pytest {{ file }}

test-one test:
    uv run pytest -k {{ test }}

# --- Docker ---

# SkillCore is private, so the build needs a read token as a build secret.
docker-build image="skillbot:local":
    @test -n "${SKILLPLATFORM_READ_TOKEN:-}" || (echo 'Set SKILLPLATFORM_READ_TOKEN, for example: export SKILLPLATFORM_READ_TOKEN=$(gh auth token)' >&2; exit 1)
    docker build --secret id=github_token,env=SKILLPLATFORM_READ_TOKEN -t {{ image }} .

docker-run image="skillbot:local":
    docker run --rm --env-file .env {{ image }}
