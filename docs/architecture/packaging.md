# Packaging

One build per platform (Linux ships two packages) carries everything the desktop app needs to run offline: the API and the worker frozen into PyInstaller binaries, the renderer, the embedding, parser and voice model packs, and the llama.cpp runtime. PyInstaller follows only `import` statements, so anything the app reaches by a path or a string must be named in a spec, and each omission shows up only in a frozen build on a clean machine; the specs name those files, and packaging tests freeze real binaries to catch the ones that slip. Generation weights are never bundled; the app downloads them when the user asks ([egress](egress.md)).

**Code:** [`surfsense_local/backend/bundling/`](../../surfsense_local/backend/bundling/), [`surfsense_local/backend/scripts/build_binaries.py`](../../surfsense_local/backend/scripts/build_binaries.py), [`surfsense_local/electron/electron-builder.yml`](../../surfsense_local/electron/electron-builder.yml), [`surfsense_local/electron/scripts/`](../../surfsense_local/electron/scripts/), [`.github/workflows/release-local.yml`](../../.github/workflows/release-local.yml), [`surfsense_local/backend/tests/packaging/`](../../surfsense_local/backend/tests/packaging/)
**Decisions:** [ADR 0021](../adr/0021-no-intel-mac-build.md), [ADR 0012](../adr/0012-vulkan-only-gpu-backend.md)

How to cut a release is in [`surfsense_local/RELEASE.md`](../../surfsense_local/RELEASE.md); how a release reaches installed apps is in [updates](updates.md).

## An installed app

The asar holds only the Electron main and preload bundles. Everything else rides beside it in `resources/`, where the main process spawns the binaries and loads the SPA by path:

| `extraResources` target | Staged in | Holds |
|---|---|---|
| `backend/api`, `backend/worker` | `backend/dist/` | the frozen onedir binaries |
| `frontend/dist` | `frontend/dist` | the Vite SPA, loaded from disk |
| `models` | `backend/models` | the embedding model, the Docling parser pack, the Kokoro voice |
| `llamacpp` | `electron/llamacpp` | `llama-server` and the libraries it links |
| `sdcpp` | `electron/sdcpp` | `sd-server`, for local image generation |

Packaged, Electron runs `resources/backend/api/api` and one `worker` process per queue, `ingest` and `studio`, and gives both `SURFSENSE_LOCAL_MODELS_DIR` pointing at `resources/models` and `HF_HUB_OFFLINE=1` (`electron/src/main/sidecars/python.ts`). In development the same sidecars run through `uv run`.

## Freezing the backend

`scripts/build_binaries.py` runs PyInstaller on `bundling/api.spec` and `bundling/worker.spec` into `dist/api/` and `dist/worker/`. PyInstaller cannot cross-compile, so each platform builds on itself. The script refuses a Python whose `sqlite3` lacks `enable_load_extension`: python.org's macOS builds omit it, and the frozen app would then die on its first migration, which is why CI freezes with uv's managed Python (`UV_PYTHON_PREFERENCE: only-managed`).

Both specs take the database inputs from `bundling/common.py`, so a dependency bump cannot fix one binary and miss the other:

- `collect_all("sqlite_vec")` ships `vec0`, which `sqlite_vec.load()` finds by the package's own path. Every connection loads it, so without it the migration on launch is the first thing to fail.
- `alembic/` ships as data. `shared/migrations.py` resolves it from its own `__file__`, which PyInstaller sets correctly. `env.py` is data rather than analysed code, so `alembic.context`, `alembic.runtime.migration` and `alembic.runtime.environment` are hidden imports.

What else each spec names, and why the analyser cannot find it on its own:

| Spec | Adds | Because |
|---|---|---|
| `api.spec` | `collect_submodules("uvicorn")` | uvicorn loads its loop, protocol and lifespan implementations by string |
| `api.spec` | `onnxruntime` and `tokenizers` libraries | the query encoder's native libraries load from C |
| `api.spec` | `curated-models.json`, `model-capabilities.json`, the chat prompts | read by path or through `importlib.resources` |
| `api.spec` | excludes Docling, torch, torchvision, transformers, pandas, scipy and OpenCV | only the worker parses files, and the analyser cannot tell these are optional |
| `worker.spec` | Docling and its packages, RapidOCR, transformers, torchvision | lazy and native imports Docling reaches only on the first PDF |
| `worker.spec` | python-docx, python-pptx, xlsxwriter, reportlab | the Office formats run model-written code that imports them, so no static import exists |
| `worker.spec` | kokoro-onnx, espeakng-loader, phonemizer | the voice model and espeak data are read by path |
| `worker.spec` | `modules.documents.tasks`, `modules.artifacts.tasks` | Huey resolves a task by its name |

## Model packs

Three packs are staged into `backend/models` before packaging and ship as `resources/models`, so the first PDF parses and the first query embeds with no network:

| Pack | Staged by | Holds |
|---|---|---|
| Embedding | `build:model`, `scripts/fetch_embedding_model.py` | `bge-small-en-v1.5`: the ONNX model, tokenizer and config |
| Parser | `build:parser`, `scripts/fetch_docling_models.py` | Docling's layout, table and RapidOCR weights, pruned of the variants ingest never loads |
| Voice | `build:voice`, `scripts/fetch_kokoro_model.py` | Kokoro, for podcasts |

