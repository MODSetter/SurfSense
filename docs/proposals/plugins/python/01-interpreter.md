# Python — the interpreter a plugin runs on

> Owns: `surfsense_local/electron/scripts/fetch-plugin-python.mjs`, the `extraResources` entry, `plugin_python()` and `system_key()` in `modules/plugins/python.py`.

## Goal

The packaged app can spawn `python -m surfsense_plugin_sdk.run`. The PyInstaller binaries that are the API and the worker cannot do this: they are not a general interpreter, and a plugin is source.

## Work

- Pin CPython at the version in `plugins/core/build-targets.json`, 3.12, the same minor the backend uses, from the python-build-standalone release. One asset per platform in that file: `windows-x64`, `macos-arm64`, `linux-x64`. There is no Intel Mac build ([ADR 0021](../../../adr/0021-no-intel-mac-build.md)). Record each URL and sha256 in the fetch script, the way `fetch-llamacpp.mjs` records llama-server.
- The script verifies the sha256, extracts, and stages atomically under `surfsense_local/electron/plugin-python/`. `electron-builder.yml` `extraResources` copies that directory to `plugin-python/`.
- `plugin_python() -> Path` returns the staged interpreter in the packaged app (`python` or `python.exe` on the staged path) and, when that path is absent, the interpreter running the API. Tests and `pnpm dev` hit the second branch and do not download anything.
- `system_key() -> str` returns this app's download key, such as `cp312-linux-x64`: the Python version of the interpreter `plugin_python()` returns, and this system's platform in the names `plugins/core/build-targets.json` uses. `choose_version.py` picks a plugin's file with it.
- The same resources directory ships `plugins/core/sdk/` beside the interpreter. That is how `python -m surfsense_plugin_sdk.run` resolves. Do not publish the SDK to PyPI. The SDK has no version of its own: it is the app's ([`../04-versioning.md`](../04-versioning.md)).
- The desktop build's `dist` script runs the fetch the same way it runs `fetch-llamacpp.mjs`, and `.github/workflows/release-local.yml` gets its own step for it, because the release build does not run `dist`. A mismatch fails the build.
- Upgrading the plugin interpreter means changing `python` in `plugins/core/build-targets.json` and the three assets together. The release that carries it republishes every plugin with no `any` file for the new key ([`../release/03-publishing.md`](../release/03-publishing.md)); their versions for the old key stay for older apps.

## Acceptance

- `checkConfiguration()` fails when a platform in `plugins/core/build-targets.json` has no asset, or an asset lacks a 64-hex sha256. That test runs with no network.
- On a developer machine, `plugin_python()` returns a path that runs `import sys; print(sys.version)` and reports 3.12 when the staged directory is present, and returns the current interpreter when it is absent.
- `system_key()` returns a key made of the Python version of the interpreter `plugin_python()` returns and one of the platforms in `plugins/core/build-targets.json`. In the packaged app, that version is the one `build-targets.json` names.
- A packaged smoke, like the Linux llama-server smoke in `release-local.yml`, runs the staged interpreter with `-c "import sys; assert sys.version_info[:2]==(3,12)"`.

## Needs from

`plugins/core/build-targets.json` from the release stream. The runtime stream calls `plugin_python()` and works before this is packaged.
