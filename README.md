# SkillBot

Discord bot for the skill-platform.

## Development

Everything runs through [`just`](Justfile) (which wraps `uv`).

- `just start` - run the bot locally (`just start-synced` also syncs the slash commands). There is no dev
  deployment: only prod exists.
- `just start-local-core` - the same against the skillcore checkout next to this repo (`../skillcore`) instead
  of the pinned release, for working on both at once.
- `just check` - lint, format check and tests. **Keep green before every push**; CI's `check` job runs the same
  and is the required check of `main`.
- `just build` - build the production image locally. skillcore is private, so it needs a token:
  `export SKILLPLATFORM_READ_TOKEN=$(gh auth token)`.

skillcore is a private git dependency, pinned to a release tag in [`pyproject.toml`](pyproject.toml)
(`[tool.uv.sources]`); to move to a newer release, change the tag and run `uv lock`. `uv.lock` is tracked: CI
and the image install with `--locked` and fail when it is stale.

## Releasing

One release flow for the whole platform; the why is in skillforge's
[`release-flow.md`](https://github.com/Nachhilfe-Leon-Weimann/skillforge/blob/main/docs/specs/release-flow.md).

Releases are driven by [release-please](https://github.com/googleapis/release-please): it keeps a release PR
(`chore(main): release X.Y.Z`) up to date with the next version and `CHANGELOG.md`, both derived from the
conventional commits on `main` - so the commit type matters (`feat`, `fix`, `!`). **Merging that PR
(`gh pr merge <n> -sd --auto`) is the release** - the `Release` workflow then tags `vX.Y.Z`, builds
`ghcr.io/nachhilfe-leon-weimann/skillbot:vX.Y.Z` and deploys through the Dokploy API, failing unless the
Dokploy deployment ends in `done`. The bot has no HTTP endpoint, so the deployment status is the whole
verification: a container that starts and then crashes is not detected. Never bump the version, edit
`CHANGELOG.md` or create a tag by hand, and nothing deploys on a plain push to `main`.

If a `Release` run fails after the release exists, fix the cause and use **Re-run failed jobs** - never
*Re-run all jobs*: release-please would find the release already created, report no new release, and every
later job would be skipped while the run turns green. To rebuild only the image, dispatch `Build` for the
tag; to deploy the current release again, dispatch `Deploy` with its version.

[`compose.yml`](compose.yml) is what Dokploy runs, and it pins the deployed version: the release PR rewrites
its `image:` tag to `vX.Y.Z` together with the version bump (as it does in `uv.lock`), so `main` names
what prod runs and a restart of the stack cannot pull a different version. `:latest` is still published, but
nothing deploys from it.

| Workflow | Role |
|---|---|
| `ci.yml` | job `check` on PRs and pushes to `main` |
| `release.yml` | push to `main`: release-please, then image and deploy when a release was created |
| `build.yml` | the image (`:vX.Y.Z`, `:sha-...`, `:latest`); can be dispatched for a tag |
| `deploy.yml` | entry point for a deploy; calls the shared workflow in [`skill-platform-workflows`](https://github.com/Nachhilfe-Leon-Weimann/skill-platform-workflows) |

### Rolling back

There is no automatic rollback. To go back to an earlier release:

1. Open a PR that sets the earlier tag on the `image:` line of `compose.yml` and merge it. Title it
   `chore(deploy): roll back to vX.Y.Z` - a `chore` neither shows up in the changelog nor causes a release.
2. Dispatch `Deploy` with that earlier version.

Nothing has to be undone afterwards: the next release PR rewrites the tag to its own version.