The release workflow runs the three scripts directly. Without the parser pack, Docling downloads its weights on first use and RapidOCR writes into `site-packages`, which is read-only inside a frozen bundle, so the first PDF would fail rather than merely be slow. `worker/ingestion/parsing.py` points `HF_HOME` at the models directory before Docling loads and, once the parser pack is complete, sets `HF_HUB_OFFLINE=1`.

## Native runtimes

- `scripts/fetch-llamacpp.mjs` stages a pinned llama.cpp build, checked against its pinned SHA-256, into `electron/llamacpp/`, keeping `llama-server` and the libraries it links. Its rules, the pin, the Vulkan-only GPU backend and the pruning, are in [local-models/runtime.md](local-models/runtime.md).
- `scripts/fetch-sdcpp.mjs` stages stable-diffusion.cpp's `sd-server` into `electron/sdcpp/` from a pinned tag, checked against a locally computed SHA-256: the Vulkan builds for Windows and Linux x64 and the macOS arm64 build. A host with no prebuilt binary gets an empty directory, and the app runs without local image generation.

`pnpm dist` in `electron/` runs every staging step, both fetch scripts included, before `electron-builder`.

## Release builds

`release-local.yml` builds on a `v*` tag, or on `workflow_dispatch` with a version and `publish: never` for a dry run:

| Runner | Artifacts |
|---|---|
| `macos-15` | `SurfSense-arm64.dmg`, `SurfSense-arm64.zip` |
| `windows-latest` | `SurfSense-Setup.exe`, NSIS, x64 |
| `ubuntu-22.04` | `SurfSense.AppImage`, `SurfSense.deb`, x64 |

The Linux runner is pinned because `ubuntu-latest` moves to 26.04 and would silently raise the AppImage's glibc floor; llama.cpp's Vulkan build needs 2.34. There is no Intel Mac build, because torch and onnxruntime no longer publish Intel macOS wheels.

Each runner, in order, checks the version (semver; on a tag push it must equal `surfsense_local/VERSION`), refuses to build with the test signing key ([license](license/app.md)), freezes the binaries, smokes the frozen worker's Docling vision imports (`--check-vision-runtime`) and the frozen API's `/health`, stages the model packs, builds the SPA and the Electron bundles, stages llama.cpp, and runs `electron-builder`. On Linux it then starts the API from the packaged `linux-unpacked` resources and runs `llama-server --list-devices` from its packaged directory, because ggml finds its backends only next to the running executable.

The macOS build is signed with the hardened runtime and notarized whenever the signing secrets are available. Two steps run only on tag pushes: the early check of the Apple notarization credentials, and Azure Trusted Signing for the Windows build.

The installer's version is the one the workflow resolved, passed as `-c.extraMetadata.version`. The tree carries it too: `surfsense_local/VERSION` is the one number, and `surfsense_local/scripts/bump-version.sh` writes it into the backend's `pyproject.toml`, both `package.json` files, the site's `lib/app-release.ts` and the backend's `app/license/release.py`, then refreshes `uv.lock`.

## The NSIS size limit

`makensis` is 32-bit and cannot map a payload over 2 GB, so the Windows installer has a hard ceiling. The Windows build hit it before 2.0.0 through the bundled Ollama's CUDA runners, which were pruned; 2.0.2's `SurfSense-Setup.exe` is 1,296,981,808 bytes on the release, about 1.3 GB. No CUDA payload ships.

## Packaging tests

All four carry the `packaging` marker, which `pyproject.toml` excludes by default because two of them freeze a binary:

| Test | Proves |
|---|---|
| `test_frozen_boot.py` | a minimal frozen entry, `sys.frozen` true, migrates a real database from the bundled revisions, loads `vec0` and round-trips a vector through `chunk_vectors` |
| `test_real_binaries.py` | the real API binary passes its retrieval import check and answers `/health`; the real worker passes its vision import check and both queue consumers stay up; the API half is broken today (Known gaps) |
| `test_spec_data_files.py` | every literal `datas` path in the specs exists, so a renamed file cannot ship missing |
| `test_license_key.py` | the compiled license keys exclude the fixture key |

Only `test_license_key.py` runs in CI, inside the release workflow.

## Known gaps

- Release CI never runs `fetch-sdcpp.mjs`, although `electron-builder.yml` packages an `sdcpp` folder, and `sdcpp/` is not in git, so installers are built without `sd-server`. The app would still offer local image models there, since `offered()` checks the image models directory, which Electron sets for every packaged build, not the binary.
- No tagged release has built the llama.cpp runtime: the v2.0.2 run staged Ollama and llmfit instead.
- No workflow runs the `surfsense_local` tests on pull requests; only the license-key test runs, inside the release workflow.
- No test ingests a PDF with networking disabled.
- `test_real_binaries.py` reads `catalog["warnings"]` from `/llm/catalog`, a field `CatalogRead` no longer has, so its API test fails with `KeyError`.
