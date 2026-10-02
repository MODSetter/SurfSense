# Release — packaging

> Owns: `plugins/core/cli/surfsense_plugin_cli/packaging/`, `plugins/core/build-targets.json`, `plugins/core/policy/size-limit-exceptions.txt`.
> Contract: [`../01-protocol.md`](../01-protocol.md). Used by: [`02-pull-request-checks.md`](02-pull-request-checks.md), [`03-publishing.md`](03-publishing.md).

## Goal

One function turns a plugin folder into its downloadable files, the same way for an author's `check`, a pull request's checks and a release. Nothing is ever compiled, and the user's machine never installs a dependency.

## Work

- Packaging is the `packaging/` job of the `surfsense-plugins` command in `plugins/core/cli/` ([`../cli/01-author-commands.md`](../cli/01-author-commands.md)). Workflows call the command and hold no logic of their own. Its install step, `install_requirements(plugin, platform, into)`, is the one `surfsense-plugins invoke` runs for the author's own platform, so an author's machine installs what a release installs.
- `plugins/core/build-targets.json` as the protocol describes it: the CPython version and each platform's `uv` target. It is read by packaging, the checks and the interpreter fetch script ([`../python/01-interpreter.md`](../python/01-interpreter.md)), so they cannot disagree.
- For each platform in the plugin's `platforms`, all of `build-targets.json` when absent: `uv pip install --python-version <python> --python-platform <target> --only-binary :all: --require-hashes -r requirements.txt --target <dir>`. A failure names the package and the platform: that version publishes no prebuilt wheel there, so pick another version or package. `uv` fetches the other platforms' wheels from one Linux machine; no platform needs its own runner.
- Compare the installed files across platforms. The same files make one `any` file; different files make one file per platform. Compare files, not packages: `tqdm` pulls in `colorama` only on Windows, so a pure-Python plugin can still need one file per platform.
- Write each file as the protocol's "Downloadable files" section describes, with the stamped `version` added to the packaged `manifest.json` when a release asks for one. Write the archive the same way every time: members sorted, times and owners fixed, gzip without a timestamp. The same inputs then give the same sha256, which makes a rerun of a release recognise what it already uploaded.
- Enforce the size limit: 100 MB per file, or the size on the plugin's line in `plugins/core/policy/size-limit-exceptions.txt`, which is `<id> <megabytes> <reason>` and added by a maintainer.

## Acceptance

- A plugin that needs only `requests` packages into one `any` file. One that needs `lxml` packages into three, and the Windows one contains a `.pyd`.
- A dependency published only as a source distribution fails, naming the package and the platform.
- Packaging the same plugin twice gives files with the same sha256.
- A file over 100 MB fails, and passes once `size-limit-exceptions.txt` names the plugin with a larger size.
- A packaged `manifest.json` carries the stamped `version` when one is given, and none otherwise.

## Needs from

`plugins/core/build-targets.json`, which whichever stream lands first adds. Nothing from the app.
