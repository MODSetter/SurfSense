# AGENTS.md

Nearest `AGENTS.md` wins. Edit this file, not `CLAUDE.md` (`CLAUDE.md` is a symlink).

## Overview

The `legacy` branch: the self-hosted SurfSense stack, frozen at the version in `VERSION`. The desktop app and everything that still ships live on `dev` and `main`.

| Tree | Role |
|------|------|
| `surfsense_backend` | FastAPI API |
| `surfsense_web` | Next.js UI; `/` goes to login |
| `surfsense_mcp` | MCP server over the REST API |
| `docker` | Compose files, the sandbox image and the install scripts |

Nothing new lands here. A bug fix is a pull request into `legacy`.

## Commands

```bash
# backend
cd surfsense_backend && uv sync
cd surfsense_backend && uv run ruff check .
cd surfsense_backend && uv run pytest -m unit

# web
cd surfsense_web && pnpm install
cd surfsense_web && pnpm dev
cd surfsense_web && pnpm format

# MCP
cd surfsense_mcp && uv sync

# compose
docker compose -f docker/docker-compose.yml

# hooks
pre-commit run --all-files
```

## Testing

| Area | Command |
|------|---------|
| Backend unit | `cd surfsense_backend && uv run pytest -m unit` |
| Backend integration | `cd surfsense_backend && uv run pytest -m integration` |
| Web unit | `cd surfsense_web && pnpm test:unit` |
| Web e2e | `cd surfsense_web && pnpm test:e2e` |
| MCP | `cd surfsense_mcp && uv run pytest` |

CI: `.github/workflows/`. A fix starts with one failing test. Use the `tdd` skill.

## Releases

- `VERSION` holds the version; `scripts/bump-version.sh` writes it into each tree's manifest.
- Tag the merge commit `legacy-vX.Y.Z`, matching `VERSION`. The tag builds and pushes `ghcr.io/modsetter/surfsense-backend`, `surfsense-web` and `surfsense-sandbox`, and moves `latest`.
- Never tag `vX.Y.Z` here: tags are repo-wide, and `v*` belongs to the desktop app.

## Pull requests

Follow [CONTRIBUTING.md](CONTRIBUTING.md). The parts agents miss:

- Open PRs against `legacy`: `gh pr create --base legacy`.
- `gh pr create --body` skips the PR template. Keep its headings: What, Why, `Fixes #`, How to test.
- Commit messages and PR titles are Conventional Commits, `type(scope): summary`.
- `surfsense_backend/app/proprietary/` is Business Source License 1.1 and changed only by maintainers: ask one before changing it.

## Skills

Canonical dir: `.agents/skills/`. `.claude/skills` is a symlink to it.

| Skill | When |
|-------|------|
| `tdd` | A bug fix with a testable seam |
| `codebase-design` | Module shape, seam, depth — `tdd` depends on this vocabulary |
| `fastapi` | FastAPI / Pydantic work |
| `frontend-workflow` | Frontend work in `surfsense_web` |
| `shadcn` | UI components in `surfsense_web`. Load it after `frontend-workflow` |

## Security

- Never commit `.env` or secrets.
- Do not put credentials in diffs, logs, or sample payloads.
