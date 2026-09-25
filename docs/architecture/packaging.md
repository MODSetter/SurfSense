# Packaging

One build per platform (Linux ships two packages) carries everything the desktop app needs to run offline: the API and the worker frozen into PyInstaller binaries, the renderer, the embedding, voice and parser model packs, and the llama.cpp, sd.cpp and audio.cpp runtimes. PyInstaller follows only `import` statements, so anything the app reaches by a path or a string must be named in a spec, and each omission shows up only in a frozen build on a clean machine; the specs name those files, and packaging tests freeze real binaries to catch the ones that slip. Generation weights are never bundled; the app downloads them when the user asks ([egress](egress.md)).

**Code:** [`surfsense_local/backend/bundling/`](../../surfsense_local/backend/bundling/), [`surfsense_local/backend/scripts/build_binaries.py`](../../surfsense_local/backend/scripts/build_binaries.py), [`surfsense_local/electron/electron-builder.yml`](../../surfsense_local/electron/electron-builder.yml), [`surfsense_local/electron/scripts/`](../../surfsense_local/electron/scripts/), [`.github/workflows/release-local.yml`](../../.github/workflows/release-local.yml), [`surfsense_local/backend/tests/packaging/`](../../surfsense_local/backend/tests/packaging/)
**Decisions:** [ADR 0021](../adr/0021-no-intel-mac-build.md), [ADR 0012](../adr/0012-vulkan-only-gpu-backend.md)

How to cut a release is in [`surfsense_local/RELEASE.md`](../../surfsense_local/RELEASE.md); how a release reaches installed apps is in [updates](updates.md).

## An installed app

The asar holds only the Electron main and preload bundles. Everything else rides beside it in `resources/`, where the main process spawns the binaries and loads the SPA by path:

| `extraResources` target | Staged in | Holds |
|---|---|---|
| `backend/api`, `backend/worker` | `backend/dist/` | the frozen onedir binaries |
| `frontend/dist` | `frontend/dist` | the Vite SPA, loaded from disk |
| `models` | `backend/models` | the embedding model and the Docling parser pack |
| `llamacpp` | `electron/llamacpp` | `llama-server` and the libraries it links |
| `sdcpp` | `electron/sdcpp` | `sd-server`, for local image generation |
| `audiocpp` | `electron/audiocpp` | `audiocpp_server`, its libraries, the curated model specs and eSpeak-ng, for podcast voices |

The app icon lives in `electron/build/icons/`: `packaged/` holds the `.icns`, `.ico` and `.png` that `electron-builder.yml` names per OS, and `dev/` a variant with a "DEV" badge, which `electron/src/main/dev-app-identity.ts` sets on the Dock, taskbar, window and About panel only while unpackaged, alongside the name "SurfSense Dev", because development runs inside Electron's own bundle and would otherwise show Electron's icon. The macOS menu bar name and the About panel icon stay Electron’s in development; only packaging changes them. Artwork on Windows and Linux fills its canvas; on macOS it sits at 824 of 1024 px with a transparent margin, Apple's icon grid, so `icon.icns` and `dev/icon-macos.png` carry that margin and the `.ico` and `.png` files do not.

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
| `worker.spec` | the local model manifest, the remote model manifest | Studio finds its chosen image and audio models through the local catalog, and classifies a remote model through the same discovery the API uses; both files are read by path |
| `worker.spec` | Docling and its packages, RapidOCR, transformers, torchvision | lazy and native imports Docling reaches only on the first PDF |
| `worker.spec` | python-docx, python-pptx, xlsxwriter, reportlab | the Office formats run model-written code that imports them, so no static import exists |
| `worker.spec` | `modules.documents.tasks`, `modules.artifacts.tasks` | Huey resolves a task by its name |

## Model packs

Three packs are staged into `backend/models` before packaging and ship as `resources/models`, so the first PDF parses, the first query embeds and the first podcast voices with no network. Every other audio model is downloaded like any other model ([`local-models/catalog.md`](local-models/catalog.md)).

