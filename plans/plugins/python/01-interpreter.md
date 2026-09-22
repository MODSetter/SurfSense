# Python — the interpreter a plugin runs on

> Owns: `surfsense_local/electron/scripts/fetch-plugin-python.mjs`, the `extraResources` entry, `plugin_python()` in `modules/plugins/python.py`.

## Goal

The packaged app can spawn `python -m surfsense_plugin`. The PyInstaller binaries that are the API and the worker cannot do this: they are not a general interpreter, and a plugin is source.

## Work

- Pin CPython 3.12, the same minor the backend uses, from the python-build-standalone release. One asset per `linux-x64`, `darwin-arm64`, `darwin-x64`, `win32-x64`. Record the URL and sha256 in the fetch script, the way `fetch-llmfit.mjs` records llmfit.
- The script verifies the sha256, extracts, and stages atomically under `surfsense_local/electron/plugin-python/`. `electron-builder.yml` `extraResources` copies that directory to `plugin-python/`.
- `plugin_python() -> Path` returns the staged interpreter in the packaged app (`python` or `python.exe` on the staged path) and, when that path is absent, the interpreter running the API. Tests and `pnpm dev` hit the second branch and do not download anything.
- The same resources directory ships `plugins/sdk/` beside the interpreter. That is how `python -m surfsense_plugin` resolves. Do not publish the SDK to PyPI.
- The desktop build's `dist` script runs the fetch the same way it runs `fetch-llmfit.mjs`. A mismatch fails the build.
- Publish workflow in the catalog stream installs dependencies with this minor version. It does not need this script. It needs the version number, which lives in this file as `PYTHON_VERSION`.

## Acceptance

- `checkConfiguration()` fails when any of the four targets lacks a 64-hex sha256. That test runs with no network.
- On a developer machine, `plugin_python()` returns a path that runs `import sys; print(sys.version)` and reports 3.12 when the staged directory is present, and returns the current interpreter when it is absent.
- A packaged smoke, the kind `check-llmfit.mjs` already does for llmfit, runs the staged interpreter with `-c "import sys; assert sys.version_info[:2]==(3,12)"`.

## Needs from

Nothing. The runtime stream calls `plugin_python()` and works before this is packaged.
