# surfsense_local

Electron desktop (`electron/`) plus bundled backend and Vite SPA (`frontend/`). No official Electron skill — this file is the desktop map. Root `AGENTS.md` owns organization.

## Commands

```bash
cd electron && pnpm dev
cd electron && pnpm test
cd electron && pnpm typecheck
./scripts/bump-version.sh
```

Version is `VERSION`. `scripts/bump-version.sh` writes it through the desktop package files.

## Do

- New modules: vertical slice, one responsibility per file. See root `AGENTS.md`.
- Each feature has a doc in `docs/architecture/` at the repo root. Read it before changing the feature, and update it in the same change.
- React UI, colors, polish, motion in `frontend/`: `frontend-workflow` skill.
- shadcn components (`frontend/components.json`): `shadcn` skill after `frontend-workflow`, not instead of it — separate, and it inspects the project live.
- New behavior: `tdd` skill.
- Interface text in `frontend/` or a main-process menu: `translate` skill.

## Do not

- Do not rewrite the Electron shell to the new layout unless that is the task.