| Pack | Staged by | Holds |
|---|---|---|
| Embedding | `build:model`, `scripts/fetch_embedding_model.py` | `bge-small-en-v1.5`: the ONNX model, tokenizer and config |
| Voice | `build:voice`, `scripts/fetch_bundled_voice.py` | `audio/`: the manifest's first audio model in its default build, Kokoro 82M `Q8_0` (190 MB), with its install record, fetched as a catalog install is: from its pinned commit, sha256-checked |
| Parser | `build:parser`, `scripts/fetch_docling_models.py` | Docling's layout, table and RapidOCR weights, pruned of the variants ingest never loads |

The release workflow runs the three scripts directly. Without the parser pack, Docling downloads its weights on first use and RapidOCR writes into `site-packages`, which is read-only inside a frozen bundle, so the first PDF would fail rather than merely be slow. `worker/ingestion/parsing.py` points `HF_HOME` at the models directory before Docling loads and, once the parser pack is complete, sets `HF_HUB_OFFLINE=1`.

## Native runtimes

- `scripts/fetch-llamacpp.mjs` stages a pinned llama.cpp build, checked against its pinned SHA-256, into `electron/llamacpp/`, keeping `llama-server` and the libraries it links. Its rules, the pin, the Vulkan-only GPU backend and the pruning, are in [local-models/runtime.md](local-models/runtime.md).
- `scripts/sdcpp/stage.mjs`, which `build:sdcpp` runs, stages stable-diffusion.cpp's `sd-server` into `electron/sdcpp/` with the libraries it loads from beside itself and its licences, leaving `sd-cli` behind. It runs `sd-server --help` from the staged folder before it swaps the folder into place.
  - Windows downloads upstream's Vulkan archive, checked against its pinned SHA-256, and copies the MSVC and OpenMP runtimes beside it, which the archive needs and does not carry.
  - Linux and macOS compile the pinned commit, because upstream's Linux archives need glibc 2.38 and its macOS archive needs macOS 26.0. The recipe, `scripts/sdcpp/recipe.mjs`, builds Vulkan on Linux, with one ggml library per micro-architecture, and Metal on macOS, for 13.3.
  - Compiling needs CMake, a C++ compiler and the Vulkan SDK (`glslc` and headers) on Linux, or Xcode's command line tools on macOS; Windows needs Visual Studio 2022 or newer with the C++ tools, for the runtime it ships. Without them the script stages an empty folder and says why, and the app runs without local images. Release CI passes `--strict`, which fails instead.
- `scripts/audiocpp/stage.mjs`, which `build:audiocpp` runs, stages audio.cpp's `audiocpp_server` into `electron/audiocpp/` with the model specs of the three curated families. It adds eSpeak-ng 1.52.0 from the pinned `espeakng-loader` wheel, which Kokoro and Kitten phonemise through (Kokoro finds it through the server's environment, Kitten through `server.json`, [`local-models/catalog.md`](local-models/catalog.md)), and eSpeak-ng's GPL licence text, which the wheel does not carry. It runs `--list-devices` from the staged folder before it swaps the folder into place.
  - macOS downloads upstream's archive, checked against its pinned SHA-256.
  - Windows and Linux compile the pinned commit, because upstream's Linux archives need glibc 2.38 and its Windows archive compiles AVX-512 into the executable. The recipe, `scripts/audiocpp/recipe.mjs`, builds only the CPU backend, since the server runs with `--backend cpu`, with one ggml library per micro-architecture and only the curated model families.
  - Compiling needs CMake and GCC 13 or newer on Linux, or Visual Studio 2022 or newer with the C++ tools on Windows. Without them the script stages an empty folder and says why, and the app runs without local audio. Release CI passes `--strict`, which fails instead.

`pnpm dist` in `electron/` runs every staging step, every native runtime included, before `electron-builder`.

## Building audio.cpp

[`build-audiocpp.yml`](../../.github/workflows/build-audiocpp.yml) compiles the Windows and Linux builds with `stage.mjs --strict`, checks them, and hands each staged folder on as an artifact. `release-local.yml` calls it, and its packaging jobs unpack the artifact before `stage.mjs`, which then finds the server already staged. A pull request that changes `scripts/audiocpp/`, the audio.cpp adapter or engine, the manifest or the voicing test runs it too. It caches the staged folder by the scripts' contents, so a release that does not change them reuses the last checked build, and voices with it again.

Why it compiles rather than downloads, in plain words: upstream's ready-made programs for Linux and Windows do not run on many of the computers the app supports, for a different reason on each.

