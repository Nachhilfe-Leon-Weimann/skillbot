alias s := sync-skillcore
alias i := install-skillcore-local
alias r := run
alias rd := run-dev
alias rm := run-main
alias rds := run-dev-sync
alias rms := run-main-sync

# --- skillcore sources ---

sync-skillcore:
    @echo "Syncing skillcore from git (lock -> latest main)..."
    uv lock --upgrade-package skillcore
    uv sync
    @echo "skillcore synced from git."

install-skillcore-local:
    @echo "Installing local skillcore (editable)..."
    uv pip install -e ../skillcore --no-deps --force-reinstall
    @echo "local skillcore installed."

which-skillcore:
    @uv pip show -v skillcore

# --- run modes ---

run:
    @echo "Running SkillBot..."
    @uv run -m skillbot

run-dev:
    @just install-skillcore-local
    @just which-skillcore
    @echo "Running SkillBot (dev + command sync)..."
    @just run

run-dev-sync:
    @just install-skillcore-local
    @just which-skillcore
    @DISCORD__SYNC_COMMANDS=1 uv run -m skillbot

run-main:
    @just sync-skillcore
    @just which-skillcore
    @just run

run-main-sync:
    @just sync-skillcore
    @just which-skillcore
    @DISCORD__SYNC_COMMANDS=1 uv run -m skillbot