# Packaging

One build per platform (Linux ships two packages) carries everything the desktop app needs to run offline: the API and the worker frozen into PyInstaller binaries, the renderer, the embedding, parser and voice model packs, and the llama.cpp and audio.cpp runtimes. PyInstaller follows only `import` statements, so anything the app reaches by a path or a string must be named in a spec, and each omission shows up only in a frozen build on a clean machine; the specs name those files, and packaging tests freeze real binaries to catch the ones that slip. Generation weights are never bundled; the app downloads them when the user asks ([egress](egress.md)).

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
| `audiocpp` | `electron/audiocpp` | `audiocpp_server`, its libraries, the curated model specs and eSpeak-ng, for podcast voices |

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
| `api.spec` | the local model manifest `catalog/local/manifest/models.json`, the remote model manifest `catalog/remote/manifest/models.json`, the chat prompts | read by path or through `importlib.resources` |
| `api.spec` | excludes Docling, torch, torchvision, transformers, pandas, scipy and OpenCV | only the worker parses files, and the analyser cannot tell these are optional |
| `worker.spec` | the remote model manifest | Studio classifies a remote model through the same discovery the API uses, and the file is read by path |
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
- `scripts/audiocpp/stage.mjs`, which `build:audiocpp` runs, stages audio.cpp's `audiocpp_server` into `electron/audiocpp/` with the model specs of the three curated families. It adds eSpeak-ng 1.52.0 from the pinned `espeakng-loader` wheel, which Kokoro and Kitten phonemise through, and eSpeak-ng's GPL licence text, which the wheel does not carry. It runs `--list-devices` from the staged folder before it swaps the folder into place.
  - macOS downloads upstream's archive, checked against its pinned SHA-256.
  - Windows and Linux compile the pinned commit, because upstream's Linux archives need glibc 2.38 and its Windows archive compiles AVX-512 into the executable. The recipe, `scripts/audiocpp/recipe.mjs`, builds only the CPU backend, since the server runs with `--backend cpu`, with one ggml library per micro-architecture and only the curated model families.
  - Compiling needs CMake and GCC 13 or newer on Linux, or Visual Studio 2022 or newer with the C++ tools on Windows. Without them the script stages an empty folder and says why, and the app runs without local audio. Release CI passes `--strict`, which fails instead.

`pnpm dist` in `electron/` runs every staging step, every native runtime included, before `electron-builder`.

## Building audio.cpp

[`build-audiocpp.yml`](../../.github/workflows/build-audiocpp.yml) compiles the Windows and Linux builds with `stage.mjs --strict`, checks them, and hands each staged folder on as an artifact. `release-local.yml` calls it, and its packaging jobs unpack the artifact before `stage.mjs`, which then finds the server already staged. A pull request that changes `scripts/audiocpp/` runs it too. It caches the staged folder by the scripts' contents, so a release that does not change them reuses the last checked build.

It is a stopgap. Once upstream publishes archives that meet both floors, the app downloads those as it does llama.cpp's, and the compile path and the workflow go.

- Linux builds on `ubuntu-22.04`, the release's own runner, with GCC 13 from the toolchain PPA. The PPA replaces the runner's libstdc++ with a newer one, so the build runs in its own job, and the frozen Python binaries never bundle it.
- libstdc++ is linked statically into every file, ggml's CPU modules included, since those take CMake's module flags. libgcc stays dynamic, because GCC 12 and 13's static unwinder on 22.04 calls `_dl_find_object`, from glibc 2.35.
- OpenMP is off, so no `libgomp` ships.
- Linux gates on no symbol newer than `GLIBC_2.34` or `GCC_7.0.0`, which RHEL 9's glibc and libgcc provide, and on no file that needs libstdc++, libgomp or Vulkan. The runner's own libstdc++ is newer than a user's, so only that gate, not the smoke run, catches a dynamic one.
- Windows copies the MSVC runtime beside the executable, so a clean Windows needs no redistributable.
- Both voice one passage with Kokoro, with the eSpeak-ng paths and flags the sidecar gives the server.
- An artifact drops symlinks and file modes, so the staged folder travels as a tar.

## Release builds

