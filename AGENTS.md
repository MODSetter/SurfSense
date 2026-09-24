# AGENTS.md

Nearest `AGENTS.md` wins. Edit this file, not `CLAUDE.md` (`CLAUDE.md` is a symlink).

## Overview

Desktop app plus scraper API. Four trees, and a fifth planned:

| Tree | Role |
|------|------|
| `surfsense_backend` | FastAPI API |
| `surfsense_web` | Next.js hosted UI |
| `surfsense_local` | Electron desktop |
| `surfsense_mcp` | MCP server over the REST API |
| `plugins` | Planned, not in the repo yet: the plugin SDK, and every plugin — ours and contributed ([proposal](docs/proposals/plugins/README.md)) |

The hosted service has been export-only since the 2.0.0 launch on 18 Sep 2026, and its user data is purged on 18 Oct 2026 ([sunset](docs/architecture/sunset.md)). Product direction is local + API.

## Code organization

Applies to **every new file**. Existing code is not a template and not a cleanup ticket.

**Must**

- Organize by feature (vertical slice), not by technical layer.
- One responsibility per file. One responsibility per folder.
- If a responsibility grows sub-responsibilities, promote it to a folder. Each sub-responsibility is its own file.
- Names state what and why, not how.
- Comments and docstrings state intent only. Do not restate the code.
- Keep them short. A line or two. Write only what the code cannot say: a constraint, a rejected alternative, a number that justifies a threshold.

**Must not**

- Do not write essays in docstrings. If it explains how you arrived at the code rather than what the code must honour, delete it.
- Do not put new work in a nearby file because it is convenient. New responsibility, new file.
- Do not add catch-all folders (`utils`, `helpers`, `common`, `misc`, `shared`) unless that name is the product concept.
- Do not layer-split new work (`controllers/`, `services/`, `models/` as the primary tree).
- Do not rewrite existing code to this layout unless the task is that rewrite.

The tree is inconsistent. New work follows this. Old work stays until a task explicitly owns it.

## Docs

[`docs/`](docs/README.md) is the engineering map. `architecture/` says what is true now, one doc per feature; `adr/` says why; `proposals/` holds designs not built yet; `contracts/` holds the frozen interfaces between trees. Task status lives in GitHub issues; docs carry only a proposal's `status` and each architecture doc's Known gaps. `plans/` is business and ops material, not specs.

- Before changing a feature, read its doc in `docs/architecture/` and the ADRs it links.
- If a change alters behaviour a doc describes, update the doc in the same change. Fixing a Known gap deletes its line.
- Run `python scripts/check_docs.py` after editing anything under `docs/` or `plans/`.

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

# desktop
cd surfsense_local/electron && pnpm dev

# MCP
cd surfsense_mcp && uv sync

# compose (dev and self-host, not production)
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
| Desktop | `cd surfsense_local/electron && pnpm test` |
CI: `.github/workflows/`. New behavior: one failing test, then the minimum code to pass it. Use the `tdd` skill. Tests hit public seams, not internals.

## Pull requests

Follow [CONTRIBUTING.md](CONTRIBUTING.md). The parts agents miss:

- Open PRs against `dev`. `gh pr create` targets the default branch, `main`, unless you pass `--base dev`.
- `gh pr create --body` skips the PR template. Keep its headings: What, Why, `Fixes #`, How to test.
- Commit messages and PR titles are Conventional Commits, `type(scope): summary`. The commitizen hook runs only where it is installed; CI does not run it.
- A new feature starts as a proposal PR in `docs/proposals/`, not as code.
- `surfsense_backend/app/proprietary/` is Business Source License 1.1: ask a maintainer before changing it. A change to `docs/contracts/` needs the owners of both sides.

## Skills

Canonical dir: `.agents/skills/`. `.claude/skills` is a symlink to it.

| Skill | When |
|-------|------|
| `tdd` | New behavior or a bug fix with a testable seam |
| `codebase-design` | Module shape, seam, depth — `tdd` depends on this vocabulary |
| `fastapi` | FastAPI / Pydantic work. Symlink into the installed wheel; repair the **same** root link after a FastAPI or Python bump. Do not keep `surfsense_backend/.agents/`. |
| `frontend-workflow` | Frontend work in `surfsense_web` and `surfsense_local/frontend`: React/Next performance, color tokens, UI polish, motion. Bundles `react-performance/`, `color/`, `polish/`, `motion/`; routes out to `shadcn`. |
| `shadcn` | UI components in a tree with `components.json`. Standalone — it inspects the project live and grants its own CLI, which only works as a discovered skill. Load it after `frontend-workflow`, not instead of it. |
| `migrate-radix-to-base` | Radix UI → Base UI migration. Stays top-level; not part of `frontend-workflow`. |
| `translate` | Interface strings in `surfsense_local`: adding a key to `translations/en.json`, moving hard-coded text into messages, translating Japanese and German. Holds the key shape, tone and glossary. |

Do not install skill catalogs. Do not add `CONTEXT.md` or a second rules tree.

`frontend-workflow` bundles what were separate skills under `react-performance/`,
`color/`, `polish/`, and `motion/`. Those files keep their old frontmatter, which
is inert — they are reference files, not discovered skills. Skill discovery is one
level deep, so do not nest a new skill inside another skill's folder.

Bundle a skill only if it is static markdown that overlaps the others. Anything
with frontmatter that does work — `allowed-tools`, `` !`command` `` substitution —
must stay top-level, because that frontmatter is inert in a bundled file.

`shadcn/SKILL.md` carries one local addition: a note routing to `frontend-workflow`
first. It is the only edit to that vendored file — restore it after any shadcn
re-sync, or component work bypasses the color palette and polish rules.

`skills-lock.json` lists `vercel-react-best-practices`, which now lives at
`frontend-workflow/react-performance/`. `shadcn` is back at its original path and
its lock entry is valid.

## Boundaries

- Do not carve hosted code out of backend/web until the purge on 18 Oct 2026. The export window and the purge script run on that code until then.
- Do not drop SearxNG, sandbox, OpenSandbox, or zero-cache from compose until a new compose is defined.
- Edit the root `README.md` directly. The draft at `plans/community-local/seo/drafts/README.md` shipped on 18 Sep 2026 and is kept only for history. Anything added to the README replaces something — its length was measured against the eight biggest repos in this category.
- Do not commit, push or open a PR unless asked.

## Security

- Never commit `.env` or secrets.
- Do not put credentials in diffs, logs, or sample payloads.
