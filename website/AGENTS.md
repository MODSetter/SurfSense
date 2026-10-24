# website

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

## Do

- New UI: vertical slice, one responsibility per file. See root `AGENTS.md`.
- React/Next, colors, UI polish, motion: `frontend-workflow` skill.
- shadcn components (`components.json`): `shadcn` skill after `frontend-workflow`, not instead of it — separate, and it inspects the project live.
- New behavior: `tdd` skill.

## Do not

- Do not add npm lockfiles.
- Do not rewrite existing routes to the new layout unless that is the task.
- Do not add accounts or app routes. The hosted app is on the `legacy` branch.
