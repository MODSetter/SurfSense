# surfsense_local

One core with two entries ([ADR 0072](../docs/adr/0072-the-desktop-and-the-container-are-two-entries-over-one-core.md)). No official Electron skill — this file is the desktop map. Root `AGENTS.md` owns organization.

| Folder | Role |
|--------|------|
| `backend/` | API and workers (Python) |
| `frontend/` | Vite SPA |
| `sidecars/` | Boot, the sidecar specs, the supervisor and the watchers both entries run; imports only Node |
| `runtimes/` | Pinned staging of llama.cpp, sd.cpp, audio.cpp and opencode; stages into `electron/<runtime>/` |
| `electron/` | Desktop entry: window, IPC, keychain, updater, packaging |
| `headless/` | Docker entry: boot context from the environment, signals |

## Commands

```bash
cd electron && pnpm dev
cd electron && pnpm test        # also runs sidecars/, runtimes/ and headless/
cd electron && pnpm typecheck   # also checks sidecars/ and headless/
./scripts/bump-version.sh
SURFSENSE_LOCAL_DATA_DIR=<dir> node headless/main.ts   # the container's entry, on a checkout
```

Version is `VERSION`. `scripts/bump-version.sh` writes it through the desktop package files.

## Do

- New modules: vertical slice, one responsibility per file. See root `AGENTS.md`.
- Each feature has a doc in `docs/architecture/` at the repo root. Read it before changing the feature, and update it in the same change.
- React UI, colors, polish, motion in `frontend/`: `frontend-workflow` skill.
- shadcn components (`frontend/components.json`): `shadcn` skill after `frontend-workflow`, not instead of it — separate, and it inspects the project live.
- New behavior: `tdd` skill.
- Interface text in `frontend/`: `translate` skill. The application menu is not translated: Electron roles, plus a few English items of ours in `electron/src/main/menu/`.

## Do not

- Do not rewrite the Electron shell to the new layout unless that is the task.
- Do not import `electron` under `sidecars/`; a test fails on it. What only Electron can do stays in `electron/`.