- **Linux: the age of the system.** Upstream's program needs a recent Linux, Ubuntu 24.04 or later (glibc 2.38). The app's build also runs on older ones, such as Ubuntu 22.04 and RHEL 9.
- **Windows: the processor, not the Windows version.** Upstream's program uses AVX-512 instructions that many common processors lack, so it crashes on them, recent ones included: Intel's 12th to 14th generation, and AMD's before Zen 4. The app's build picks the right code for the processor it runs on.

macOS needs neither, so the app ships upstream's program there. The app's builds are upstream's own code at a pinned commit; only the build settings differ.

It is a stopgap. Once upstream publishes archives that meet both floors, the app downloads those as it does llama.cpp's, and the compile path and the workflow go.

- Linux builds on `ubuntu-22.04`, the release's own runner, with GCC 13 from the toolchain PPA. The PPA replaces the runner's libstdc++ with a newer one, so the build runs in its own job, and the frozen Python binaries never bundle it.
- libstdc++ is linked statically into every file, ggml's CPU modules included, since those take CMake's module flags. libgcc stays dynamic, because GCC 12 and 13's static unwinder on 22.04 calls `_dl_find_object`, from glibc 2.35.
- OpenMP is off, so no `libgomp` ships.
- Linux gates on no symbol newer than `GLIBC_2.34` or `GCC_7.0.0`, which RHEL 9's glibc and libgcc provide, and on no file that needs libstdc++, libgomp or Vulkan. The runner's own libstdc++ is newer than a user's, so only that gate, not the voicing test, catches a dynamic one.
- Windows copies the MSVC runtime beside the executable, so a clean Windows needs no redistributable.
- Both run `test_audiocpp_voicing.py` on the staged folder, cached or not, with each curated model's pinned file downloaded from the URL its manifest entry names ([Packaging tests](#packaging-tests)).
- An artifact drops symlinks and file modes, so the staged folder travels as a tar.

## Building sd.cpp

[`build-sdcpp.yml`](../../.github/workflows/build-sdcpp.yml) compiles the Linux and macOS builds with `stage.mjs --strict`, checks each against the app's floors, and hands each staged folder on as an artifact, as `build-audiocpp.yml` does. A pull request that changes `scripts/sdcpp/` runs it too, so a compile that a pin bump or a new runner image breaks fails in review rather than in a release. It caches the staged folder by the scripts' contents. Windows is a pinned download, so the release job stages it itself, as it does llama.cpp.

Why it compiles on Linux and macOS, in plain words: upstream's ready-made programs start only on the newest systems there, Ubuntu 24.04 (glibc 2.38) and macOS 26.0, while the app runs on Ubuntu 22.04, RHEL 9 and macOS 13.3, the floor its llama.cpp and audio.cpp builds already set. Upstream's Windows program runs on any x64 processor, since its AVX-512 code sits only in the per-processor ggml libraries ggml picks at start, so Windows takes it as built.

- Linux builds on `ubuntu-22.04` with LunarG's Vulkan SDK, as llama.cpp's own 22.04 release does, because 22.04 packages no `glslc` to compile ggml's shaders.
- libstdc++ is linked statically into every file, ggml's modules included, and OpenMP is off, so neither `libstdc++` nor `libgomp` ships. libgcc stays dynamic.
- Linux gates on no symbol newer than `GLIBC_2.34` or `GCC_7.0.0`, on no file that needs libstdc++ or libgomp, and on only the Vulkan backend needing the system's Vulkan loader, which comes with the GPU driver.
- macOS gates on every file targeting 13.3 or older and linking only the system's libraries and its own.
- It is a stopgap, like audio.cpp's: once upstream publishes a Linux archive built on 22.04 and a macOS one for 13.3, the app downloads those and the compile goes.

## Release builds

`release-local.yml` builds on a `v*` tag, or on `workflow_dispatch` with a version and `publish: never` for a dry run:

| Runner | Artifacts |
|---|---|
| `macos-15` | `SurfSense-arm64.dmg`, `SurfSense-arm64.zip` |
| `windows-latest` | `SurfSense-Setup.exe`, NSIS, x64 |
| `ubuntu-22.04` | `SurfSense.AppImage`, `SurfSense.deb`, x64 |

