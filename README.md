# SkillBot

The Discord bot of the skill-platform: tutoring management on Discord, backed by the
[skillforge](https://github.com/Nachhilfe-Leon-Weimann/skillforge) API.

## Development

Needs `uv`, `just` and a `.env` (see [`.env.example`](.env.example)).

| Command | |
|---|---|
| `just dev` | run the bot |
| `just dev-synced` | run it and sync the slash commands |
| `just dev-local-core` | run it against the local `../skillcore` checkout |
| `just check` | lint, format check, typecheck and tests - keep green before every push |

Everything else is in the [`justfile`](justfile).

## Releasing

Merging the release PR (`chore(main): release X.Y.Z`) is the release: tag, image and deploy follow. Never bump
the version or tag by hand - the conventional commits on `main` (`feat`, `fix`, `!`) drive both.

The platform's one flow, documented in skillforge:
[`release-flow.md`](https://github.com/Nachhilfe-Leon-Weimann/skillforge/blob/main/docs/specs/release-flow.md)
(the why), [rolling back](https://github.com/Nachhilfe-Leon-Weimann/skillforge#rolling-back), and
[`skill-platform-workflows`](https://github.com/Nachhilfe-Leon-Weimann/skill-platform-workflows) (the deploy).
