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
- New behavior: `tdd` skill.

## Do not

- Do not rewrite the Electron shell to the new layout unless that is the task.
