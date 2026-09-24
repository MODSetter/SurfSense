# Running opencode

> opencode `v1.18.32` ships inside the installer. SurfSense launches it with its own fetches switched off, sends the HTTP it does make through an egress proxy, answers its permission requests, and points it at a folder of Docling text instead of the user's files.

Source links below are to opencode at tag [`v1.18.32`](https://github.com/anomalyco/opencode/tree/v1.18.32) (commit `545f51d`). Paths are under `packages/`.

## What is being bundled

- [anomalyco/opencode](https://github.com/anomalyco/opencode), MIT licence, published 21 Sep 2026. It is built with Bun 1.3.14 into one executable per platform.
- Release archives: `opencode-windows-x64.zip` 59.2 MB, `opencode-darwin-arm64.zip` 44.2 MB, `opencode-linux-x64.tar.gz` 57.8 MB.
- opencode published 45 releases between 1 Jul and 21 Sep 2026, so the version is pinned and moved on purpose.
- It sends its tool list on every model request and has no mode for models without native tool calling. The request for one was closed as not planned ([#19966](https://github.com/anomalyco/opencode/issues/19966)).
- Its `read` tool treats `.docx` as binary and passes PDFs and images to the model as attachments ([`opencode/src/tool/read.ts`](https://github.com/anomalyco/opencode/blob/v1.18.32/packages/opencode/src/tool/read.ts)). The agent reads Docling text instead (Working folders, below).

## Packaging

- Stage the pinned archive and check its SHA-256 at build time, as [`fetch-llamacpp.mjs`](../../../surfsense_local/electron/scripts/fetch-llamacpp.mjs) does for llama.cpp.
- Ship ripgrep beside it. On its first grep, opencode looks for `rg` on `PATH`, then in its own `bin` folder under its cache directory, and otherwise downloads it from GitHub ([`core/src/ripgrep/binary.ts`](https://github.com/anomalyco/opencode/blob/v1.18.32/packages/core/src/ripgrep/binary.ts), [`core/src/global.ts`](https://github.com/anomalyco/opencode/blob/v1.18.32/packages/core/src/global.ts)).
- The installer downloads nothing. Today's targets are already offline builds: NSIS on Windows, dmg and zip on macOS, AppImage and deb on Linux ([`electron-builder.yml`](../../../surfsense_local/electron/electron-builder.yml)).
- The Windows installer was 1.3 GB at 2.0.2, against a 2 GB `makensis` ceiling ([packaging](../../architecture/packaging.md)). Measure it again after adding opencode and ripgrep.

## Launch

- `opencode serve` binds `127.0.0.1` by default ([`opencode/src/cli/network.ts`](https://github.com/anomalyco/opencode/blob/v1.18.32/packages/opencode/src/cli/network.ts)). Set `OPENCODE_SERVER_PASSWORD` to a secret made at each launch; with it set, the server requires basic auth ([`opencode/src/server/auth.ts`](https://github.com/anomalyco/opencode/blob/v1.18.32/packages/opencode/src/server/auth.ts)).
- The routes SurfSense needs, all in [`opencode/src/server/routes/instance/httpapi/groups/`](https://github.com/anomalyco/opencode/tree/v1.18.32/packages/opencode/src/server/routes/instance/httpapi/groups):
  - `POST /session` opens a session.
  - `POST /session/:sessionID/message` and `POST /session/:sessionID/prompt_async` send a prompt.
  - `GET /event` streams events as `text/event-stream`.
  - `POST /permission/:requestID/reply` answers a permission request with `once`, `always` or `reject`.
- Electron's supervisor spawns today's sidecars ([`sidecars/supervisor.ts`](../../../surfsense_local/electron/src/main/sidecars/supervisor.ts)). Which process spawns opencode is open.

## No network without consent

| What opencode would fetch | Defined in | How SurfSense prevents it |
|---|---|---|
| Its model catalog, when `serve` starts and every hour | [`core/src/models-dev.ts`](https://github.com/anomalyco/opencode/blob/v1.18.32/packages/core/src/models-dev.ts) | `OPENCODE_DISABLE_MODELS_FETCH=1` |
| `@opencode-ai/plugin` from npm, into each config folder, on the first session | [`opencode/src/config/config.ts`](https://github.com/anomalyco/opencode/blob/v1.18.32/packages/opencode/src/config/config.ts), [`core/src/npm.ts`](https://github.com/anomalyco/opencode/blob/v1.18.32/packages/core/src/npm.ts) | Ship each config folder with `node_modules` and a `package-lock.json` that lists the package, which is what `npm.ts` checks before installing |
| ripgrep from GitHub | [`core/src/ripgrep/binary.ts`](https://github.com/anomalyco/opencode/blob/v1.18.32/packages/core/src/ripgrep/binary.ts) | Ship `rg` (Packaging, above) |
| Shared sessions on opencode's servers | [`opencode/src/share/share-next.ts`](https://github.com/anomalyco/opencode/blob/v1.18.32/packages/opencode/src/share/share-next.ts) | `OPENCODE_DISABLE_SHARE=1` and `"share": "disabled"` |
| LSP server downloads | [`opencode/src/effect/runtime-flags.ts`](https://github.com/anomalyco/opencode/blob/v1.18.32/packages/opencode/src/effect/runtime-flags.ts) | `OPENCODE_DISABLE_LSP_DOWNLOAD=1` |
| Web pages and web search | the `webfetch` and `websearch` tools | `deny` both |
| opencode's own hosted provider | `enabled_providers` in [`core/src/v1/config/config.ts`](https://github.com/anomalyco/opencode/blob/v1.18.32/packages/core/src/v1/config/config.ts) | List only SurfSense's provider |
| npm plugins | [`core/src/flag/flag.ts`](https://github.com/anomalyco/opencode/blob/v1.18.32/packages/core/src/flag/flag.ts) | `OPENCODE_PURE=1` |
| Config, plugins and MCP servers from a `.opencode` folder or `opencode.json` in the working folder | [`opencode/src/config/paths.ts`](https://github.com/anomalyco/opencode/blob/v1.18.32/packages/opencode/src/config/paths.ts) | `OPENCODE_DISABLE_PROJECT_CONFIG=1` |
| Skills and instructions from other tools' folders | [`opencode/src/effect/runtime-flags.ts`](https://github.com/anomalyco/opencode/blob/v1.18.32/packages/opencode/src/effect/runtime-flags.ts) | `OPENCODE_DISABLE_EXTERNAL_SKILLS=1` and `OPENCODE_DISABLE_CLAUDE_CODE=1`; confirm what each one skips |
| OpenTelemetry export | [`core/src/observability/otlp.ts`](https://github.com/anomalyco/opencode/blob/v1.18.32/packages/core/src/observability/otlp.ts) | Leave `OTEL_EXPORTER_OTLP_ENDPOINT` unset |
| Its web UI from `https://app.opencode.ai` | [`opencode/src/server/shared/ui.ts`](https://github.com/anomalyco/opencode/blob/v1.18.32/packages/opencode/src/server/shared/ui.ts) | Never set `OPENCODE_DISABLE_EMBEDDED_WEB_UI`, which forces that fallback; confirm the staged binary embeds the UI |

Keep opencode's own configuration and state out of the user's: run it with `XDG_CONFIG_HOME`, `XDG_DATA_HOME`, `XDG_CACHE_HOME`, `XDG_STATE_HOME` and a home directory inside SurfSense's data folder. It finds its folders through `xdg-basedir` and `os.homedir()` ([`core/src/global.ts`](https://github.com/anomalyco/opencode/blob/v1.18.32/packages/core/src/global.ts)). Confirm on each OS that Bun's `os.homedir()` follows `HOME` or `USERPROFILE`.

**Enforcing it.** Bun's `fetch` reads `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY` and `NO_PROXY` on each request ([Bun docs](https://bun.com/docs/runtime/networking/fetch)). opencode's HTTP client is Effect's `FetchHttpClient` over the global `fetch` ([`core/src/effect/app-node-platform.ts`](https://github.com/anomalyco/opencode/blob/v1.18.32/packages/core/src/effect/app-node-platform.ts)). So SurfSense launches opencode with those variables pointing at a forward proxy in the backend. The proxy calls `egress.require()` for each host it is asked to reach ([`modules/egress/service.py`](../../../surfsense_local/backend/modules/egress/service.py)) and refuses the rest, and `NO_PROXY` covers loopback. What it does not cover:

- WebSockets: Bun does not apply these variables to them, and opencode passes a proxy by hand only on its OpenAI Responses WebSocket path ([`opencode/src/plugin/openai/ws.ts`](https://github.com/anomalyco/opencode/blob/v1.18.32/packages/opencode/src/plugin/openai/ws.ts)).
- Programs a shell command starts, which can ignore the variables ([ADR 0028](../../adr/0028-model-written-code-runs-with-approval.md)).

## Models and context

- opencode reaches models through a custom provider on `@ai-sdk/openai-compatible`, which is built into the binary ([`opencode/src/provider/provider.ts`](https://github.com/anomalyco/opencode/blob/v1.18.32/packages/opencode/src/provider/provider.ts)). Remote models go through SurfSense, so their keys stay there.
- Set `limit.context` and `limit.output` for every model. Without `limit.input`, opencode's usable input is `context − min(limit.output, 32000)`, and an unset output limit counts as 32,000 ([`opencode/src/session/overflow.ts`](https://github.com/anomalyco/opencode/blob/v1.18.32/packages/opencode/src/session/overflow.ts), [`opencode/src/provider/transform.ts`](https://github.com/anomalyco/opencode/blob/v1.18.32/packages/opencode/src/provider/transform.ts)). With an 8,192-token context and no output limit, usable input is 0, so every turn overflows and triggers compaction.
- The context value is the window llama-server loaded for that model on this machine. The app reads it from `/props` ([runtime](../../architecture/local-models/runtime.md)), and the load plan chooses it from 8,192, 16,384, 32,768 or the model's trained length ([fit](../../architecture/local-models/fit.md)).
- **Fixed prompt size.** The default system prompt is 8,528 characters ([`opencode/src/session/prompt/default.txt`](https://github.com/anomalyco/opencode/blob/v1.18.32/packages/opencode/src/session/prompt/default.txt)). A custom agent's `prompt` replaces it, and opencode still appends more system text after it ([`opencode/src/session/llm/request.ts`](https://github.com/anomalyco/opencode/blob/v1.18.32/packages/opencode/src/session/llm/request.ts)). Each tool sent adds its description ([`opencode/src/tool/`](https://github.com/anomalyco/opencode/tree/v1.18.32/packages/opencode/src/tool)):

| Tool | Description, characters |
|---|---|
| `bash` | 1,269 |
| `read` | 1,158 |
| `edit` | 1,369 |
| `write` | 623 |
| `glob` | 517 |
| `grep` | 657 |
| `task` | 2,305 |
| `todowrite` | 2,012 |
| `webfetch` | 750 |
| `skill` | 399 |
| `question` | 657 |

Those eleven add up to 11,716 characters. A tool denied with the pattern `*` is left out of the list sent to the model ([`opencode/src/permission/index.ts`](https://github.com/anomalyco/opencode/blob/v1.18.32/packages/opencode/src/permission/index.ts)). Measure the real token cost with llama-server's `/tokenize`, which the app already calls, before choosing the output limit.

## Permissions

- opencode's default for every tool is `allow` ([`opencode/src/agent/agent.ts`](https://github.com/anomalyco/opencode/blob/v1.18.32/packages/opencode/src/agent/agent.ts)).
- `bash` is `ask`. opencode publishes each request as a permission `Asked` event ([`opencode/src/permission/index.ts`](https://github.com/anomalyco/opencode/blob/v1.18.32/packages/opencode/src/permission/index.ts)). SurfSense reads it from `/event`, shows the full command, and answers through `POST /permission/:requestID/reply` ([ADR 0028](../../adr/0028-model-written-code-runs-with-approval.md)). Confirm the event's name as it appears on the stream.
- `webfetch` and `websearch` are `deny`.
- File edits and writes are allowed only inside the output folder, and `external_directory` is `deny`. The shell tool also checks `external_directory` for paths outside the working folder ([`opencode/src/tool/shell.ts`](https://github.com/anomalyco/opencode/blob/v1.18.32/packages/opencode/src/tool/shell.ts)). Write this rule set and test it before shipping.
- Snapshots are off with `"snapshot": false`. They are also off in any folder that is not a git repository ([`opencode/src/snapshot/index.ts`](https://github.com/anomalyco/opencode/blob/v1.18.32/packages/opencode/src/snapshot/index.ts)).
- `OPENCODE_EXPERIMENTAL` and `OPENCODE_EXPERIMENTAL_CODE_MODE` stay unset; the first turns on the second ([`opencode/src/effect/runtime-flags.ts`](https://github.com/anomalyco/opencode/blob/v1.18.32/packages/opencode/src/effect/runtime-flags.ts)).

## Working folders

opencode's working folder belongs to SurfSense, not the user:

- **A text view:** each ready source's extracted markdown as a `.md` file. opencode's own `read`, `grep` and `glob` then work on Docling text. The agent can only read it.
- **An output folder** the agent can write to.

Uploads exist on disk only as `original.<ext>` in folders named by row ids ([documents](../../architecture/documents.md)), so the text view has to name them. Sources from a linked folder keep their relative paths ([`05-sources-folder.md`](05-sources-folder.md)).

A custom tool named `read` replaces the built-in one. Custom tools load from a `tool/` or `tools/` folder in a config folder and are keyed by id, with custom tools added after built-ins ([`opencode/src/tool/registry.ts`](https://github.com/anomalyco/opencode/blob/v1.18.32/packages/opencode/src/tool/registry.ts), [`opencode/src/session/tools.ts`](https://github.com/anomalyco/opencode/blob/v1.18.32/packages/opencode/src/session/tools.ts)). That is the fallback if the text view is not enough.

## Open questions

- Which process spawns and stops opencode: Electron's supervisor or the backend.
- Which opencode tools are sent. Each costs context (table above).
- The output limit for agent turns.
- How files the agent writes become artifacts: the agent calls `create_artifact` ([`02-tools.md`](02-tools.md)), or SurfSense imports the output folder.
- How uploads are named in the text view, and when the view is rebuilt.
- Whether SurfSense offers opencode's `always` reply.
- How a host the proxy refuses reaches the egress consent prompt.
- Whether local models are reached directly on llama-server or also through SurfSense.
- A test that runs opencode with the network blocked and checks that it opens no connection beyond loopback.
