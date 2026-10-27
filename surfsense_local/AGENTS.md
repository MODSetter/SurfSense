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
cd electron && pnpm test        # also runs sidecars/ and runtimes/
cd electron && pnpm typecheck   # also checks sidecars/
cd frontend && pnpm test        # the desktop; tests tagged docker are left out
cd frontend && pnpm test:docker # tests tagged docker, with the image build's settings and no Electron
cd headless && pnpm test        # the Docker entry; image.test.ts skips without an image
cd headless && pnpm typecheck   # also checks sidecars/
SURFSENSE_TEST_IMAGE=surfsense:local node --test headless/image.test.ts   # a built image
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
- A backend test of what the Docker image changes (its user, process reaping, bundled models, system libraries) also takes `pytest.mark.image`, so Docker Tests runs it inside the image too.
- A frontend branch only the Docker image takes (no Electron bridge, its build settings, `in_container`) is tested in a `describe(…, { tags: ["docker"] }, …)` beside its desktop tests, which Docker Tests runs with the image's build settings.
- Interface text in `frontend/`: `translate` skill. The application menu is not translated: Electron roles, plus a few English items of ours in `electron/src/main/menu/`.

## Do not

- Do not rewrite the Electron shell to the new layout unless that is the task.
- Do not import `electron` under `sidecars/`; a test fails on it. What only Electron can do stays in `electron/`.
