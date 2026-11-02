# www

The site at `www.surfsense.com`, built by Vercel from this folder. Next.js App Router, `pnpm`, Biome. Root `AGENTS.md` owns organization and TDD.

Package manager is **pnpm**, not npm or yarn.

Next.js docs for this installed version: `node_modules/next/dist/docs/`.

## Commands

```bash
pnpm install
pnpm dev
pnpm build
pnpm format
pnpm test:unit
```

## Layout

| Folder | Holds |
|---|---|
| `app/` | Routes. A page's body is its `page.tsx`; files only that route uses sit beside it. The home page's sections are in `app/(home)/_home/` |
| `features/<name>/` | Code more than one route uses: downloads, license, announcements, analytics, docs, desktop telemetry |
| `components/ui/` | shadcn primitives and `cn` |
| `components/site/` | The site's shared blocks: nav, footer, shell, FAQ, buttons, logos, JSON-LD |
| `content/` | MDX: `docs/`, `blog/`, `changelog/`, `announcements/` |

New code starts beside the route that uses it and moves to `features/` when a second route needs it. `sitemap.ts` reads each route's data directly. Tests sit beside their code as `*.test.ts`.

## User docs

`content/docs/v2/` is the SurfSense 2.0 user guide at `/docs/v2`. `content/docs/legacy/` documents the final self-hosted release and takes fixes only, no new pages.

- Readers are users, not engineers. No internals, repo paths or ADR numbers.
- Quote interface labels exactly as `surfsense_local/frontend/translations/en.json` has them, as Settings › Models.
- No em dashes, en dashes or spaced hyphens in prose.
- Leave out numbers that change every release, such as model counts, sizes and benchmarks. The changelog carries them.
- Each folder's `meta.json` orders its pages; `---Label---` is a group heading. Folders are one level deep.
- A sidebar icon is a name in `meta.json` or frontmatter, and must also be in `DOCS_ICONS` in `features/docs/source.ts`.
- Moving or renaming a page adds a redirect to `features/docs/docs-redirects.mts`, with a test beside it.
- Before a PR: `pnpm test:unit`, which also validates every `meta.json`, and `pnpm build`.

## Do

- New UI: vertical slice, one responsibility per file. See root `AGENTS.md`.
- React/Next, colors, UI polish, motion: `frontend-workflow` skill.
- shadcn components (`components.json`): `shadcn` skill after `frontend-workflow`, not instead of it — separate, and it inspects the project live.
- New behavior: `tdd` skill.

## Do not

- Do not add npm lockfiles.
- Do not rewrite existing routes to the new layout unless that is the task.
- Do not add accounts or app routes. The hosted app is on the `legacy` branch.
