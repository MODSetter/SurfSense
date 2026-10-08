---
status: proposed
code:
  - surfsense_local/backend/pyproject.toml
  - surfsense_local/backend/bundling/worker.spec
  - surfsense_local/backend/worker.py
  - surfsense_local/backend/modules/runtime_packs/
  - surfsense_local/backend/modules/egress/service.py
  - surfsense_local/backend/modules/plugins/plugin_interpreter.py
  - surfsense_local/backend/modules/resource_usage/engines.py
  - surfsense_local/backend/worker/ingestion/parsing.py
  - surfsense_local/backend/tests/packaging/
  - surfsense_local/electron/electron-builder.yml
  - surfsense_local/electron/build/entitlements.python.plist
  - surfsense_local/electron/src/main/sidecars/python.ts
  - surfsense_local/electron/src/main/updater.ts
  - surfsense_local/electron/scripts/fonts/
  - surfsense_local/electron/scripts/python/
  - surfsense_local/electron/scripts/packs/office/
  - surfsense_local/electron/scripts/check-installer-size.mjs
  - surfsense_local/frontend/src/features/runtime-packs/
  - surfsense_local/frontend/src/features/egress/
  - surfsense_local/scripts/licenses/
  - .github/workflows/release-local.yml
  - .github/workflows/build-runtime-packs.yml
  - .github/workflows/code-quality.yml
  - docs/adr/0041-runtime-packs-after-consent.md
---

# Runtime and packs

> The document engines run inside the frozen Studio worker, which already carries almost every library they need, so the file agent adds about 75 MB to a Windows installer, most of it opencode, which installers carry from the release that turns the agent on (M5). The installer gains pypdf, three metric-compatible font families, a licence gate that also reads the native binaries inside the frozen tree, and a third-party notices file, and loses the 0.8 GB of developer caches that leak into local builds. LibreOffice is an optional runtime pack, shown in the interface as "Office support": a pinned upstream build, unaltered except for deleted files, that SurfSense re-hosts on its own releases, pins by sha256 in the app, and downloads only when the user asks and allows GitHub. It runs only outside the engine child and outside any database transaction, under a profile with updates, macros and links off, on a copy whose external links have been removed. Recalculated values never come from an alpha engine. A new ADR settles that executable packs are allowed after consent. No general Python ships for the engines or the agent's shell; the one the plugin system needs ships with plugins. No JavaScript runtime is needed, and Electron's RunAsNode fuse is switched off.

Facts below were checked on 3 Oct 2026 in this repo, in the local Windows build in `surfsense_local/electron/release/` (built 25 Sep 2026), and in upstream registries. Numbers are marked **measured** (with how) or **estimated**. Sibling streams: [01 sources and folders](01-sources-and-folders.md), [02 skills and engines](02-skills-and-engines.md), [03 editable artifacts](03-editable-artifacts.md), [05 model ladder and evals](05-model-ladder-and-evals.md), and [06 product shape](06-product-shape.md), which owns the interface names. Phases are numbered RT0 to RT6 so they do not collide with other streams' phase names, such as 06's R1. Milestones M0 to M10 are the [README](README.md)'s; the [Phases](#phases) table says which one carries each phase.

## Today

### Installer size and its two ceilings

