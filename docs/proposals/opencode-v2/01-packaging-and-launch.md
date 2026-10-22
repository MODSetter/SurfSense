# Packaging and launch

## Packaging

opencode 2.x is published on npm only, one package per platform holding `package/bin/opencode[.exe]` and nothing else. [`pins.mjs`](../../../surfsense_local/electron/scripts/opencode/pins.mjs) pins these tarballs by version and SHA-256, and [`stage.mjs`](../../../surfsense_local/electron/scripts/opencode/stage.mjs) unpacks them with the same `tar -xf` it uses today:

| Host | Tarball | SHA-256 |
|---|---|---|
| darwin-arm64 | `https://registry.npmjs.org/@opencode/cli-darwin-arm64/-/cli-darwin-arm64-2.1.2.tgz` | `88e5fa8d8e29354308350c5ed7842e23f63c0b4e4594cd8f91b0ca006b7da224` |
| linux-x64 | `https://registry.npmjs.org/@opencode/cli-linux-x64-baseline/-/cli-linux-x64-baseline-2.1.2.tgz` | `e8a87dc3dba4acbd931b575db4d62722b66e13df5b208f73a8a9da69fdcacdc6` |
| win32-x64 | `https://registry.npmjs.org/@opencode/cli-windows-x64-baseline/-/cli-windows-x64-baseline-2.1.2.tgz` | `a3f55a44492671cad2f464d901f4a264de0f13bdae68e55b2a3ac09424268494` |

- Each matches npm's published `sha512` integrity. Linux's `-baseline` build needs glibc 2.30 or later.
- The archives are 86 to 102 MB, about 40 MB more than 1.18.34's, and the executables 189 to 219 MB.
- The licence still comes from the tag, `https://raw.githubusercontent.com/anomalyco/opencode/v2.1.2/LICENSE`, unchanged at `625f0f61…cb6b`.
- ripgrep stays shipped: 2.x still looks for `rg` on `PATH`, then downloads 15.1.0 from GitHub.
- The macOS executable is signed by Anomaly Innovations (5NZ4Q7NXJ4) with the same five entitlements as 1.x, so `mac.signIgnore` in [`electron-builder.yml`](../../../surfsense_local/electron/electron-builder.yml) stays. The Windows executable is Authenticode-signed for "Anomaly Innovations, Inc"; on Windows 11 with Defender on it ran with no detection, 173 ms cold and 68 ms warm.
- `--version` prints `opencode v2.1.2`, so [`check-stage.mjs`](../../../surfsense_local/electron/scripts/opencode/check-stage.mjs) reads the release after ` v` instead of comparing the whole line. 2.x writes a log even for `--version`, so the check runs it in a throwaway home.
- The `@opencode-ai/plugin` lockfile stub and `npm_config_*` go: 2.x installs nothing at startup.

## Launch

`serve --hostname 127.0.0.1 --port <port>` stays, and prints `server listening on http://…` without 1.x's `opencode ` prefix. Readiness is `GET /api/info` answering `version: "2.1.2"`. It needs the password even while booting, so it is also how [`opencode-leftovers.ts`](../../../surfsense_local/electron/src/main/sidecars/opencode-leftovers.ts) proves a recorded process is ours, by the `pid` it returns; a 1.x leftover from the release before still answers `/global/health`.

`serve --service` is not used. Only in that mode does 2.x resume a turn a quit or crash cut off ([`core/src/session/execution/restart.ts`](https://github.com/anomalyco/opencode/blob/v2.1.2/packages/core/src/session/execution/restart.ts), wired only for mode `service` in [`cli/src/server-process.ts`](https://github.com/anomalyco/opencode/blob/v2.1.2/packages/cli/src/server-process.ts)), and it resumes a turn the user declined too, because a decline is recorded with the default reason `shutdown`. It also ignores `OPENCODE_PASSWORD` for a password file of its own.

## Environment

[`opencode.ts`](../../../surfsense_local/electron/src/main/sidecars/opencode.ts) still builds the environment from nothing. What 2.x reads, from [`cli/src/server-process.ts`](https://github.com/anomalyco/opencode/blob/v2.1.2/packages/cli/src/server-process.ts) and [`cli/src/env.ts`](https://github.com/anomalyco/opencode/blob/v2.1.2/packages/cli/src/env.ts):

| Variable | 2.x |
|---|---|
| `OPENCODE_PASSWORD` | the server password; `OPENCODE_SERVER_PASSWORD` is still read as its old name. Removed from the environment of what opencode runs |
| `OPENCODE_CONFIG`, `OPENCODE_TEST_HOME`, `XDG_*` | read as in 1.x |
| `OPENCODE_DISABLE_MODELS_FETCH`, `OPENCODE_DISABLE_CLAUDE_CODE` | read |
| `OPENCODE_CONFIG_PROJECT_DISABLE` | read; `OPENCODE_DISABLE_PROJECT_CONFIG` is its old name |
| `OPENCODE_DISABLE_SHARE`, `_LSP_DOWNLOAD`, `_DEFAULT_PLUGINS`, `_EXTERNAL_SKILLS`, `_AUTOUPDATE`, `OPENCODE_PURE`, `OPENCODE_PERMISSION`, `OPENCODE_EXPERIMENTAL*` | not read; what they switched off is switched off in the configuration ([config](03-config-and-permissions.md)) |
| `TMPDIR`, `TEMP`, `TMP` | opencode's scratch folder is `$TMPDIR/opencode`, shared with the user's own opencode, so these point inside SurfSense's agent folder |

`OPENCODE_CONFIG_CONTENT`, `OPENCODE_CONFIG_DIR`, `OPENCODE_DB`, `OPENCODE_MODELS_URL` and `OPENCODE_MODELS_PATH` are read and stay out, as the allowlist already keeps them.

## Windows

- A folder spelled two ways is two places to 2.x: `C:\` and `c:\`, or a different letter case, give a separate location, project and session list, and a trailing `\` is stored on the session and missed when listing by the plain spelling. Every folder SurfSense passes is resolved, without a trailing separator, in one case.
- Paths come back with forward slashes. `\\?\` paths are treated as outside the working folder and refused, even when they point into it.
- Bun extracts a 5.1 MB `.bun-*.dll` and a 0.5 MB `.bun-*.node` into the temp folder at every start and never removes them; the temp folder is swept at launch.
- `taskkill /pid /t /f` stops the server and its children and frees the port within 1.5 s. Started as [`supervisor.ts`](../../../surfsense_local/electron/src/main/sidecars/supervisor.ts) starts it, opencode exits with Electron; started by anything else it outlives its parent, so the leftover record stays.
- Paths of 267 to 342 characters with non-ASCII names worked with `LongPathsEnabled=1`; the executables declare `longPathAware`. Windows defaults to 0, so the 259-character budget stays.