`release-local.yml` builds on a `v*` tag, or on `workflow_dispatch` with a version and `publish: never` for a dry run:

| Runner | Artifacts |
|---|---|
| `macos-15` | `SurfSense-arm64.dmg`, `SurfSense-arm64.zip` |
| `windows-latest` | `SurfSense-Setup.exe`, NSIS, x64 |
| `ubuntu-22.04` | `SurfSense.AppImage`, `SurfSense.deb`, x64 |

The Linux runner is pinned because `ubuntu-latest` moves to 26.04 and would silently raise the AppImage's glibc floor; llama.cpp's Vulkan build needs 2.34. There is no Intel Mac build, because torch and onnxruntime no longer publish Intel macOS wheels.

Each runner, in order, checks the version (semver; on a tag push it must equal `surfsense_local/VERSION`), refuses to build with the test signing key ([license](license/app.md)), freezes the binaries, smokes the frozen worker's Docling vision imports (`--check-vision-runtime`) and the frozen API's `/health`, stages the model packs, builds the SPA and the Electron bundles, stages llama.cpp and audio.cpp, and runs `electron-builder`. The three runners wait for the `audiocpp` job, whose Windows and Linux builds they unpack. On Linux it then starts the API from the packaged `linux-unpacked` resources and runs `llama-server --list-devices` and `audiocpp_server --list-devices` from their packaged directories, because ggml finds its backends only next to the running executable, and checks that eSpeak-ng and its licence are packaged beside `audiocpp_server`.

The macOS build is signed with the hardened runtime and notarized whenever the signing secrets are available. Two steps run only on tag pushes: the early check of the Apple notarization credentials, and Azure Trusted Signing for the Windows build.

The installer's version is the one the workflow resolved, passed as `-c.extraMetadata.version`. The tree carries it too: `surfsense_local/VERSION` is the one number, and `surfsense_local/scripts/bump-version.sh` writes it into the backend's `pyproject.toml`, both `package.json` files, the site's `lib/app-release.ts` and the backend's `app/license/release.py`, then refreshes `uv.lock`.

## The NSIS size limit

`makensis` is 32-bit and cannot map a payload over 2 GB, so the Windows installer has a hard ceiling. The Windows build hit it before 2.0.0 through the bundled Ollama's CUDA runners, which were pruned; 2.0.2's `SurfSense-Setup.exe` is 1,296,981,808 bytes on the release, about 1.3 GB. No CUDA payload ships.

## Packaging tests

All four carry the `packaging` marker, which `pyproject.toml` excludes by default because two of them freeze a binary:

| Test | Proves |
|---|---|
| `test_frozen_boot.py` | a minimal frozen entry, `sys.frozen` true, migrates a real database from the bundled revisions, loads `vec0` and round-trips a vector through `chunk_vectors` |
| `test_real_binaries.py` | the real API binary passes its retrieval import check and answers `/health`; the real worker passes its vision import check and both queue consumers stay up; both binaries ship the remote manifest, and the frozen API serves a curated row |
| `test_spec_data_files.py` | every literal `datas` path in the specs exists, so a renamed file cannot ship missing |
| `test_license_key.py` | the compiled license keys exclude the fixture key |

Only `test_license_key.py` runs in CI, inside the release workflow.

## Known gaps

- Release CI never runs `fetch-sdcpp.mjs`, although `electron-builder.yml` packages an `sdcpp` folder, and `sdcpp/` is not in git, so installers are built without `sd-server`. The app would still offer local image models there, since `offered()` checks the image models directory, which Electron sets for every packaged build, not the binary.
- No tagged release has built the llama.cpp runtime: the v2.0.2 run staged Ollama and llmfit instead.
- No issue on audio.cpp asks for archives that meet the app's floors yet, so `build-audiocpp.yml` has no end date.
- No release has built or packaged audio.cpp yet, and nothing has staged its macOS archive on a Mac.
- No workflow runs the `surfsense_local` tests on pull requests; only the license-key test runs, inside the release workflow.
- No test ingests a PDF with networking disabled.
- `test_the_curated_manifest_is_one_of_them` fails on Windows: `literal_data_paths()` joins the spec's path with `Path`, which gives backslashes there, and the test looks for a forward-slash string.