The Linux runner is pinned because `ubuntu-latest` moves to 26.04 and would silently raise the AppImage's glibc floor; llama.cpp's Vulkan build needs 2.34. There is no Intel Mac build, because torch and onnxruntime no longer publish Intel macOS wheels.

Each runner, in order, checks the version (semver; on a tag push it must equal `surfsense_local/VERSION`), refuses to build with the test signing key ([license](license/app.md)), freezes the binaries, smokes the frozen worker's Docling vision imports (`--check-vision-runtime`) and the frozen API's `/health`, stages the model packs, builds the SPA and the Electron bundles, stages llama.cpp, audio.cpp and sd.cpp, and runs `electron-builder`. The three runners wait for the `audiocpp` and `sdcpp` jobs, and unpack audio.cpp's Windows and Linux builds and sd.cpp's Linux and macOS builds. On Linux it then starts the API from the packaged `linux-unpacked` resources and runs `llama-server --list-devices`, `audiocpp_server --list-devices` and `sd-server --help` from their packaged directories, because ggml finds its backends only next to the running executable, and checks that eSpeak-ng and its licence are packaged beside `audiocpp_server`, and sd.cpp's Vulkan backend and licence beside `sd-server`.

The macOS build is signed with the hardened runtime and notarized whenever the signing secrets are available. Two steps run only on tag pushes: the early check of the Apple notarization credentials, and Azure Trusted Signing for the Windows build.

The installer's version is the one the workflow resolved, passed as `-c.extraMetadata.version`. The tree carries it too: `surfsense_local/VERSION` is the one number, and `surfsense_local/scripts/bump-version.sh` writes it into the backend's `pyproject.toml`, both `package.json` files, the site's `lib/app-release.ts` and the backend's `app/license/release.py`, then refreshes `uv.lock`.

## The NSIS size limit

`makensis` is 32-bit and cannot map a payload over 2 GB, so the Windows installer has a hard ceiling. The Windows build hit it before 2.0.0 through the bundled Ollama's CUDA runners, which were pruned; 2.0.2's `SurfSense-Setup.exe` is 1,296,981,808 bytes on the release, about 1.3 GB. No CUDA payload ships.

## Packaging tests

All five carry the `packaging` marker, which `pyproject.toml` excludes by default because two of them freeze a binary and one runs audio.cpp's server on real models:

| Test | Proves |
|---|---|
| `test_frozen_boot.py` | a minimal frozen entry, `sys.frozen` true, migrates a real database from the bundled revisions, loads `vec0` and round-trips a vector through `chunk_vectors` |
| `test_real_binaries.py` | the real API binary passes its retrieval import check and answers `/health`; the real worker passes its vision import check and both queue consumers stay up; both binaries ship the remote manifest, the worker ships the local one, and the frozen API serves a curated row |
| `test_spec_data_files.py` | every literal `datas` path in the specs exists, so a renamed file cannot ship missing, and both `api.spec` and `worker.spec` bundle the local model manifest |
| `test_license_key.py` | the compiled license keys exclude the fixture key |
| `test_audiocpp_voicing.py` | the staged audio.cpp server, started with the sidecar's flags from the `server.json` the app writes, voices two turns of each curated model through the app's adapter, at the sample rate its entry names, then holds no model loaded; it runs only when `SURFSENSE_TEST_AUDIO_MODELS` names a folder of the pinned files, each checked against its sha256, and then fails without a staged server; `build-audiocpp.yml` runs it on both builds |

Two run in CI: `test_license_key.py` inside the release workflow, and `test_audiocpp_voicing.py` inside `build-audiocpp.yml`.

## Known gaps

- `build-sdcpp.yml` has not run yet, so no release has built or packaged sd.cpp: the Linux and macOS compiles and the Windows runtime copy have not run; only the build recipe is unit-tested.
- No CI job generates an image with the staged `sd-server`; its gates are `--help` and the platform floors, not a picture.
- No tagged release has built the llama.cpp runtime: the v2.0.2 run staged Ollama and llmfit instead.
- No issue on audio.cpp asks for archives that meet the app's floors yet, so `build-audiocpp.yml` has no end date.
- No release has built or packaged audio.cpp yet, and nothing has staged its macOS archive on a Mac.
- No workflow runs the `surfsense_local` unit or integration tests on pull requests; only the two packaging tests above run in CI.
- No test ingests a PDF with networking disabled.
