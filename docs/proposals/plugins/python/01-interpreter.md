# Python — the interpreter a plugin runs on

> Owns: `surfsense_local/electron/scripts/fetch-plugin-python.mjs`, the `extraResources` entry, `plugin_python()`, `system_key()` and `sdk_version()` in `modules/plugins/python.py`.

## Goal

The packaged app can spawn `python -m surfsense_plugin`. The PyInstaller binaries that are the API and the worker cannot do this: they are not a general interpreter, and a plugin is source.

## Work

- Pin CPython at the version in `plugins/targets.json`, 3.12, the same minor the backend uses, from the python-build-standalone release. One asset per platform in that file: `windows-x64`, `macos-arm64`, `linux-x64`. There is no Intel Mac build ([ADR 0021](../../../adr/0021-no-intel-mac-build.md)). Record each URL and sha256 in the fetch script, the way `fetch-llamacpp.mjs` records llama-server.
- The script verifies the sha256, extracts, and stages atomically under `surfsense_local/electron/plugin-python/`. `electron-builder.yml` `extraResources` copies that directory to `plugin-python/`.
- `plugin_python() -> Path` returns the staged interpreter in the packaged app (`python` or `python.exe` on the staged path) and, when that path is absent, the interpreter running the API. Tests and `pnpm dev` hit the second branch and do not download anything.
- `system_key() -> str` returns this app's download key, such as `cp312-linux-x64`: the Python version of the interpreter `plugin_python()` returns, and this system's platform in the names `plugins/targets.json` uses. Installing picks a plugin's download with it.
- The same resources directory ships `plugins/sdk/` beside the interpreter. That is how `python -m surfsense_plugin` resolves. Do not publish the SDK to PyPI.
- `sdk_version() -> str` reads `VERSION` from that shipped SDK folder, or from `plugins/sdk/` in development. Listing and installing test each plugin's `sdk` range against it, so the app never states a version its SDK does not have.
- The desktop build's `dist` script runs the fetch the same way it runs `fetch-llamacpp.mjs`, and `.github/workflows/release-local.yml` gets its own step for it, because the release build does not run `dist`. A mismatch fails the build.
- Upgrading the plugin interpreter means changing `python` in `plugins/targets.json` and the three assets together. Publishing then rebuilds every plugin with compiled downloads for the new key ([`../catalog/02-publish.md`](../catalog/02-publish.md)).

## Acceptance

- `checkConfiguration()` fails when a platform in `plugins/targets.json` has no asset, or an asset lacks a 64-hex sha256. That test runs with no network.
- On a developer machine, `plugin_python()` returns a path that runs `import sys; print(sys.version)` and reports 3.12 when the staged directory is present, and returns the current interpreter when it is absent.
- `system_key()` returns a key made of the Python version of the interpreter `plugin_python()` returns and one of the platforms in `plugins/targets.json`. In the packaged app, that version is the one `plugins/targets.json` names.
- `sdk_version()` equals the contents of `plugins/sdk/VERSION`, in development and in the packaged app.
- A packaged smoke, like the Linux llama-server smoke in `release-local.yml`, runs the staged interpreter with `-c "import sys; assert sys.version_info[:2]==(3,12)"`.

## Needs from

`plugins/targets.json` from the catalog stream. The runtime stream calls `plugin_python()` and works before this is packaged.