- `makensis` is 32-bit and cannot map a payload over 2 GB ([packaging](../../architecture/packaging.md#the-nsis-size-limit)). GitHub refuses any release asset of 2 GiB or more: "Each file included in a release must be under 2 GiB" ([GitHub docs](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases)). The second ceiling applies to every platform and to anything SurfSense hosts on Releases.
- v2.0.3's assets, measured by research report I7 with `gh release view`: `SurfSense-Setup.exe` 1,129,150,720 B, `SurfSense-arm64.dmg` 1,261,147,542 B, `SurfSense-arm64.zip` 1,245,087,801 B, `SurfSense.AppImage` 1,360,618,521 B, `SurfSense.deb` 1,246,171,516 B. The 2.1.0 dry run on 3 Oct uploaded a 1,130,260,665 B Windows artifact. Headroom is about 0.87 GB on Windows and 0.79 GB on the AppImage, the tightest. [packaging](../../architecture/packaging.md#the-nsis-size-limit) still quotes 2.0.2's 1.30 GB.
- The local `SurfSense-Setup.exe` of 25 Sep is 1,935,572,620 B (**measured**, `ls -l`), about 0.8 GB more than CI's. `electron-builder.yml` copies `from: ../backend/models` whole ([`electron-builder.yml`](../../../surfsense_local/electron/electron-builder.yml)). Locally that folder holds the three real packs (docling 398 MB, audio 181 MB, bge-small 65 MB) plus `hub/` 506 MB (a Docling Hugging Face cache), `kokoro/` 338 MB (the pre-audio.cpp voice), `xet/` and a dev `models.ini` (**measured**, `du -sm`). No step prunes them.
- Differential updates are off, so every app update downloads the whole installer again ([updates](../../architecture/updates.md#consent)).
- No installer carries opencode or ripgrep yet. `ENABLED_BY_DEFAULT` is `false` in [`enabled.mjs`](../../../surfsense_local/electron/scripts/opencode/enabled.mjs), whose comment ties the flip to "the agent test", and the "Stage opencode" step in [`release-local.yml`](../../../.github/workflows/release-local.yml) stages nothing while it is off.

### What the frozen worker already carries

- [`worker.spec`](../../../surfsense_local/backend/bundling/worker.spec) runs `collect_all` on `docx`, `pptx`, `xlsxwriter` and `reportlab`, because Studio's Office formats run model-written code that imports them and no static import exists. It also collects Docling, RapidOCR, transformers and torchvision.
- openpyxl 3.1.5 and pypdfium2 5.13.0 are not declared in [`pyproject.toml`](../../../surfsense_local/backend/pyproject.toml). Both arrive only through `docling-slim`'s `standard` extra ([`uv.lock`](../../../surfsense_local/backend/uv.lock)).
- They are frozen, openpyxl only in part (**measured**: the PYZ of `backend/dist/worker/worker.exe`, read with PyInstaller's `CArchiveReader`, 12,448 modules). openpyxl has 176 of its 190 modules; the 14 missing, among them `openpyxl.utils.dataframe` and `openpyxl.worksheet.picture`, were never reached through Docling. pypdfium2 is complete with `pypdfium2_raw/pdfium.dll` (7 MB). lxml 6.1.3 is complete, its compiled modules as `.pyd` files. pandas, Pillow, defusedxml, cryptography and jinja2 are present; pypdf, pdfplumber, pdfminer, fontTools and matplotlib are absent. The worker also carries `faker` (738 modules, 9 MB), pulled in by `polyfactory` through `docling-slim`.
- The frozen API has no lxml, docx or openpyxl, but it has `tarfile`, `lzma`, `httpx` and `psutil` (**measured**, same method on `api.exe`). [`api.spec`](../../../surfsense_local/backend/bundling/api.spec) adds the two `models.json` manifests and the prompt folders as data, and nothing from `plugins/core/`.
- The frozen worker is not a Python. [`worker.py`](../../../surfsense_local/backend/worker.py) accepts a queue name or `--check-vision-runtime`, and calls `multiprocessing.freeze_support()`. It imports `worker.consumer` (Huey, the models, the queues) at module top, before it reads `argv`. The API already re-executes itself for its device probe, because "The frozen build has no interpreter to run `-m` with" ([`main.py`](../../../surfsense_local/backend/main.py) `probe_devices`). A frozen worker that only prints its usage starts in 0.8 to 1.7 s (**measured**, three runs), and that includes the consumer's imports.
- An idle Studio worker holds a 77 MB working set and 541 MB of private memory on Windows (**measured**, `worker.exe studio` after 20 s).
- Packaged, the Python sidecars run with `cwd` set to the resources folder ([`python.ts`](../../../surfsense_local/electron/src/main/sidecars/python.ts) `pythonCmd`). The local `win-unpacked/resources/` holds a stray `output.pdf`, most likely a model-written ReportLab script that wrote a relative path ([`runner.py`](../../../surfsense_local/backend/worker/studio/office/runner.py) runs model code with `exec()`).
- Ingest commits before it parses ("drop it before parsing"), so [`parsing.py`](../../../surfsense_local/backend/worker/ingestion/parsing.py) `markdown_for()` runs outside any transaction ([`pipeline.py`](../../../surfsense_local/backend/worker/ingestion/pipeline.py) `_ingest`).

### Interpreters and JavaScript

- [`plugin_interpreter.py`](../../../surfsense_local/backend/modules/plugins/plugin_interpreter.py) `plugin_python()` returns `sys.executable`, with the comment "The packaged worker is not a Python, so the app will ship one for plugins." Plugins therefore run only in development today. The design pins python-build-standalone CPython at [`build-targets.json`](../../../plugins/core/build-targets.json) `"python": "3.12"` for `windows-x64`, `macos-arm64` and `linux-x64` ([plugin interpreter](../plugins/bundles/python/01-interpreter.md)). The staging script it names, `fetch-plugin-python.mjs`, does not exist. Plugin dependencies may be compiled wheels, installed after the app is ([plugin packaging](../plugins/bundles/release/01-packaging.md)).
- opencode's environment puts opencode's own folder, then the system `PATH`, on `PATH` ([`opencode.ts`](../../../surfsense_local/electron/src/main/sidecars/opencode.ts) `opencodeEnvironment`). `python` in the agent's shell is the user's own, or on Windows the Store stub. Its proxies point at `127.0.0.1:9`, so nothing it starts can install packages.
- Two JavaScript runtimes already ship. `ELECTRON_RUN_AS_NODE=1 electron.exe` reports Node 24.20.0 on Electron 44.2.0, and `BUN_BE_BUN=1 opencode.exe --version` reports Bun 1.3.14 (**measured** on the staged binaries). Neither ships npm.
- No Electron fuses are configured: nothing in `src/`, `scripts/` or `electron-builder.yml` mentions fuses, and nothing in the app sets `ELECTRON_RUN_AS_NODE` (**measured**, grep). electron-builder 26.16.1, the pinned version, supports `electronFuses`, `win.signExts`, `mac.signIgnore` and `mac.binaries`, but not per-file entitlements (its `configuration.d.ts` and `macOptions.d.ts`).

### Downloads after install

- GGUF downloads stream with resume and an optional sha256, and set `follow_redirects=True` ([`download.py`](../../../surfsense_local/backend/modules/llm/providers/llamacpp/download.py)). The gate is `transact(session, egress.require, egress.HUGGINGFACE)` before the job starts ([install router](../../../surfsense_local/backend/modules/llm/catalog/local/install_jobs/router.py)). Install jobs run in the API, in memory, one at a time, behind the catalogue's install lock ([`jobs.py`](../../../surfsense_local/backend/modules/llm/catalog/local/install_jobs/jobs.py) `InstallJobs`, which is typed to models).
- `BUILT_IN` holds only `host:huggingface.co` ([`service.py`](../../../surfsense_local/backend/modules/egress/service.py)). The plugin installer design adds `host:github.com` and `host:release-assets.githubusercontent.com`, allows a redirect only to the second, and checks sha256 before it extracts ([plugin install](../plugins/bundles/install/01-install-update-uninstall.md)).
- Settings › Network already shows an "App updates" row with host `github.com`. electron-updater runs in the main process, out of reach of `egress.require()`, and is gated by the `automatic` preference in `updates.json` ([egress](../../architecture/egress.md), [updates](../../architecture/updates.md)). Egress has "one row per host by construction", and a host's dialog "names every errand" ([ADR 0027](../../adr/0027-egress-consent-per-host.md)).
- The docs disagree on executable downloads. The agent proposal says "The installer downloads nothing. Anything fetched later is fetched by the running app after egress consent" ([agent README](../agent/README.md), Locked decisions). [`cuda-backend.md`](../cuda-backend.md) says an opt-in post-install CUDA pack was intended, "which the airgapped rule later ruled out". No ADR states that rule; ADR 0004, 0014, 0016, 0017 and 0019 describe the app as airgapped, and [ADR 0030](../../adr/0030-formatjs-renders-interface-text.md) forbids fetching translations at run time.
- The app's updater takes the newest entry of `MODSetter/SurfSense`'s releases feed (`allowPrerelease = true`), not GitHub's Latest pointer ([updates](../../architecture/updates.md#two-apps-one-repo)). The plugin design publishes into a second repository, `SurfSense-Inc/surfsense-plugin-releases`, through an organisation-owned GitHub App scoped to that repository and a `plugin-publishing` environment ([plugin publishing](../plugins/bundles/release/03-publishing.md)). None of the three exists yet: they are that design's one-time setup steps. On 3 Oct 2026 `gh repo view SurfSense-Inc/surfsense-plugin-releases` finds no repository, and this repository's environments are `github-pages`, `Preview` and `Production` (`gh api …/environments`). The plugin catalogue refresh reads `releases/latest/download/plugin-catalog.json` from that repository, so whatever release is marked Latest there must carry the catalogue ([plugin protocol](../plugins/bundles/01-protocol.md)).

### Signing and notarization

- On a `v*` tag, electron-builder signs every `.exe` under `resources/` and no `.dll` or `.pyd` (I7, from the 2.1.0 dry-run log). The local worker holds 323 `.dll` and `.pyd` files, of which 89 carry a valid upstream signature, such as the PSF's on `python312.dll` (**measured**, `Get-AuthenticodeSignature`).
- The macOS app uses the hardened runtime. `entitlementsInherit: build/entitlements.mac.plist` gives every nested binary `allow-jit`, `allow-unsigned-executable-memory`, `disable-library-validation` and `allow-dyld-environment-variables` ([`entitlements.mac.plist`](../../../surfsense_local/electron/build/entitlements.mac.plist), whose comment says the frozen sidecars and llama-server need the last two).
- The 2.1.0 macOS dry run failed at notarization with Apple's 403 "A required agreement is missing or has expired" (I7, run 37102724459). The early credential check runs only on tag pushes ([`release-local.yml`](../../../.github/workflows/release-local.yml) "Verify Apple notarization credentials").

### Licences

- No CI step checks dependency licences, and "No third-party license notices ship with the app" ([about](../../architecture/about.md)). The plugin pull-request checks already define a rule, the ASF's Category A and B ([plugin checks](../plugins/bundles/release/02-pull-request-checks.md)).
- The backend's environment has 142 distributions. By their metadata only these are not plainly permissive (**measured**, `importlib.metadata`): certifi (MPL-2.0), tqdm (MPL-2.0 AND MIT), huey (no licence metadata), and the dev-only pyinstaller and pyinstaller-hooks-contrib (GPL-2.0 with the bootloader exception).
- **Metadata misses bundled binaries.** opencv-python 5.0.0.93, which arrives through RapidOCR, declares "Apache 2.0", yet its wheel carries FFmpeg as `cv2/opencv_videoio_ffmpeg500_64.dll` (30.9 MB) with the LGPL-2.1 text in `LICENSE-3RD-PARTY.txt` ("FFmpeg is redistributed within all opencv-python packages"). The same DLL is in the frozen worker's `_internal/cv2/` (**measured**, `backend/.venv` and `release/win-unpacked`). Other third-party native code rides inside permissive wheels the same way: PDFium in `pypdfium2_raw`, and torch's `libiomp5md.dll` and `uv.dll` in `torch/lib/`.
- The frontend's production dependencies are 717 packages under 16 licence ids (**measured**, `pnpm licenses list --prod`). The ones a gate must decide are jszip `(MIT OR GPL-3.0-or-later)`, lightningcss MPL-2.0, caniuse-lite CC-BY-4.0, and `buffers@0.1.1` with no licence.
- eSpeak-ng 1.52.0 ships beside `audiocpp_server` under GPL-3.0-or-later, with its licence text ([`audiocpp/pins.mjs`](../../../surfsense_local/electron/scripts/audiocpp/pins.mjs)). It is a separate process, not linked into SurfSense code.

### LibreOffice, measured

The LibreOffice 25.2.7.2 installed on the development machine was copied into a scratch folder, trimmed, and run from there (**measured**). 25.2 reached end of life on 30 Nov 2025, so these figures are a guide, not the pinned build's:

| | Full install | Trimmed copy |
|---|---|---|
| Unpacked | 720 MB | 489 MB |
| `tar` + `xz -9` | not measured | 113,126,484 B |
| `tar` + `gzip -6` | not measured | 171,869,382 B |

- The trim removed `help/`, `share/extensions` (dictionaries), `share/gallery`, `share/template`, `share/wizards`, `share/xpdfimport`, `share/Scripts`, every icon theme except `images_colibre.zip`, the bundled Python 3.10, and the updater (`updater.exe`, `update_service.exe`, `updchklo.dll`, `updatecheckuilo.dll`).
- From the scratch folder, with a seeded profile (`-env:UserInstallation`), `soffice.com --headless --convert-to pdf` converted a python-docx DOCX and a python-pptx PPTX, so a copied tree runs from another folder.
- xlsxwriter cached 0 for `=A1*A2` and `=SUM(A1:A3)*10`. Round-tripped through the copy with `OOXMLRecalcMode` 0, openpyxl's `data_only` read 6 and 110. One small conversion took 1.1 to 1.2 s with a warm profile; three files with a fresh profile took 4.9 s and peaked at a 400 MB working set.
- 162 of the 163 executables and libraries left carry The Document Foundation's valid Authenticode signature; the exception is `fbintl.dll`, from Base's Firebird engine.
- On 3 Oct 2026 TDF's stable folder lists 25.8.7, 26.2.5, 26.2.6, 26.8.0 and 26.8.1 ([download.documentfoundation.org](https://download.documentfoundation.org/libreoffice/stable/)). 25.8 ended on 12 Jun 2026, 26.2 ends on 30 Nov 2026 and 26.8 on 13 Jun 2027 ([endoflife.date](https://endoflife.date/libreoffice), which follows TDF's release plan).
- In the skills project a fresh profile let LibreOffice's MAR updater and its elevated Maintenance Service upgrade the user's install from 24.8.7.2 to 25.2.7.2. The project's rule disables updates three ways and strips `LIBO_UPDATER_*`, notes that "a Job Object cannot stop an elevated service", and records that one approved run must still show an unchanged `version.ini` build id (`references/skills_to_improve/docs/LESSONS.md`, lessons 9 and 10).
- Viewers and previews show a workbook's cached values; only Excel's full load refreshes them (LESSONS.md, lesson 2).

## Decisions

1. **The engines run in the frozen worker, in a child the worker starts from its own binary, and the child never imports the queue consumer.** The worker already holds nearly every library they need, and `--engine-op` follows the API's `--probe-devices` precedent ([`main.py`](../../../surfsense_local/backend/main.py)). [02](02-skills-and-engines.md) owns the child and the queue; this stream owns the spec, the libraries and the dispatch in `worker.py`.
2. **Every library an engine imports is declared in `pyproject.toml` and collected by name in `worker.spec`.** openpyxl, pypdfium2 and jsonschema arrive through Docling, and a frozen openpyxl already lacks 14 modules. A Docling bump must not remove an engine's dependency.
3. **pypdf joins the worker; pdfplumber and IronCalc wait.** pypdf (BSD-3, 0.40 MB wheel) does PDF forms, merge and split. IronCalc 0.8.3 is an alpha release with no licence metadata beyond classifiers ([PyPI](https://pypi.org/project/ironcalc/)); whether 02's xlsx engine uses it is 02's call, after open question 7, and its values never enter a delivered file (decision 17). pdfplumber would bring a 6.59 MB pdfminer.six wheel for tables Docling and pypdfium2 already cover, so it waits for a failing PDF engine test.
4. **No JavaScript runtime is used for documents, and the RunAsNode, NODE_OPTIONS and inspect fuses are switched off.** Python builders cover creation, so docx-js has no caller. The app never runs Electron as Node. The main executable is the one users launch, the one macOS privacy grants are recorded against and the one Windows publisher rules recognise; with the fuses on, one environment variable turns it into a Node host, and a launcher can inject code into the running app ([Electron fuses](https://www.electronjs.org/docs/latest/tutorial/fuses)). The plugin interpreter, a separate executable, is weighed on its own in decision 5 and Options.
5. **No general Python ships for the engines or the agent's shell. The plugin interpreter ships with the plugin runtime, for plugins only, under its own minimal macOS entitlements.** Engines need no interpreter, [02](02-skills-and-engines.md) §6 sets bash from 05's capability, and 02 rejects a standalone Python for the agent. Plugins cannot run packaged without one. On macOS the interpreter is signed with `disable-library-validation` alone, which plugin wheels installed after the app need, and without the dyld-environment and JIT keys every other nested binary inherits. Putting it on the agent's `PATH` is a separate proposal, gated on 05 matrix evidence that frontier agents fail without it and reconciled with 02.
6. **LibreOffice is an optional runtime pack, shown as "Office support", never part of the installer.** [06](06-product-shape.md) keeps the word "pack" in the interface for job content, so the pack appears under Settings › Downloads as "Office support (LibreOffice)" and a feature that needs it says "Needs Office support". This document calls it the Office pack. It would add about 113 MB on Windows (measured on 25.2) and about 300 MB on macOS (estimated), downloaded again with every release because differential updates are off. As a pack it downloads once per pinned version, for those who ask.
7. **The running app may download pinned third-party runtime binaries, unaltered except for deleted files, after per-host consent, and a new ADR says so.** It reconciles [`cuda-backend.md`](../cuda-backend.md) with the agent README and the plugin design, and names executable downloads as a new class against the airgapped framing of ADR 0004, 0014 and 0017. The installer still downloads nothing, and every feature it ships works without a pack.
8. **SurfSense CI builds packs and hosts them as releases in `SurfSense-Inc/surfsense-plugin-releases` under a `runtime-` tag prefix, with URLs, sizes and sha256s compiled into the app.** That repository will have the publisher App, its single-repository scope and the protected environment, so packs add no credential of their own. None of them exists today, so creating them is an RT3a task with named owners, following the plugin design's setup: an owner of SurfSense-Inc creates the repository and the App, and MODSetter creates the `plugin-publishing` environment and stores the App's ID and key. A `runtime-` release is never marked Latest, because the plugin catalogue refresh reads the Latest release. Re-hosting removes LibreOffice's mirror redirects; staying off `MODSetter/SurfSense` keeps pack releases out of the feed the updater reads; compiled-in pins need no remote catalogue and add no trust root.
9. **A pack download follows exactly one redirect, `github.com` to `release-assets.githubusercontent.com`, and refuses any other before writing a byte.** Consent is per host ([ADR 0027](../../adr/0027-egress-consent-per-host.md)); a redirect elsewhere is egress nobody allowed.
10. **The Office pack keeps LibreOffice's signed binaries untouched: Windows and Linux are trimmed by deletion only, and macOS ships TDF's `.app` whole.** Deletion keeps TDF's per-file Authenticode signatures (162 of 163 valid, measured). Any change inside a macOS bundle breaks its seal, and SurfSense cannot notarize a re-signed copy today.
11. **The pack pins the newest point release of the oldest TDF branch with at least six months of fixes left at the app's release, at `.1` or later.** Today that is 26.8.1: 26.2 ends on 30 Nov 2026. A pin must never start on an ended branch, and each app release re-applies the rule, so a LibreOffice security fix still needs an app release.
12. **A LibreOffice the user already has is used only after they confirm it once in Settings › Downloads, and only if it is a supported TDF branch, carries no shared extensions and sits at a fixed install path.** Customer documents are untrusted input, an ended branch gets no security fixes, and a shared extension loads into every profile. It always runs under SurfSense's own profile, with updates off three ways and `LIBO_UPDATER_*` stripped (lessons 9 and 10).
13. **One LibreOffice process runs at a time, app-wide, with a seeded profile, the caller's deadline, a bounded wait for the lock, macros and link updates off, proxies pointed at nowhere, and a copy whose external links are removed.** Three small files peaked at 400 MB (measured), Lambda guidance is at least 3,008 MB ([shelfio](https://github.com/shelfio/aws-lambda-libreoffice)), and llama-server is resident beside it. A shared profile collides on its lock. A DOCX or XLSX can pull another local file into a render through a `file:` link, a field or DDE, and a profile key is not a test.
14. **LibreOffice runs only outside the engine child and outside `transact()`, in a named process for each consumer.** Recalculation runs in the engines worker after the child exits, thumbnails in a Studio job after commit, PDF export in a Studio export job, and legacy conversion in the ingest worker before Docling. A slow conversion must not kill an edit, and SQLite's 5 s busy timeout rules out holding a transaction across one.
15. **Liberation, Carlito and Caladea ship in the installer; CJK fonts are a pack.** The three are OFL-1.1, 7.7 MB (E5), and metric-compatible with Arial, Times New Roman, Calibri and Cambria, which keeps line breaks close to Word. One CJK region subset is 35 to 66 MiB (E5).
16. **One licence policy gates the frozen binaries, every native library inside them, the renderer bundle, every staged runtime and every pack, and writes the notices file the app ships.** GPL and AGPL code never runs in-process with Apache-2.0 code; LGPL is allowed only as a separate, replaceable shared library with its text and a source pointer; the PyInstaller bootloader's exception is a policy rule, not an override. Metadata alone missed FFmpeg inside opencv-python.
17. **Recalculated values from LibreOffice may become a delivered workbook's cached values, and the report names them; values from IronCalc never do; without LibreOffice, stale cached values are cleared.** Every delivered workbook keeps its formulas and `fullCalcOnLoad="1"`. Previews and Protected View show cached values (lesson 2): a blank is visible, a stale or wrongly computed number is not.
18. **One GitHub consent covers every errand on `github.com` and `release-assets.githubusercontent.com`: app updates, runtime packs and, once they ship, plugins.** Egress has one row per host, and the dialog must name every errand ([ADR 0027](../../adr/0027-egress-consent-per-host.md)). Two rows for one host, or a pack grant that silently allows plugins, would break both rules.
19. **The Office pack is free.** The pricing FAQ says "everything the app itself does stays free" ([`pricing-content.ts`](../../../surfsense_web/components/pricing/pricing-content.ts)), and the pack is someone else's MPL code with no SurfSense feature in it. A runtime pack is not a job pack.
20. **opencode stays on the pinned 1.x line; a move to 2.x is its own change.** 2.x ships only as npm platform packages, its Windows executable is 207 MB against 181 MB (I7), and whether `BUN_BE_BUN` survives is unknown. [02](02-skills-and-engines.md) decision 15 and [05](05-model-ladder-and-evals.md) decision 10 rely on the same pin.

## Design

### 1. Inventory per phase

What each phase needs at run time, where it comes from, and what changes. "Have" means present in today's frozen worker (measured above).

| Need | Used by | RT1 engines | RT3 Office pack | RT4 interpreter | Source and licence |
|---|---|---|---|---|---|
| lxml 6.1.x | docx and xlsx engines, the render-copy cleaner | have; declare `lxml>=6.1,<7` | | | BSD-3; 7.0.0b1 exists, so the cap holds until 7.0 is final |
| openpyxl 3.1.5 | xlsx inspect, 03's read-only bodies, reading recalculated values | have, partial; declare and `collect_all` | | | MIT; never saves a customer workbook |
| python-docx, python-pptx, xlsxwriter, reportlab | builders, Studio | have | | | MIT, MIT, BSD-2, BSD |
| pypdfium2 5.13 | pdf pages, page PNGs | have; declare and `collect_all` | renders the pack's PDFs to PNG | | Apache-2.0 / BSD-3; PDFium licences must ship |
| pypdf 6.19 | pdf forms, merge, split | **add** | | | BSD-3, 0.40 MB wheel |
| ironcalc 0.8.3 | candidate for 02's xlsx checks | | | | alpha; classifiers MIT and Apache-2.0; 02's call after open question 7 |
| jsonschema | 02's plan check | have, through Docling; declare | | | MIT |
| `surfsense_engines` and its data | all engines | **add** (02's package) | | | Apache-2.0; XSDs per 02's provenance record |
| `anthropic` SDK, `jiter`, `distro`, `docstring-parser` | [05](05-model-ladder-and-evals.md)'s native provider, API and worker | **add** with 05 P1 (M4), ahead of the rest of RT1 | | | MIT; 1.68 + 0.23–0.35 + 0.02 + 0.02 MB wheels |
| opencv-python's FFmpeg DLL | nothing SurfSense calls | have; candidate removal | | | LGPL-2.1 inside an Apache-2.0 wheel |
| Fonts | reportlab PDFs, the pack, viewers | **add** `resources/fonts/` | the pack's own copy | | OFL-1.1 |
| LibreOffice | render, full recalculation, legacy formats | | **pack** | | MPL-2.0, unaltered except deleted files |
| CPython 3.12 | plugins | | | **add** `resources/python/` | PSF; PBS builds against libedit, not GPL readline (E5) |
| Node, Bun, docx-js, pptxgenjs | nothing | | | | not shipped |
| pdfplumber, pdfminer.six | nothing yet | | | | MIT; waits for a failing test |
| PyMuPDF, ONLYOFFICE x2t, HyperFormula, pycel, pandoc | never | | | | AGPL, AGPL, GPL-3, GPL-3, GPL-2+; refused by the gate |

Package sizes are wheel sizes from PyPI's JSON API, read on 3 Oct.

### 2. The worker spec and entry point

Changes to [`worker.spec`](../../../surfsense_local/backend/bundling/worker.spec), each with the reason the analyser cannot find it alone:

```python
for package in (
    ...,
    # Engines and Studio bodies import these; Docling's extra is not a contract,
    # and a frozen openpyxl already lacked 14 modules the analyser never reached.
    "openpyxl",
    "pypdfium2",
    "pypdfium2_raw",
    "pypdf",
    # Engines load their plan schemas and XSDs by path, so the package and its
    # data are collected whole.
    "surfsense_engines",
):
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(package)
```

- 02's engines are a library with direct imports ([02](02-skills-and-engines.md) decision 3). The skills project dispatched subcommands through a `SUBCOMMANDS` table and `importlib.import_module`, and found `plan_schema.json` and its fonts through `__file__` (`references/skills_to_improve/shared/src/docx_redline.py`, `docxkit/plan.py`, `office/fonts.py`). A carried-over module that keeps a string import goes into `hiddenimports`; the packaging test below catches any it misses.
- **Entry point.** `worker.py` reads `argv` first and imports `worker.consumer` only in the queue branch, so an `--engine-op` child and both checks never load Huey, SQLAlchemy's models or the queues:

  ```python
  if __name__ == "__main__":
      import multiprocessing

      multiprocessing.freeze_support()
      arguments = sys.argv[1:]
      if arguments[:1] == ["--engine-op"]:
          # A child per engine operation: load the engine, not the queue.
          from worker.engines.engine_op import main as engine_op
          engine_op(arguments[1:])
      elif arguments == ["--check-engine-runtime"]:
          check_engine_runtime()
      elif arguments == ["--check-vision-runtime"]:
          check_vision_runtime()
      elif len(arguments) == 1:
          from worker.consumer import consume
          consume(arguments[0])
      else:
          sys.exit("usage: worker.py <ingest|studio|plugins|engines>")
  ```

- `--check-engine-runtime` imports every engine module, loads each engine's data through `importlib.resources`, renders a fixture PDF page with pypdfium2 and opens it with pypdf, then prints whether `worker.consumer` is in `sys.modules` and how long the start took. `release-local.yml` runs it after freezing, as it runs the vision check.
- The API spec gains `packs.json` and nothing for the engines: only the worker runs them ([02](02-skills-and-engines.md) section 1). With 01 phase 4b (M8) it also gains `collect_all("watchfiles")`, and `pyproject.toml` declares watchfiles 1.2.0, which today arrives only through `uvicorn[standard]` ([`uv.lock`](../../../surfsense_local/backend/uv.lock)); 01's packaging test imports `watchfiles._rust_notify` in the frozen API ([01](01-sources-and-folders.md)).
- The Studio builders keep `collect_all` on `docx`, `pptx`, `xlsxwriter` and `reportlab`. Where a builder format does not yet reach the `exec()` baseline on a local model, that format keeps the `exec()` path there ([02](02-skills-and-engines.md) phase B), and that path imports them at run time.
- Candidate removals, each behind a packaging test: `faker` and `polyfactory` through `excludes`, about 9 MB unpacked, once a test shows Docling never imports them; and opencv-python's `opencv_videoio_ffmpeg*.dll`, 30.9 MB unpacked, filtered out of `binaries` once `--check-vision-runtime` and an OCR fixture pass without it. cv2 loads that plugin only for video I/O (estimate, which the test settles). Removing it also removes the one LGPL library in the worker.
- 02's engines worker is a fourth sidecar. If its consumer imported what the Studio consumer does, it would idle at 541 MB private on Windows (measured above); it imports only `modules.engine_runs.tasks` at start ([02](02-skills-and-engines.md) section 4). It never loads the embedding encoder: chunks and vectors for engine and agent versions are computed by the Studio worker ([03](03-editable-artifacts.md)'s `index_version` for engine versions and `version_job` for agent versions), never the engines worker.
- **Memory.** The README's whole-stack budget records idle and busy private bytes per process on a 16 GB Windows laptop with integrated graphics, at the M5 and M6 exits. From this stream it counts the engines worker idle and during an operation and the `--engine-op` child; RT3b (M8) adds LibreOffice's conversion peak beside a resident llama-server (400 MB working set on three small files, measured on 25.2).

### 3. Size budget

All figures are compressed installer bytes in decimal MB. "Measured" means a release asset, an upstream download or a local measurement. "Estimated" means a sum of measured parts, recompressed by NSIS, hdiutil or AppImage's squashfs.

| | Windows NSIS | macOS DMG | AppImage |
|---|---|---|---|
| Binding ceiling | 2,000 (makensis) | 2,147 (GitHub) | 2,147 (GitHub) |
| v2.0.3 (measured) | 1,129 | 1,261 | 1,361 |
| + opencode and ripgrep, from M5, when `ENABLED_BY_DEFAULT` turns true (measured archives) | +62 | +46 | +61 |
| + engine libraries: pypdf, engines, schemas, Anthropic SDK in two binaries (estimated from wheels) | +6 | +6 | +6 |
| + fonts (estimated from 7.7 MB of TTF) | +5 | +5 | +5 |
| + skills folder and notices (estimated) | +1 | +1 | +1 |
| **After RT1–RT3** | **1,203** | **1,319** | **1,434** |
| Headroom | 797 | 828 | 713 |
| + RT4 interpreter: PBS `install_only_stripped` 22.0 / 25.0 / 34.3 MB (measured) | +22 | +25 | +34 |
| **After RT4** | **1,225** | **1,344** | **1,468** |
| Headroom | 775 | 803 | 679 |
| *Rejected:* LibreOffice in the installer | about +113 (measured on 25.2, Windows trim) | about +300 (estimated from the 298.8 MB upstream DMG) | +110 to 150 (estimated) |

- The Office pack does not appear in the installer. On disk it took 489 MB on Windows (measured, trimmed 25.2.7), about 1 GB on macOS (estimated, untrimmed) and 450 to 550 MB on Linux (estimated). RT3b re-measures all three on the pinned version, and the manifest carries the real figures.
- A local build leaks about 0.8 GB of model caches. Phase RT0 fixes it with an allowlist on the `models` entry in `electron-builder.yml`:

  ```yaml
  - from: ../backend/models
    to: models
    # Only the three packs packaging.md lists; dev caches (hub/, kokoro/, xet/)
    # pushed a local Setup.exe to 1.94 GB, 0.8 GB over CI's.
    filter: ["bge-small-en-v1.5/**", "audio/**", "docling/**"]
  ```

  A packaging test asserts that `resources/models` holds exactly those three folders.
- `scripts/check-installer-size.mjs` runs in `release-local.yml` after `electron-builder`, prints each artifact's size and its change from the last release (`gh release view`), and fails above 1,700 MB on Windows or 1,850 MB elsewhere. The line keeps at least 300 MB below each ceiling for torch, Docling and Chromium growth, which no proposal controls. After RT4 it still leaves about 475 MB on Windows. The gate ships in M0 and measures the artifacts as built, so from the M5 release it counts opencode and ripgrep without a change. That release flips `ENABLED_BY_DEFAULT`, once [05](05-model-ladder-and-evals.md)'s `agent_smoke` and `free_agent_tasks` rows on the native Claude route are committed and [03](03-editable-artifacts.md) phase 3 makes agent files into versions; `enabled.mjs`'s comment then points at those rows and 05's capability rule. Until then agent threads stay behind the developer switch.
- A llama.cpp bump ([05](05-model-ladder-and-evals.md) phase P5a, M9) is a pin change in `fetch-llamacpp.mjs` (82 MB unpacked today, I7); the size gate catches one that grows.

### 4. Python: who needs an interpreter

| Consumer | Needs a real interpreter? | What it gets |
|---|---|---|
| Engines (02) | No | the frozen worker, re-executed with `--engine-op` |
| Fixed workflows (02, 05) | No | the same engines in the worker |
| Studio builders | No | the worker |
| Plugins | Yes: a plugin is source run with `python -m` | PBS 3.12, RT4 |
| The agent's shell | Not in this proposal: [02](02-skills-and-engines.md) §6 sets bash from 05's capability and refuses a standalone Python for skills | the user's own `python`, as today |

PBS ships in the installer, never as a pack: it costs 22 to 34 MB (section 3), and shipped it is signed and, on macOS, sealed inside the notarized bundle. An unsigned download would be neither.

**Staging.** `scripts/python/pins.mjs` pins python-build-standalone `20261003`, CPython 3.12.15 `install_only_stripped`, one URL and sha256 per `build-targets.json` platform. `scripts/python/stage.mjs` follows `scripts/opencode/stage.mjs` (`pinned-download.mjs`, a version smoke, an atomic swap) and in between:

1. removes `pip`, `ensurepip`, `idlelib`, Tcl/Tk, `test/` and `include/` ("The user's machine never runs `pip`", [plugin packaging](../plugins/bundles/release/01-packaging.md));
2. byte-compiles with `compileall --invalidation-mode unchecked-hash`, since the AppImage is read-only and a write into a macOS bundle breaks its seal;
3. asserts Python 3.12, `import ssl, sqlite3`, and a `ctypes` callback, which libffi closures need.

It replaces the plugin proposal's `fetch-plugin-python.mjs` and `electron/plugin-python/`; the folder is `electron/python/`, shipped as `resources/python/`.

**Wiring.**

- `electron-builder.yml` gains `from: python, to: python`.
- `pythonEnv()` in `python.ts` passes `SURFSENSE_LOCAL_PYTHON_DIR` to the API and the workers. `plugin_python()` returns the interpreter inside it when the variable is set and the file exists, and `sys.executable` otherwise, as the plugin design already says. Plugins keep their from-scratch environment ([plugin runtime](../plugins/bundles/runtime/01-process.md)).
- opencode's environment does not change.

**Signing.** On Windows, electron-builder signs `python.exe` and `pythonw.exe` with the app's identity, as it signs every `.exe` under `resources/`. A publisher rule that trusts SurfSense's certificate therefore trusts a general interpreter too; the security notes in [packaging](../../architecture/packaging.md) say so and recommend path rules. On macOS, electron-builder cannot set entitlements per file, so:

- `mac.signIgnore` names `python/bin/python3.12`;
- an `afterPack` hook, `scripts/python/sign-mac.mjs`, signs that one file with `codesign --options runtime --timestamp --entitlements build/entitlements.python.plist` before electron-builder signs the bundle;
- `entitlements.python.plist` holds `com.apple.security.cs.disable-library-validation` only, because a plugin's compiled wheels are installed into the data folder after the app and carry no SurfSense signature. It omits `allow-dyld-environment-variables`, `allow-jit` and `allow-unsigned-executable-memory`, unless the `ctypes` smoke above shows libffi needs the JIT key (open question 8).

The interpreter's signing identifier differs from the app's, so macOS privacy grants made to SurfSense do not apply to it (estimate, checked in RT4 with `codesign -d` and a TCC-protected read).

**JavaScript, if it is ever needed.** docx-js's native Word charts are the one feature without a Python equivalent today. python-pptx's chart XML writer emits the same DrawingML chart part a DOCX embeds, so [02](02-skills-and-engines.md) can build charts in Python (estimate, untested). If JS still becomes necessary, the order of preference is: opencode's Bun under `BUN_BE_BUN=1`, smoked on every opencode pin bump, with a pre-bundled docx-js (1.24 MB UMD, E5); then a pinned Node 24 LTS (37.6 MB Windows zip, E5). Electron as Node is not an option once the fuse is off.

### 5. Electron fuses

`electron-builder.yml` gains:

```yaml
# The app never runs Electron as Node. Left on, these let one environment
# variable or argument turn the app's own executable into a Node host or
# inject code into it.
electronFuses:
  runAsNode: false
  enableNodeOptionsEnvironmentVariable: false
  enableNodeCliInspectArguments: false
```

`release-local.yml` reads the packaged binary's fuses with `@electron/fuses` 1.8.0, already installed as electron-builder's dependency, and fails if any of the three is on. The update path needs one manual check per platform before the first release with fuses: N to N+1 must install (open question 6).

### 6. The Office pack

**What it is for, and who calls it.** Every caller runs outside `transact()` and outside 02's engine child, and passes a deadline.

| Job | Calling process and function | Phase | Without the pack |
|---|---|---|---|
| Recalculating an edited workbook | engines worker, `worker/engines/office_step.py` `recalc_after(version_id, deadline)` ([02](02-skills-and-engines.md)), after the `--engine-op` child exits and before the version finishes, with its own 150 s budget, separate from and after 02's 180 s child limit | RT3b (M8); 02 phase 5a (M7) ships first and uses the right-hand column until then | cached values of changed formulas cleared, `fullCalcOnLoad`, the report says so |
| Before and after slide thumbnails | Studio worker, a job enqueued after the version commits, `worker/studio/shared/thumbnails.py` `render_thumbnails(version_id)`; [03](03-editable-artifacts.md) decides where the PNGs are stored | RT3b (M8), used from 03's pptx diff | badge and per-slide text diff only |
| PDF export of a DOCX or PPTX version | Studio worker, an export job that 03's export route enqueues, `worker/studio/shared/pdf_export.py` `export_pdf(version_id, deadline)`, which converts a copy of the version's file; [03](03-editable-artifacts.md) owns the route and the save dialog | 03 phase 7 (M10), on RT3b | export offers the Office format only |
| Legacy `.doc`, `.xls`, `.ppt`, `.rtf`, `.odt` | ingest worker, `parsing.py` `_markdown_from()` converts a copy to OOXML before Docling | RT6 (M8), with 01 | unreadable until RT6, and 01's root header counts them; "Needs Office support" after |

02's `export_document` writes its `external` and `issues` kinds with engines alone, so it never calls the pack. Renders are QA signals, not proof of what Word shows. LibreOffice's OOXML import differs from Word's (E5).

Every caller's message about the pack, such as "LibreOffice was busy; values not recalculated", is a `{code, values}` line, as in 02's reports, rendered through the ICU catalogs with English as the fallback ([02](02-skills-and-engines.md)).

**Building it.** `.github/workflows/build-runtime-packs.yml` runs on `workflow_dispatch` from `main` with a pack id and an upstream version, on the three release runners. Scripts live in `surfsense_local/electron/scripts/packs/office/` and reuse `pinned-download.mjs`:

- `pins.mjs`: TDF's MSI, DMG and deb tarball for one version, with URLs on `download.documentfoundation.org` and their sha256s. This is a CI fetch, never a user's.
- `build.mjs`:
  - Windows: `msiexec /a <msi> /qn TARGETDIR=<dir>` (an administrative image), then the measured trim list. `fbintl.dll` and `Engine12.dll` (Firebird) go only after the smoke passes without them.
  - Linux: `dpkg-deb -x` of the Writer, Calc, Impress, Draw and core debs into one tree, then the same trim. A gate like audio.cpp's checks for no symbol newer than `GLIBC_2.34` and lists the system libraries headless mode still opens.
  - macOS: copy `LibreOffice.app` out of the DMG unchanged.
- Each runner then writes `PROVENANCE.json` (upstream URL, sha256, the trim list) and `SOURCE.txt` (TDF's source archive for that exact version under `https://download.documentfoundation.org/libreoffice/src/<version>/`, and the `libreoffice-<version>` tag), keeping `LICENSE`, `NOTICE` and `readmes/`. It runs the smoke through the app's own runner code: one DOCX, one PPTX and one `.doc` to PDF, and the fixture workbook recalculated to 6 and 110, then the `office`-marked tests below. macOS adds `codesign --verify --deep --strict` and `spctl --assess --type execute`; Windows fails on any unsigned PE file beyond the reviewed list. It records the archive's size and unpacked size.
- The upload job runs in the `plugin-publishing` environment and turns `PLUGIN_PUBLISHER_APP_ID` and `PLUGIN_PUBLISHER_PRIVATE_KEY` into a token with `actions/create-github-app-token` (`owner: SurfSense-Inc`, `repositories: surfsense-plugin-releases`), as [plugin publishing](../plugins/bundles/release/03-publishing.md) does. It uploads `office-<lo-version>-<n>-<platform>.tar.xz` with those files to the release `runtime-office-<lo-version>-<n>`, created with `gh release create --latest=false` so the plugin catalogue's Latest release never moves, and prints the `packs.json` entry for a reviewed pull request. MODSetter starts the workflow; the pull request's reviewer owns the pin.
- **One-time setup, an RT3a task.** The repository, the App and the environment are created as [plugin publishing](../plugins/bundles/release/03-publishing.md) sets out: an owner of SurfSense-Inc creates the public repository `SurfSense-Inc/surfsense-plugin-releases` and the "SurfSense plugin publisher" App, installed on that repository alone with Contents read and write; MODSetter creates the `plugin-publishing` environment and stores `PLUGIN_PUBLISHER_APP_ID` and `PLUGIN_PUBLISHER_PRIVATE_KEY` in it. The environment admits `main`, as `build-runtime-packs.yml` needs. Whichever of RT3a and the plugin installer starts first does the setup; until then no pack can be published, and M8 lists it as a dependency.

**The manifest.** `modules/runtime_packs/manifest/packs.json` ships in the API binary, as the model manifests do ([`api.spec`](../../../surfsense_local/backend/bundling/api.spec) names its data files). Platform keys are written into it, not read from `build-targets.json` at run time, because the frozen API carries nothing from `plugins/core/`:

```json
{
  "schema": 1,
  "packs": {
    "office": {
      "version": "26.8.1-1",
      "upstream": "LibreOffice 26.8.1",
      "branch_end": "2027-06-13",
      "detected_branches": {"26.2": "2026-11-30", "26.8": "2027-06-13"},
      "platforms": {
        "windows-x64": {
          "url": "https://github.com/SurfSense-Inc/surfsense-plugin-releases/releases/download/runtime-office-26.8.1-1/office-26.8.1-1-windows-x64.tar.xz",
          "sha256": "<64 hex>",
          "size": "<bytes, measured by the build>",
          "unpacked": "<bytes, measured by the build>",
          "entry": "program/soffice.com"
        }
      }
    }
  }
}
```

`detected_branches` lists the TDF branches a found install may be, each with its end date, written when the pin moves.

**The backend slice**, `modules/runtime_packs/`:

| File | Holds |
|---|---|
| `catalog.py` | `pack_for_this_system(pack_id) -> PackFile \| None`, from the manifest and the running platform's key |
| `download.py` | `download_pack(file, destination)`: streams to a `.part`, resumes with `Range`, never follows a redirect on its own, takes one 301/302/307 from `github.com` to `https://release-assets.githubusercontent.com/`, refuses any other before writing, stops past `size`, checks sha256 |
| `install.py` | `PackInstalls`, the packs' own single install slot with its own lock, and `install_steps(pack_id)`: download, extract, smoke, swap, record. A pack install never waits behind a model download, and each has its own progress and cancel. Once the Office pack is in place, it sets `reconcile_requested_at` on every linked root so [01](01-sources-and-folders.md)'s reconcile queues the legacy files it held back |
| `extract.py` | `extract(archive, into)`: `tarfile` with `filter="data"`, which rejects absolute paths, `..`, links leaving the tree and device files ([Python docs](https://docs.python.org/3/library/tarfile.html#extraction-filters)); it runs in `asyncio.to_thread`, and CPython's `lzma` releases the GIL while it decompresses |
| `import_file.py` | `import_pack(pack_id, path)`: the same checks on an archive the user picked, for machines that never go online |
| `office.py` | `office_runtime() -> OfficeRuntime \| OfficeUnavailable`: the pack, then a confirmed detected install, then a reason |
| `detect.py` | finds and vets an installed LibreOffice (section 7) |
| `soffice.py` | `convert(source, target_format, out_dir, *, deadline) -> Path`, raising `OfficeBusy`, `OfficeTimeout` or `OfficeFailed` |
| `render_copy.py` | `neutralize_external(copy)`: removes external targets from the copy LibreOffice opens (section 7). Imports lxml, so only workers import it |
| `profile.py` | seeds a profile's `registrymodifications.xcu` |
| `router.py`, `schemas.py` | `GET /runtime-packs`, `POST /runtime-packs/{id}/install`, `POST /runtime-packs/{id}/import`, `POST /runtime-packs/office/use-detected`, `DELETE /runtime-packs/{id}`; progress on the existing install event stream |

**On disk.** `<data>/runtime/office/<version>/` holds the tree and `installed.json` beside it names the version in use. Extraction goes to `<version>.staging-<pid>`, and the folder is renamed into place only after `soffice --version` and one conversion pass from there.

**Consent and egress.**

- `modules/egress/service.py` adds `GITHUB = "host:github.com"` and `GITHUB_ASSETS = "host:release-assets.githubusercontent.com"` to `BUILT_IN`. The plugin installer needs the same two hosts, and whichever stream lands first adds them.
- **One GitHub dialog.** The egress copy for GitHub (`frontend/src/features/egress/`) asks for both hosts at once and names every errand on them, widest first: checking for and downloading app updates (sends the app's version and platform); downloading a runtime pack the user chose (sends the file name); and, from the change that ships the plugin installer, installing plugins and refreshing their catalogue (sends the plugin's name). All send the IP address; none sends chats or documents. Allowing it turns on both rows; each later errand adds its line to the copy in the change that adds the errand.
- **One row per host.** Settings › Network's App updates row becomes the `host:github.com` row and lists its errands; `release-assets.githubusercontent.com` is its own row with the same errands. `updater.ts` reads the `host:github.com` grant through the API (with the secret from `secret.ts`) before every check, manual or scheduled, and checks nothing while it is off. `automatic` in `updates.json` stays the schedule preference. Users who allowed automatic updates before are asked once with the new dialog, as Hugging Face's old grants were ([ADR 0027](../../adr/0027-egress-consent-per-host.md), "Where the code stands").
- `POST /runtime-packs/office/install` runs `egress.require` for both hosts before any connection opens, as `start_install` does for Hugging Face. The install button reads its size from this platform's manifest entry: "Download Office support: LibreOffice 26.8.1, <size> MB."
- Nothing downloads at launch, on update, or because a feature would like a render; a feature that needs the pack shows "Needs Office support".
- The website's privacy page lists "three kinds of destination", with update checks as the only GitHub errand ([`privacy/page.tsx`](../../../surfsense_web/app/\(home\)/privacy/page.tsx), section 3.2). The M8 release that ships RT3a adds `release-assets.githubusercontent.com` and the pack download to it, with what each sends.

**Updates.** A new app release may carry a newer `packs.json` entry; Settings then offers the update, and nothing downloads until the user clicks. The old version works until the new one passes its smoke, and is deleted at the next start once nothing holds it. Settings shows the pinned branch's end date, and after it, "LibreOffice 26.8 no longer receives fixes; update SurfSense".

**Removal.** `DELETE /runtime-packs/office` renames the version folder to `.removed-<ts>` and deletes it at the next start. On Windows the rename fails while `soffice` holds a file, and the route answers `409` ("in use; try again when the current job ends"). `electron-builder.yml` sets no `deleteAppDataOnUninstall`, so uninstalling the app leaves packs in the data folder, like downloaded models.

**Settings › Downloads** is a new section in the System group of `SETTINGS_SECTIONS` ([`settings-dialog.tsx`](../../../surfsense_local/frontend/src/features/settings/settings-dialog.tsx)), where [06](06-product-shape.md) puts it. Its "Office support (LibreOffice)" entry (`frontend/src/features/runtime-packs/`) shows the state (not installed, installing, installed with version and size, update available, or using a confirmed LibreOffice at a path), what the pack enables, its licence and source link, and Install, Install from file, Update and Remove. A found install appears as "LibreOffice 26.2.6 found at …", with Use it, or with the reason it cannot be used. The Electron main process opens the file picker and hands the API a path, as it does for documents.

### 7. Running LibreOffice

`soffice.py` `convert()`:

- **Executable.** `program/soffice.com` on Windows, which waits; `soffice.exe` detaches and returns 0 (I3, lesson 9). `program/soffice` on Linux, `Contents/MacOS/soffice` on macOS.
- **Input.** A copy in a fresh folder, passed through `render_copy.neutralize_external()` first. The customer's file is never opened.
- **Arguments.** `-env:UserInstallation=<profile URL> --headless --invisible --nodefault --nolockcheck --nologo --norestore --convert-to <format[:filter]> --outdir <fresh dir> <one input>`. One input per call, because same-named outputs overwrite each other (measured).
- **Success** is an output file with a non-zero size that starts with `%PDF-` or `PK\x03\x04`; the exit code is not trusted.
- **Deadline.** The caller passes a monotonic deadline. The lock wait ends 20 s before it with `OfficeBusy`, and nothing starts. A conversion gets the smaller of 90 s and the time left, then the process tree is killed with psutil, already a direct dependency, and `OfficeTimeout` is raised. A timeout or profile error retries once with a freshly seeded profile, only if at least 30 s remain. Callers name the error in their report ("LibreOffice was busy; values not recalculated").
- **Concurrency.** One conversion app-wide, under an OS file lock on `<data>/runtime/office/run.lock`, shared by the engines, Studio and ingest workers.
- **Environment.** Built from scratch like opencode's: the OS allowlist, `HOME` set to the profile folder, proxies at `http://127.0.0.1:9`, no `LIBO_UPDATER_*`, never `SURFSENSE_LOCAL_SECRET`.

`profile.py` seeds `<data>/runtime/office/profiles/slot-0/user/registrymodifications.xcu` with:

| Key | Value | Why |
|---|---|---|
| `org.openoffice.Office.Calc/Formula/Load/OOXMLRecalcMode` and `ODFRecalcMode` | 0 (always) | the default is 1, "never" ([Calc.xcs](https://github.com/LibreOffice/core/blob/master/officecfg/registry/schema/org/openoffice/Office/Calc.xcs)); measured to turn 0 into 6 and 110 |
| `org.openoffice.Office.Update/Update/Enabled` | false | lesson 10's first rule; a found install must never update itself through SurfSense |
| `org.openoffice.Office.Jobs/Jobs/UpdateCheck/Arguments/AutoCheckEnabled` and `AutoDownloadEnabled` | false, false | lesson 10; a fresh profile has both on |
| `org.openoffice.Office.Common/Security/Scripting/MacroSecurityLevel` and `DisableMacrosExecution` | 3, true | customer documents are untrusted input |
| `org.openoffice.Office.Common/Security/Scripting/BlockUntrustedRefererLinks` and `SecureURL` | true, empty list | refuse links from documents outside trusted locations, and trust no location |
| Calc's and Writer's link update modes (`Content/Update/Link`) | never | linked images, external workbooks and DDE are not refreshed |
| `org.openoffice.Inet/Settings/ooInetProxyType` and the HTTP and HTTPS proxy name and port | 2, `127.0.0.1`, 9 | LibreOffice reads its own proxy settings, not only the environment's |

The last three rows' key paths are candidates, confirmed against `officecfg` in RT3b. The profile is a second line. The first is `neutralize_external()`, which works on the copy's XML with lxml and does not depend on LibreOffice honouring a key:

- every relationship with `TargetMode="External"` whose target is not `http:` or `https:` gets the target `about:invalid`; `http:` and `https:` targets get the same, since the render needs no network;
- `INCLUDETEXT`, `INCLUDEPICTURE`, `LINK`, `DDE` and `DDEAUTO` field codes keep their last result and lose the instruction;
- an `xl/externalLinks/` part keeps its cached values and loses its file target, so recalculation uses the values the workbook already holds;
- `oleObject` parts with a link (`w:object` with `r:id` to an external target) are treated as relationships above.

**Recalculation** is `recalc_copy(xlsx_path, *, deadline) -> dict[cell, value]`: convert a copy to xlsx under the profile above and read cached values with openpyxl's `data_only`. The rule for delivered workbooks, shared with [02](02-skills-and-engines.md):

1. The `--engine-op` child writes the edit, sets `fullCalcOnLoad="1"`, and removes the cached `<v>` of every formula whose inputs changed. 02's xlsx engine decides that set; every formula in the workbook is the conservative fallback.
2. If `office_runtime()` is available, `recalc_after()` runs `recalc_copy()` within its budget, then a second child (`xlsx.set_cached(values)`) writes LibreOffice's values into those cleared cells only, at the XML level. LibreOffice's re-written workbook is never saved. Cells where LibreOffice returns an error stay cleared.
3. The report names what happened: "Values for 14 formulas computed by LibreOffice 26.8.1; Excel recalculates on open", or "14 formula values cleared; previews show them blank until the file is opened in Excel", with the cells.
4. IronCalc, if 02 adopts it, feeds the diff and the report only ("expected 42 in B7"), never the file.

**Detecting an installed LibreOffice.** `detect.py` looks only at fixed install locations:

- Windows: `HKLM\SOFTWARE\LibreOffice\UNO\InstallPath` through `winreg`, then `%ProgramFiles%\LibreOffice\program\soffice.com`. `HKCU` is not read: any process the user runs can write it.
- macOS: `/Applications/LibreOffice.app` and `~/Applications/LibreOffice.app`.
- Linux: `/usr/lib/libreoffice/program/soffice`, `/usr/lib64/libreoffice/program/soffice` and `/opt/libreoffice*/program/soffice`. `PATH` is not searched.

Snap and Flatpak installs are skipped: their confinement hides dot-folders in the home folder (estimate), and the data folder is `~/.surfsense` ([`index.ts`](../../../surfsense_local/electron/src/main/index.ts) `DATA_DIR`). A found install is offered only when it passes every check, and each refusal shows its reason in Settings:

- its version (`program/version.ini` on Windows, `versionrc` elsewhere, confirmed in RT3b) is on a branch in `detected_branches` whose end date has not passed;
- `share/uno_packages/cache/uno_packages/` is empty and `share/extensions/` holds only the bundled extensions TDF's installer for that branch ships (an allowlist per branch, built in RT3b), because shared extensions load into every profile, SurfSense's included;
- the pack's smoke passes, cached by path, version and modification time.

It is used only after the user clicks Use it, which `POST /runtime-packs/office/use-detected` records with the path and version. A changed version re-runs the checks; a changed path asks again. Detection reads local files only.

**Resource usage.** `modules/resource_usage/engines.py` `engine_of()` attributes `soffice.bin` and `soffice` to an `office` engine, so the panel stops counting LibreOffice as the interface.

### 8. Fonts

- `scripts/fonts/pins.mjs` pins Liberation 2.1.5, Carlito and Caladea release archives from their GitHub repositories ([Liberation](https://github.com/liberationfonts/liberation-fonts), [Carlito](https://github.com/googlefonts/carlito), [Caladea](https://github.com/googlefonts/caladea)) by sha256. `scripts/fonts/stage.mjs` stages the TTFs and each OFL text into `electron/fonts/`, which ships as `resources/fonts/`. That is 24 files and 7.7 MB (E5, measured).
- `pythonEnv()` passes `SURFSENSE_LOCAL_FONTS_DIR`. reportlab-based builders register the TTFs from it by path. The frontend's DOCX viewer maps Calibri, Cambria, Arial and Times New Roman to the same families through `@font-face` with `local()` first, from WOFF2 copies in the SPA (about 1.5 MB, estimated).
- The Office pack carries its own copy of the three families in `share/fonts/truetype/`, where LibreOffice loads bundled fonts on Linux and macOS. Whether Windows LibreOffice loads them from there or needs them in the profile is open question 3.
- **CJK** is a second pack, `fonts-cjk`, on the same mechanism: Noto Sans CJK, one region subset per download, 35 to 66 MiB (E5), offered when a document's text is CJK and the export or render would otherwise show boxes. Windows and macOS have system CJK fonts that LibreOffice uses, so the pack matters most on Linux and for reportlab PDFs.

### 9. The licence gate and notices

`surfsense_local/scripts/licenses/`:

| File | Does |
|---|---|
| `policy.json` | Allowed SPDX ids per kind (below), denied ids (`GPL-*`, `LGPL-*`, `AGPL-*`, `SSPL-1.0`, `EUPL-*`, `CC-BY-NC-*`) outside the kinds that allow them, the reviewed `binaries` table, and overrides. An override records a licence a human confirmed where metadata is missing or wrong (package, version range, licence, reason, reviewer); it never widens what a kind allows |
| `check_python.py` | The runtime set from `uv export --no-dev --frozen`, read from the build environment's metadata (`License-Expression`, then classifiers, then an override). An `OR` expression passes when any branch passes. Then the native scan: every `.dll`, `.so`, `.dylib` and `.pyd` under `dist/api` and `dist/worker` is mapped to its owning distribution through the installed `RECORD` files, and must match a reviewed `binaries` entry (glob, component, licence, kind, licence file, source pointer for copyleft). An unmatched binary fails, whatever its owner's metadata says. Licence files are collected with `pip-licenses --with-license-file` (MIT) and from the `binaries` entries |
| `check_js.mjs` | `pnpm licenses list --prod --json` in `frontend/` and `electron/`. Built into pnpm, so no new dependency |
| `check_staged.mjs` | Each staged runtime (llama.cpp, sd.cpp, audio.cpp, eSpeak-ng, opencode, ripgrep, PBS, fonts) and each pack declares `licenses.json`: component, SPDX id, kind, licence file paths and, for copyleft, a source URL |
| `notices.mjs` | Writes `THIRD_PARTY_NOTICES.txt` into `resources/licenses/`, with every licence text and source pointer the checks collected. Settings › About links it, which closes [about](../../architecture/about.md)'s gap |

The kinds and what each allows:

| Kind | Means | Allows |
|---|---|---|
| `in-process` | Python or JS source in a frozen binary or bundle, or native code linked into one | ASF Category A; Category B (MPL, EPL) for unaltered files with a source pointer. Never GPL, LGPL or AGPL, and no override changes that |
| `replaceable-library` | a separate shared library file loaded at run time, which the user can replace in the installed tree | the above plus LGPL-2.1 and LGPL-3.0, with the licence text and a pointer to the exact source in the notices |
| `separate-executable` | its own process, never linked into SurfSense code | the above plus GPL, with its text and source present. eSpeak-ng's case today |
| `bootloader` | the PyInstaller bootloader inside every frozen executable | `GPL-2.0-or-later WITH Bootloader-exception` only, for the component `pyinstaller-bootloader` only |

Rules that matter:

- Kind comes from where the code sits, not from the package: FFmpeg inside opencv-python is `replaceable-library`, cv2's own `.pyd` is `in-process`.
- An unknown licence fails until it is reviewed. Today that means `huey` (MIT upstream, no metadata), `buffers@0.1.1`, and each third-party binary the first scan lists: FFmpeg in `cv2/`, PDFium and its third-party parts in `pypdfium2_raw/`, and torch's bundled libraries in `torch/lib/`. The first run reviews the worker's 323 Windows binaries by glob.
- [02](02-skills-and-engines.md)'s provenance gate, rule 4, calls `check_python.py` with this policy instead of reading licences itself, so one list exists (a change 02 must accept; see below).

The gate runs in `code-quality.yml` on pull requests that change a lockfile, a `pins.mjs`, `policy.json` or `packs.json`, and in `release-local.yml` after freezing and before `electron-builder`, since the native scan reads the frozen trees.

### 10. Signing and notarization

- **Windows, installer.** Every `.exe` is signed today, PBS's included from RT4. Adding `win.signExts: [".dll", ".pyd"]` waits on open question 4 (234 unsigned worker libraries, measured, against Smart App Control). Re-signing replaces an upstream signature, which 89 files carry, so a list would name only unsigned files.
- **Windows, Office pack.** TDF's signatures survive the trim (measured), and SurfSense signs nothing in it. A file the backend's own HTTP client writes carries no Mark of the Web, so SmartScreen does not prompt (estimate, checked in RT3b on a clean VM).
- **macOS, installer.** PBS's interpreter is signed by the `afterPack` hook with its own entitlements (section 4); its `.so` files are signed with the bundle. No notarized build has yet carried opencode or PBS. A notarized macOS build that carries opencode gates the agent's macOS release in M5: if notarization is still blocked then, the agent ships on Windows and Linux first, and the docs and the downloads page say so. A notarized build carrying PBS gates RT4 on macOS the same way.
- **macOS, Office pack.** TDF's `.app` is copied whole, so its signature and stapled ticket stay valid wherever it is extracted (verified in RT3b with `spctl`). A trimmed macOS pack needs SurfSense to re-sign and notarize it.
- **The notarization blocker.** Every macOS release waits for the Apple Developer agreement to be accepted, which needs the account holder and no code. The README names its owner and a date to chase. RT0 runs the existing `notarytool history` step on manual dry runs too, and weekly on a schedule, so an expired agreement fails before a release rather than after a full build.

## Options considered and rejected

| Option | Why not |
|---|---|
| LibreOffice in the installer | About +113 MB on Windows (measured on 25.2) and about 300 MB on macOS, downloaded again with every app update because differential updates are off, for a feature most jobs never use |
| LibreOffice downloaded from TDF's mirrors at run time | MirrorBrain redirects to hosts the user never allowed, and no SurfSense-controlled sha256 or provenance |
| A remote, refreshable pack catalogue | A second trust root and a fetch the user did not ask for. Compiled-in pins cost one app release per pack update |
| Packs on `MODSetter/SurfSense` releases | The updater takes the newest entry of that feed, so a pack release would become what installed apps try to update to |
| A dedicated `surfsense-runtime-packs` repository | A second publisher App, environment and secret pair for the same kind of upload the plugin repository will handle; one setup serves both |
| Pinning the oldest branch still receiving fixes (26.2 today) | It ends on 30 Nov 2026, likely before the pack ships, and the pin moves only with an app release |
| Using a found LibreOffice by default | It may be an ended branch or carry shared extensions, and running it is a choice about the user's own software |
| A separate `github.com` consent for packs | Two rows for one host, and a per-host grant made for packs would silently allow every later errand on GitHub |
| IronCalc values as a delivered workbook's cached values | An alpha engine's wrong value would be silent in every preview |
| Trimming and re-signing the macOS `.app` now | Breaks TDF's seal, and SurfSense cannot notarize while the agreement is expired |
| unoserver for throughput | Runs under LibreOffice's bundled Python, which the trim removes, and its README calls Windows "untested" (E5). One conversion at a time does not need it |
| ONLYOFFICE x2t, PyMuPDF, HyperFormula, pycel, `formulas` | AGPL, AGPL, GPL-3, GPL-3, and EUPL plus scipy (E5) |
| Typst for PDF output | 21.4 MiB on Windows (E5) for a path reportlab and the pack cover; revisit if PDF/A or PDF/UA becomes a job requirement |
| PBS on the agent's `PATH`, with a `site-docs/` of Office libraries | 02 §6 denies bash in job threads and on local models and refuses a standalone Python for skills; it would bring back model-written Office code, and openpyxl must never save a customer workbook. A later proposal needs 05 matrix evidence first |
| `worker --run-script` posing as `python` | A frozen stdlib subset, no `-m` or `-c`, `sys.executable` pointing at the worker, 0.8 to 1.7 s per start (measured) |
| PBS as a downloadable pack | Small enough to ship, and shipped it is signed with the app on Windows and sealed in the bundle on macOS |
| A signed general interpreter under the app's inherited entitlements | Every nested binary inherits `allow-dyld-environment-variables` and the JIT keys; a script host needs none of them. Its own entitlements file costs one hook |
| Leaving the fuses on because PBS is a script host anyway | PBS is a separate executable with its own identifier; the fuses protect the app's own executable, which carries the app's grants and runs its windows |
| Electron as Node, or a dedicated Node 24, for docx-js | Keeps the RunAsNode fuse on for every user, or adds 27 to 38 MB (E5), for one creation path Python covers |
| Driving the user's Microsoft Office over COM (Windows) or AppleScript (macOS) | Office's connected experiences, add-ins and cloud fonts can send content to Microsoft outside `egress.require()`, against [ADR 0017](../../adr/0017-egress-off-by-default.md); a third render path to test; on macOS, automation prompts and no headless mode. It needs its own proposal that answers both |
| Downloading packs from the Electron main process | Outside `egress.require()`; only the updater has that exception ([egress](../../architecture/egress.md)), and it now reads the GitHub grant |

## Phases

| # | Phase | Milestone | Scope | Depends on | Size |
|---|---|---|---|---|---|
| RT0 | Headroom and hygiene | M0 | `models` allowlist and its test; `check-installer-size.mjs` and the budget line; worker `cwd` moved to `<data>/run/<queue>` in `pythonCmd` with a `python.test.ts` case; fuses and their release check; weekly and dry-run notarization check; `packaging.md` sizes corrected | none; can start now | S: config, one script, one test each |
| RT2 | Licence gate, notices, fonts | M1 | `scripts/licenses/` with kinds and the native scan, reviews for huey, `buffers`, the bootloader rule and the first binary scan, CI wiring, `THIRD_PARTY_NOTICES.txt` in About; `scripts/fonts/`, `SURFSENSE_LOCAL_FONTS_DIR`, viewer webfonts | none: the native scan reads today's frozen trees, and RT1's additions pass through it | M: three collectors, a scan and a policy, with negative tests |
| RT1 | Engine runtime in the worker | M6, with 02 phase 1; the Anthropic SDK lands with 05 P1 in M4 | declare lxml, openpyxl, pypdfium2; add pypdf; spec entries; `worker.py` dispatch before the consumer import; `--check-engine-runtime` and its release step; `surfsense_engines` collection once 02's package exists; the FFmpeg DLL and `faker` removals if their tests pass | 02 phase 0 (M1) for the engine package; dependency changes can start now | M: spec and packaging tests that freeze real binaries |
| RT3a | Pack mechanism, consent and ADR | M8 | ADR 0041; the one-time setup of `surfsense-plugin-releases`, its publisher App and the `plugin-publishing` environment (owners in section 6), unless the plugin installer did it first; `modules/runtime_packs/` download, extract, install slot, import, remove, update; the two GitHub hosts and the one GitHub dialog; `updater.ts` reading the grant; Settings › Downloads; `runtime-` releases, never marked Latest, and an empty manifest; the privacy page's new destination | ADR accepted, which waits on TDF's answer (open question 1); RT2 for pack licence checks | M: one slice modelled on GGUF installs and the plugin installer, plus the updater change and the setup |
| RT3b | Office pack, shown as "Office support" | M8 | `build-runtime-packs.yml`, trim scripts per OS, smoke, re-measured sizes, first release of 26.8.1; `office.py`, `soffice.py`, `render_copy.py`, `profile.py`, `detect.py` with opt-in; the `office` pytest marker in `pyproject.toml`; resource-usage attribution; `recalc_copy()`, `render_thumbnails()` and `export_pdf()` entry points for 02 and 03; a how-to page in `surfsense_web/content/docs/v2/` | RT3a | L: three platform builds, a hardened runner, licence review |
| RT6 | Legacy formats at ingest | M8 | `parsing.py` converts `.doc`, `.xls`, `.ppt`, `.rtf` and `.odt` copies through the pack before Docling; 01's row text | RT3b; 01's linked folders and its agreement on the copy | S |
| RT4 | Plugin interpreter | M10 | `scripts/python/`, `plugin_python()`, `entitlements.python.plist` and the signing hook, packaged smoke | the plugin runtime stream shipping | M: one more staged runtime, signed and notarized |
| RT5 | CJK fonts pack | M10 | `fonts-cjk` on RT3a's mechanism; offer on CJK text | RT3a | S |

RT0 and RT2 are independent of every other stream. On this stream's side, turning the agent on in M5 needs only RT0's size gate, which then counts opencode and ripgrep, and the macOS notarization gate in section 10; the engine tools need RT1 in M6. 02 phase 5a's xlsx engine (M7) ships before the pack (M8): until then, and on any machine without the pack, workbooks carry cleared values the report names, and slides get no thumbnails. With 01 phases 4a and 4b (M8), this stream also takes 01's `mac.extendInfo` folder usage strings into `electron-builder.yml` and watchfiles into `api.spec` (section 2).

## Tests

Packaging tests carry the `packaging` marker and freeze real binaries, as [packaging](../../architecture/packaging.md#packaging-tests) requires:

- `tests/packaging/test_engine_runtime.py` freezes `worker.spec` into a temporary folder and runs `worker --check-engine-runtime`. It fails on a missing module or data file, including the 14 openpyxl modules missing today, a plan schema or XSD that `importlib.resources` cannot open, a pypdfium2 render that returns no page, or `worker.consumer` in `sys.modules`. It records the start time for the release log.
- `test_real_binaries.py` gains a case: the frozen worker runs `--engine-op` on a fixture DOCX with a one-operation plan. The output's sha256 is stable across two runs, and the input is unchanged.
- `test_spec_data_files.py` gains: every `collect_all` package in `worker.spec` resolves in the build environment, `surfsense_engines` contributes at least its schema files, and `api.spec` carries `packs.json`.
- `tests/packaging/test_unpacked_resources.py` reads `release/*-unpacked/resources/`. `models/` holds exactly the three packs, `fonts/` holds the pinned files and their licences, `licenses/THIRD_PARTY_NOTICES.txt` exists, and no `output.*` file sits in `resources/`.
- If the FFmpeg DLL is removed: `--check-vision-runtime` and an OCR fixture pass on a worker frozen without it.

Unit and integration tests:

- `tests/unit/runtime_packs/test_manifest.py`: every platform entry has an `https` URL starting with `https://github.com/SurfSense-Inc/surfsense-plugin-releases/releases/download/runtime-`, a 64-hex sha256, a size and an entry path; the platform keys equal `plugins/core/build-targets.json`'s, read from the repository; the pinned version's branch is in `detected_branches` and `branch_end` is its end date. No network.
- `tests/integration/runtime_packs/test_download.py`, on `httpx.MockTransport`: with either host off, `EgressDeniedError` names both before any request; a redirect to any other host, or a second redirect, is refused with nothing written; a body past `size` stops; a sha256 mismatch leaves no file; a cut download resumes with `Range` after a fresh redirect.
- `test_extract.py`: an archive with `../`, an absolute path, a link leaving the tree or a device file extracts nothing and leaves no folder.
- `test_install.py`: a failed smoke leaves the previous version in use; an update keeps the old folder until the new one passes; removal while a fake `soffice` holds a file returns `409` on Windows; Install from file refuses an archive whose sha256 is not the manifest's; a pack install requested while a model download runs starts at once in its own slot, and cancelling one leaves the other running; a finished Office pack install sets `reconcile_requested_at` on every linked root.
- `tests/unit/runtime_packs/test_soffice.py`, with a fake `soffice`: exit 0 without an output file fails; a hang past the limit leaves no process from its tree; the environment holds no `SURFSENSE_LOCAL_` or `LIBO_UPDATER_` name and its proxies point at `127.0.0.1:9`; each call gets its own output folder; two calls never overlap; a lock held past the deadline raises `OfficeBusy` with no process started; a deadline nearer than 90 s shortens the limit; no retry starts with under 30 s left.
- `test_render_copy.py`: fixtures with a `file:` image relationship, an `INCLUDETEXT` and an `INCLUDEPICTURE` field, a `DDEAUTO` field, an external workbook reference and a linked OLE object come out with no external target and the fields' last results kept; the original file's sha256 is unchanged.
- `test_profile.py`: the seeded file sets every key in section 7, including `Update/Enabled` and `AutoDownloadEnabled`.
- `test_detect.py`: fake trees and a fake `winreg` find each layout; a snap path is skipped; a `soffice` on `PATH` and an `HKCU` entry are ignored; an ended branch and a branch outside `detected_branches` are refused with the reason; an install with a package under `share/uno_packages/cache/uno_packages/` or an unlisted folder in `share/extensions/` is refused; an install that fails the smoke is not offered; a passing install is not used until `use-detected` records it; a changed path asks again.
- `tests/integration/runtime_packs/test_office_real.py`, marker `office`, run by `build-runtime-packs.yml` on each built pack: DOCX, PPTX and `.doc` convert; the fixture workbook recalculates to 6 and 110; a linked image at a local listener causes no connection; an auto-run macro does not run; each `test_render_copy.py` fixture, linking a canary file, renders and recalculates without the canary's text in the PDF's text, its image colours in the PNG, or its values in the recalculated cells. The same fixtures also run with `neutralize_external()` disabled, to record which profile keys hold on their own.
- `test_office_real.py::test_found_install_is_not_updated`, marker `office`, on the Windows runner after a normal install of TDF's MSI: a conversion through `detect.py`'s path leaves `program/version.ini`'s build id unchanged, and no `updater.exe` or `update_service.exe` process appears while it runs.
- `surfsense_local/backend/pyproject.toml` registers `office` in `markers` and changes `addopts` to `-m 'not packaging and not office'`, so unit runs never start LibreOffice.
- `scripts/licenses/` tests: GPL-only fails; `(MIT OR GPL-3.0-or-later)` and MPL-2.0 pass; a missing licence fails without a reviewed override; LGPL as Python source fails even with an override; LGPL as a `replaceable-library` passes only with its text and source pointer; a fixture wheel with Apache-2.0 metadata and a bundled DLL listed in its `RECORD` fails until a `binaries` entry reviews it; the bootloader expression passes for `pyinstaller-bootloader` and fails for any other component; a staged GPL component passes only as `separate-executable` with its text and source URL.
- Electron: `python.test.ts` (a packaged worker's `cwd` is under the data folder; `SURFSENSE_LOCAL_FONTS_DIR`, and in RT4 `SURFSENSE_LOCAL_PYTHON_DIR`, are passed); `updater.test.ts` (no check while the GitHub grant is off, even with `automatic` on); the release step fails a build whose RunAsNode fuse is on.
- RT4: a packaged smoke runs a `ctypes` callback on the staged 3.12; on macOS, `codesign -d --entitlements` on the interpreter shows `disable-library-validation` and neither `allow-dyld-environment-variables` nor `allow-jit`; a plugin with a compiled wheel loads it.

## What this changes in existing ADRs and proposals

- **New ADR 0041**, "The running app may download pinned upstream runtime binaries, unaltered except for deleted files, after per-host consent." The [README](README.md) numbers it: 0039 is 02's and 03's edits ADR. Accepting it waits on open question 1.
  - Context: ADR 0004, 0014 and 0017 call the app airgapped, and [ADR 0030](../../adr/0030-formatjs-renders-interface-text.md) forbids fetching translations at run time. Model weights are data; a pack is executable code, a new class of download after install.
  - Decision: the installer downloads nothing and every installed feature works without a pack; a pack is third-party code, built by SurfSense CI from a pinned upstream, unaltered except for deleted files, hosted on SurfSense's own releases, and pinned by URL, size and sha256 inside the app; it downloads only on a user action, after `egress.require()` for each host, with no redirect beyond the one named; an offline machine can install a pack from a file; SurfSense's own code never arrives as a pack. Plugins have their own design.
- **[02 skills and engines](02-skills-and-engines.md)**, to be agreed with 02's author: §2's licence gate, rule 4, calls `scripts/licenses/check_python.py` instead of reading `License-Expression` and classifiers itself; §3's xlsx engine follows decision 17 (clear changed formulas' cached values, write LibreOffice's values back only through `recalc_after()`, IronCalc never into the file) and owns whether IronCalc is used; §4's `engine_job` runs `recalc_after()` after the child, outside its 180 s; phase 5a no longer depends on the pack, which improves its output when present; §6's bash rule is the one this proposal cites.
- **[03 editable artifacts](03-editable-artifacts.md)**: pptx thumbnails come from `render_thumbnails(version_id)`, a Studio job after commit, not from `changes.summarize` at commit. Phase 7's PDF export is `convert()`'s fourth caller, `export_pdf(version_id, deadline)` in a Studio export job outside `transact()`. The engines worker never loads the embedding encoder, so 03's version contract has the Studio worker compute chunks and vectors for engine and agent versions (`index_version` and `version_job`), never the engines worker.
- **[01 sources and folders](01-sources-and-folders.md)**: legacy `.doc`, `.xls` and `.ppt` stay unreadable until RT6 (M8), and the root header counts them; from RT6 a legacy file shows "Needs Office support" when the pack is absent, and the pack's install sets `reconcile_requested_at` on every linked root so reconcile queues them.
- **[agent](../../architecture/agent.md)** and [`enabled.mjs`](../../../surfsense_local/electron/scripts/opencode/enabled.mjs): in M5, "the agent test" becomes 05's `agent_smoke` rows and capability rule, and `ENABLED_BY_DEFAULT` becomes `true`.
- **The website's [privacy page](../../../surfsense_web/app/\(home\)/privacy/page.tsx)**: section 3.2 gains `release-assets.githubusercontent.com` and the pack download in M8.
- **[`cuda-backend.md`](../cuda-backend.md)**: the sentence saying the airgapped rule ruled out a post-install pack is replaced by a link to ADR 0041. CUDA stays deferred, for the measured 0.66 s per turn, not for a rule.
- **[Agent README](../agent/README.md)**, Locked decisions, "Installer and network": links ADR 0041.
- **[Plugin interpreter](../plugins/bundles/python/01-interpreter.md)**: `fetch-plugin-python.mjs` and `electron/plugin-python/` become `scripts/python/stage.mjs` and `electron/python/`. `plugin_python()` reads `SURFSENSE_LOCAL_PYTHON_DIR`. The interpreter has its own macOS entitlements file.
- **[Plugin install](../plugins/bundles/install/01-install-update-uninstall.md)**: the two GitHub hosts are shared with runtime packs and app updates, and the one GitHub dialog names all three errands.
- **[Plugin publishing](../plugins/bundles/release/03-publishing.md)**: `surfsense-plugin-releases` also holds `runtime-*` releases, written by `build-runtime-packs.yml` with the same App and environment; its README says so.
- **[Plugin pull-request checks](../plugins/bundles/release/02-pull-request-checks.md)**: the licence rule moves into `scripts/licenses/policy.json`, and plugin checks call it.
- **[updates](../../architecture/updates.md)**: the updater checks only while `host:github.com` is allowed; `automatic` is the schedule.
- **[egress](../../architecture/egress.md)**: the Destinations table gains `host:github.com` and `host:release-assets.githubusercontent.com` with their errands (app updates, runtime packs, later plugins); the App updates row becomes the `github.com` row.
- **[ADR 0027](../../adr/0027-egress-consent-per-host.md)**: a Consequences note: allowing GitHub for app updates allows runtime-pack downloads and, later, plugin installs, and the reverse; the dialog names all of them, and asks for `release-assets.githubusercontent.com` with `github.com`.
- **[packaging](../../architecture/packaging.md)**: the `worker.spec` table gains openpyxl, pypdfium2, pypdf and the engines. The `models` row names its allowlist. New rows for `fonts`, `licenses` and, in RT4, `python`, with the publisher-rule note. The NSIS section quotes 2.0.3's 1.13 GB. The tests table gains the new tests.
- **[about](../../architecture/about.md)**: notices ship.
- **[ADR 0016](../../adr/0016-no-telemetry.md)** and **[ADR 0017](../../adr/0017-egress-off-by-default.md)**: unchanged. Packs follow them, and pack use is never reported.
- **[ADR 0028](../../adr/0028-model-written-code-runs-with-approval.md)**: unchanged. LibreOffice is shipped code converting documents, not model-written code.
- **[ADR 0012](../../adr/0012-vulkan-only-gpu-backend.md)**: unchanged. ADR 0041 permits a CUDA pack in principle but decides nothing about one.

## Dependencies on other streams

- **[02 skills and engines](02-skills-and-engines.md)**: the `surfsense_engines` package and its data files for the spec; the `--engine-op` child and the engines queue; `recalc_after()` in `engine_job`; the recalculated-values rule and IronCalc's place in the xlsx engine; the provenance gate calling this licence policy; the bash rule (§6); Python chart generation instead of docx-js; reports whose lines are `{code, values}`, which the pack's callers reuse.
- **[03 editable artifacts](03-editable-artifacts.md)**: the post-commit thumbnail job and where its PNGs live; the PDF export route that enqueues `export_pdf()`; chunks and vectors for engine versions computed outside the engines worker; the xlsx diff's "values not recalculated" note matching decision 17's report lines; the DOCX viewer's webfont mapping.
- **[05 model ladder and evals](05-model-ladder-and-evals.md)**: the Anthropic SDK in both binaries with P1 in M4 (about 2 MB of wheels, within budget); the `agent_smoke` and `free_agent_tasks` rows on the native Claude route that, with 03 phase 3, turn `ENABLED_BY_DEFAULT` on in M5; the llama.cpp bump (P5a) as a pin change under the size gate; the opencode pin policy (decision 20); the matrix running on the packaged worker and staged opencode.
- **[01 sources and folders](01-sources-and-folders.md)**: legacy formats in linked folders, converted at ingest from RT6, and the root header's count of unreadable legacy files until then; `@tanstack/react-virtual` (MIT) passes the gate; watchfiles in `api.spec` and the `mac.extendInfo` strings with phases 4a and 4b.
- **[README](README.md)**: the whole-stack memory budget, measured at the M5 and M6 exits, that counts the engines worker and, from M8, LibreOffice; owners and chase dates for the Apple agreement and TDF's answer.
- **[06 product shape](06-product-shape.md)**: the names "Office support" and "Needs Office support", Settings › Downloads as their place, and "pack" in the interface kept for job content.
- **Plugin streams**: the plugin runtime shipping (RT4). The plugin releases repository, its publisher App and the `plugin-publishing` environment are created by whichever of RT3a and the plugin installer starts first (section 6).

## Open questions

1. Is a LibreOffice trimmed by deletion acceptable under the MPL and TDF's trademark policy, and may the pack say "LibreOffice" in its title? Must SurfSense mirror the full corresponding source, externals included, beside each pack, or is TDF's source link enough? ADR 0041 is not accepted until this is answered, and RT3a waits on it; the README names who asks TDF and when to chase.
2. Is TDF's macOS aarch64 build notarized with a stapled ticket, so that an untouched `.app` extracted into the data folder passes `spctl`? RT3b's smoke answers it.
3. Does LibreOffice on Windows load fonts from the pack's `share/fonts/truetype/`, or must they sit in the profile or the system? This decides whether the Windows pack needs the fonts copied elsewhere.
4. Does Windows 11 Smart App Control block the installer's 234 unsigned worker libraries, or the pack's one unsigned `fbintl.dll`? Test on a SAC-enabled VM before choosing `win.signExts`.
5. Who accepts the Apple Developer agreement, and when? Nothing in this proposal ships on macOS before that, and the agent's macOS release waits on it (section 10). The README names the owner and a chase date.
6. Does the updater still install N to N+1 on all three platforms once the RunAsNode fuse is off?
7. How much of a real security questionnaire's formulas does IronCalc 0.8.3 evaluate, and how often does it disagree with LibreOffice? 02 measures it on the questionnaire fixtures before adopting it.
8. Do `ctypes` callbacks in PBS 3.12 on macOS arm64 need `allow-jit` or `allow-unsigned-executable-memory` under the hardened runtime? The RT4 smoke answers it; the entitlements file grows only if it fails.
9. Does `msiexec /a` produce the same tree as the installed copy measured here, and which system libraries does the Linux tree need on a minimal Ubuntu 22.04 and RHEL 9, given AppImage users cannot install packages?
10. Does a single `Range` resume work against `release-assets.githubusercontent.com` after its signed URL expires, re-resolving the redirect from `github.com`?
11. Can `faker`, `polyfactory` and opencv-python's FFmpeg DLL be excluded without breaking a Docling or RapidOCR path?
12. Which `share/extensions/` folders does each supported TDF branch install by default on each platform? RT3b builds the allowlist from TDF's installers; a found install that differs is refused until the list covers it.
