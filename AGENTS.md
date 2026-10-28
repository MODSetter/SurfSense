# AGENTS.md

Nearest `AGENTS.md` wins. Edit this file, not `CLAUDE.md` (`CLAUDE.md` is a symlink).

## Overview

Desktop app plus SurfSense's own backend. Three trees:

| Tree | Role |
|------|------|
| `www` | Next.js site at `www.surfsense.com`, and the update feed and usage routes the desktop calls |
| `surfsense_local` | Electron desktop |
| `backend` | The one SurfSense backend, one process run by `server/`: the [license portal](docs/architecture/license/portal.md) in `license/`, its `mailer/`, and `plugins/`, which holds SurfSense's own plugin servers ([plugin host](docs/architecture/plugin-host.md)) and the [registry](docs/architecture/plugin-registry.md); `plugins/bundles/` holds the earlier, local design's SDK and tooling, deferred |

The hosted service closed on 18 Oct 2026, when its user data was purged. The self-hosted stack, `surfsense_backend`, `surfsense_web`, `surfsense_mcp` and `docker/`, lives only on the `legacy` branch ([legacy stack](docs/architecture/legacy.md)). Product direction is local + API.

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
# www
cd www && pnpm install
cd www && pnpm dev
cd www && pnpm format

# desktop
cd surfsense_local/electron && pnpm dev

# backend/: the one backend: the license portal and SurfSense's own plugins
cd backend && uv sync
cd backend && PYTHONPATH=plugins uv run python -m server

# bundles (deferred): the manifest rules, the SDK, the surfsense-plugins command
cd backend/plugins/bundles/core/manifest && uv sync
cd backend/plugins/bundles/core/sdk && uv sync
cd backend/plugins/bundles/core/sdk && uv run pyright
cd backend/plugins/bundles/core/cli && uv sync

# hooks
pre-commit run --all-files
```

## Testing

| Area | Command |
|------|---------|
| Website unit | `cd www && pnpm test:unit` |
| `backend/` | `cd backend && uv run pytest` |
| Bundles: manifest rules | `cd backend/plugins/bundles/core/manifest && uv run pytest -m unit` |
| Bundles: SDK | `cd backend/plugins/bundles/core/sdk && uv run pytest -m unit` |
| Bundles: SDK against the app | `cd backend/plugins/bundles/core/sdk && uv run pytest -m contract` (starts the desktop backend; `uv sync` it first) |
| Bundles: CLI | `cd backend/plugins/bundles/core/cli && uv run pytest` (starts the desktop backend; `uv sync` it first) |
| Desktop | `cd surfsense_local/electron && pnpm test` |
| Docker entry | `cd surfsense_local/headless && pnpm test` |
| Frontend in Docker mode | `cd surfsense_local/frontend && pnpm test:docker` (tests tagged `docker`; `pnpm test` leaves them out) |
| Docker installers | `node --test docker/scripts/install.test.ts` (both scripts against a stand-in `docker`; `install.ps1`'s half needs `pwsh`) |
| Docker image | `SURFSENSE_TEST_IMAGE=<image> node --test surfsense_local/headless/image.test.ts` (starts the image on ports 4929 and 4943; `SURFSENSE_TEST_IMAGE_PORT=4931` moves them to 4931 and 4945, beside a running install) |
| Backend in the image | build `docker/surfsense/Dockerfile --target backend-tests` and run it with `tests/` and `docs/contracts/` mounted, as `docker-tests.yml` does; it runs `pytest -m image` |
CI: `.github/workflows/`. New behavior: one failing test, then the minimum code to pass it. Use the `tdd` skill. Tests hit public seams, not internals.

## Pull requests

Follow [CONTRIBUTING.md](CONTRIBUTING.md). The parts agents miss:

- Open PRs against `dev`. `gh pr create` targets the default branch, `main`, unless you pass `--base dev`.
- `gh pr create --body` skips the PR template. Keep its headings: What, Why, `Fixes #`, How to test.
- Commit messages and PR titles are Conventional Commits, `type(scope): summary`. The commitizen hook runs only where it is installed; CI does not run it.
- A new feature starts as a proposal PR in `docs/proposals/`, not as code.
- `backend/plugins/proprietary/` is Business Source License 1.1 and changed only by maintainers: ask one before changing it. A change to `docs/contracts/` needs the owners of both sides.

## Skills

Canonical dir: `.agents/skills/`. `.claude/skills` is a symlink to it.

| Skill | When |
|-------|------|
| `tdd` | New behavior or a bug fix with a testable seam |
| `codebase-design` | Module shape, seam, depth — `tdd` depends on this vocabulary |
| `fastapi` | FastAPI / Pydantic work. Symlink into the installed wheel; repair the **same** root link, into `surfsense_local/backend/.venv`, after a FastAPI or Python bump. |
| `frontend-workflow` | Frontend work in `www` and `surfsense_local/frontend`: React/Next performance, color tokens, UI polish, motion. Bundles `react-performance/`, `color/`, `polish/`, `motion/`, and `base-ui.md` for Base UI in `surfsense_local/frontend`; routes out to `shadcn`. |
| `shadcn` | UI components in a tree with `components.json`. Standalone — it inspects the project live and grants its own CLI, which only works as a discovered skill. Load it after `frontend-workflow`, not instead of it. |
| `translate` | Interface strings in `surfsense_local`: adding a message in code (`en.json` is generated from it), moving hard-coded text into messages, translating Japanese and German. Holds the key shape, tone and glossary. |

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

- Legacy self-hosted fixes go in a pull request into `legacy`, never `dev`.
- Edit the root `README.md` directly. The draft at `plans/community-local/seo/drafts/README.md` shipped on 18 Sep 2026 and is kept only for history. Anything added to the README replaces something — its length was measured against the eight biggest repos in this category. Make the same change in every `README.<locale>.md`, section for section; [`06-repo-readme.md`](plans/community-local/seo/06-repo-readme.md#the-readme-since-9-oct-2026) has the rules, where each format-table cell is checked, and how to replace the demo video.
- Do not commit, push or open a PR unless asked.

## Security

- Never commit `.env` or secrets.
- Do not put credentials in diffs, logs, or sample payloads.
