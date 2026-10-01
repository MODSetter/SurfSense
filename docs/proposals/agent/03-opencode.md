# Running opencode

> opencode `v1.18.34` ships inside the installer. Electron starts it on first use with its network cut off and a configuration SurfSense writes. It reaches every model through one SurfSense endpoint, the backend is its only client and answers its permission requests, and it works in a folder of Docling text instead of the user's files.

Source links below are to opencode at tag [`v1.18.34`](https://github.com/anomalyco/opencode/tree/v1.18.34) (commit `aec0b9a`), checked on 1 Oct 2026. Paths are under `packages/`.

## What is being bundled

- [anomalyco/opencode](https://github.com/anomalyco/opencode), MIT licence. `v1.18.34` was published on 30 Sep 2026. It is built with Bun into one executable per platform.
- The archives staged, with the SHA-256 GitHub publishes for each: `opencode-windows-x64-baseline.zip` (62.2 MB), `opencode-linux-x64-baseline.tar.gz` (60.7 MB) and `opencode-darwin-arm64.zip` (45.5 MB). Unpacked, the standard builds are 181 MB on Windows, 186 MB on Linux and 144 MB on macOS.
- opencode published 45 releases between 1 Jul and 21 Sep 2026, so the version is pinned and moved on purpose.
- A second line, 2.x, has been tagged since 11 Sep 2026, from `v2.0.0` to `v2.0.21` on 30 Sep. It is published only on npm, as [`@opencode/cli`](https://www.npmjs.com/package/@opencode/cli), not as release archives. Its server moves the routes under `/api` ([`protocol/src/groups/session.ts` at `v2.0.21`](https://github.com/anomalyco/opencode/blob/v2.0.21/packages/protocol/src/groups/session.ts)) and changes event names and payloads ([`app/src/utils/server-compat.ts`](https://github.com/anomalyco/opencode/blob/v1.18.34/packages/app/src/utils/server-compat.ts)). SurfSense pins 1.x, and what differs sits in one backend module (The backend's client, below).
- It sends its tool list on every model request and has no mode for models without native tool calling. The request for one was closed as not planned ([#19966](https://github.com/anomalyco/opencode/issues/19966)).
- Its `read` tool treats `.docx` as binary and passes PDFs and images to the model as attachments ([`opencode/src/tool/read.ts`](https://github.com/anomalyco/opencode/blob/v1.18.34/packages/opencode/src/tool/read.ts)). The agent reads Docling text instead (Working folders, below).

## Packaging

- Stage the pinned archives and check each against its SHA-256 at build time with [`pinned-download.mjs`](../../../surfsense_local/electron/scripts/pinned-download.mjs), as [`fetch-llamacpp.mjs`](../../../surfsense_local/electron/scripts/fetch-llamacpp.mjs) does for llama.cpp.
- On x64, stage the `-baseline` archive, which opencode builds without AVX2 (`avx2: false` in [`opencode/script/build.ts`](https://github.com/anomalyco/opencode/blob/v1.18.34/packages/opencode/script/build.ts)), so the agent runs on older CPUs too.
- Ship ripgrep beside it and put that folder on the `PATH` opencode gets. On its first grep, opencode looks for `rg` on `PATH`, then in its own `bin` folder under its cache directory, and otherwise downloads it from GitHub ([`core/src/ripgrep/binary.ts`](https://github.com/anomalyco/opencode/blob/v1.18.34/packages/core/src/ripgrep/binary.ts)).
- Ship opencode's one config folder with `@opencode-ai/plugin` in `node_modules` and a `package-lock.json` that lists it. At startup opencode installs that package into every config folder in the background, unless it is already there ([`opencode/src/config/config.ts`](https://github.com/anomalyco/opencode/blob/v1.18.34/packages/opencode/src/config/config.ts) L452, [`core/src/npm.ts`](https://github.com/anomalyco/opencode/blob/v1.18.34/packages/core/src/npm.ts)). Launch it with `npm_config_audit=false` and `npm_config_fetch_retries=0`, so a case this misses fails at once instead of waiting on a network it cannot reach.
- On macOS the executable is signed with the app's existing [`entitlements.mac.plist`](../../../surfsense_local/electron/build/entitlements.mac.plist), which grants the JIT and unsigned executable memory Bun's engine uses ([Bun docs](https://bun.com/docs/guides/runtime/codesign-macos-executable)). Confirm a notarized build runs it, and that the signed Windows build runs it on a clean machine with Defender on.
- The installer downloads nothing. Today's targets are already offline builds: NSIS on Windows, dmg and zip on macOS, AppImage and deb on Linux ([`electron-builder.yml`](../../../surfsense_local/electron/electron-builder.yml)).
- The 2.0.3 installers are 1.13 GB on Windows to 1.36 GB for the AppImage ([release](https://github.com/MODSetter/SurfSense/releases/tag/v2.0.3)), against a 2 GB `makensis` ceiling on Windows ([packaging](../../architecture/packaging.md)). They grow by about the compressed archive, 46 to 62 MB. Measure them after adding opencode and ripgrep.

## Launch

- Electron's supervisor starts opencode the first time a thread needs it, with `startOne()`, the way it starts sd-server once a model is on disk ([`sidecars/supervisor.ts`](../../../surfsense_local/electron/src/main/sidecars/supervisor.ts)). One opencode serves every workspace.
- Arguments: `serve --hostname 127.0.0.1 --port <port>`, with a port the supervisor picks. Left to itself, opencode tries 4096 first ([`opencode/src/server/server.ts`](https://github.com/anomalyco/opencode/blob/v1.18.34/packages/opencode/src/server/server.ts) L120–121).
- Auth: `OPENCODE_SERVER_PASSWORD` is 32 random bytes made at each launch. With it set, the server requires basic auth, user `opencode` ([`opencode/src/server/auth.ts`](https://github.com/anomalyco/opencode/blob/v1.18.34/packages/opencode/src/server/auth.ts)). Electron passes the URL and password to the API's environment only; the renderer never sees them.
- Ready: stdout prints `opencode server listening on http://…` ([`opencode/src/cli/cmd/serve.ts`](https://github.com/anomalyco/opencode/blob/v1.18.34/packages/opencode/src/cli/cmd/serve.ts)), then `GET /global/health` answers `healthy: true` and `version: "1.18.34"` ([`groups/global.ts`](https://github.com/anomalyco/opencode/blob/v1.18.34/packages/opencode/src/server/routes/instance/httpapi/groups/global.ts)). Any other version is stopped and reported, because the backend speaks only the pinned one.
- Environment: built from an allowlist, as a plugin run builds its own ([`plugin_environment.py`](../../../surfsense_local/backend/modules/plugins/runner/plugin_environment.py)), never inherited. An inherited `OPENCODE_PERMISSION` is merged deep over SurfSense's permission rules ([`opencode/src/config/config.ts`](https://github.com/anomalyco/opencode/blob/v1.18.34/packages/opencode/src/config/config.ts) L559–561), and an inherited `OPENCODE_CONFIG`, `OPENCODE_CONFIG_CONTENT` or `OPENCODE_CONFIG_DIR` adds configuration ([`core/src/flag/flag.ts`](https://github.com/anomalyco/opencode/blob/v1.18.34/packages/core/src/flag/flag.ts)). The supervisor passes the whole parent environment to every sidecar today, so opencode's spec needs its own.
- Folders: `XDG_CONFIG_HOME`, `XDG_DATA_HOME`, `XDG_CACHE_HOME`, `XDG_STATE_HOME`, `HOME`, `USERPROFILE` and `OPENCODE_TEST_HOME` all point inside SurfSense's data folder. opencode finds its folders through `xdg-basedir`, and its home through `OPENCODE_TEST_HOME` before `os.homedir()` ([`core/src/global.ts`](https://github.com/anomalyco/opencode/blob/v1.18.34/packages/core/src/global.ts) L19). Its sessions database lives under its data folder, so it stays inside SurfSense's.
- Stop: on Windows, `taskkill /t` on the process before anything else. Elsewhere, SIGTERM to its process group, then SIGKILL to the group whether or not the parent has exited, because shell commands and MCP clients it started can outlive it.
- Leftovers: `serve` keeps running when its parent is killed (observed with `v1.18.34` on Linux). The supervisor records each opencode it starts, with its pid and port, in its data folder. At boot it stops a recorded process that is still an `opencode serve` on its recorded port, and nothing else.
- Restart: after a crash, restart at most once every 10 s, and the backend resyncs (Routes and events, below).
- A new configuration, such as another model, is not a restart. opencode reads the file per folder, the first time the folder is used, and keeps what it read, so the backend writes the file and then calls `POST /global/dispose`, which drops every folder's instance and ends their turns ([`groups/global.ts`](https://github.com/anomalyco/opencode/blob/v1.18.34/packages/opencode/src/server/routes/instance/httpapi/groups/global.ts)). opencode's own config update does the same. The event streams end with `server.instance.disposed` and are opened again. Restarting the process on a rewrite instead raced: a folder first used after the write read the new file from the old process, which the restart then cut off.

## Routes and events

The routes SurfSense uses, in [`opencode/src/server/routes/instance/httpapi/groups/`](https://github.com/anomalyco/opencode/tree/v1.18.34/packages/opencode/src/server/routes/instance/httpapi/groups):

| Route | Use |
|---|---|
| `GET /global/health` | readiness and version |
| `POST /session`, `DELETE /session/:sessionID` | open a session with a title (Configuration, below), and delete it with its thread |
| `POST /session/:sessionID/prompt_async` | send a turn; it answers 204 at once, and a failure arrives later as `session.error` |
| `POST /session/:sessionID/abort` | stop a turn |
| `GET /session/status`, `GET /session/:sessionID/message`, `GET /permission` | resync after the event stream reconnects |
| `GET /event` | the event stream, as `text/event-stream` |
| `POST /permission/:requestID/reply` | answer a permission request |
| `GET /config`, `POST /global/dispose` | check which configuration is loaded, and make every folder read the file again |

- A request's folder is `?directory=`, which wins over the `x-opencode-directory` header and the process's own folder ([`middleware/workspace-routing.ts`](https://github.com/anomalyco/opencode/blob/v1.18.34/packages/opencode/src/server/routes/instance/httpapi/middleware/workspace-routing.ts) L87). The client sends it URL-encoded, so folder names outside ASCII survive.
- `GET /event` sends `server.connected` first, then `server.heartbeat` every 10 s ([`handlers/event.ts`](https://github.com/anomalyco/opencode/blob/v1.18.34/packages/opencode/src/server/routes/instance/httpapi/handlers/event.ts) L63–71). Frames carry no `id:`, so nothing is replayed after a reconnect. The client reconnects after 20 s without a frame, and on every `server.connected` it reads session status, the open thread's messages and pending permission requests again.
- The events the client reads are `message.updated`, `message.part.updated`, `message.part.delta`, `session.status`, `session.idle`, `session.error`, `permission.asked`, `permission.replied`, `todo.updated` and `server.instance.disposed` ([`sdk/js/src/v2/gen/types.gen.ts`](https://github.com/anomalyco/opencode/blob/v1.18.34/packages/sdk/js/src/v2/gen/types.gen.ts)). A tool part moves through `pending`, `running`, `completed` and `error`.

## The backend's client

- A hand-written httpx client covers the routes above and reads the event stream. Its event model names only the fields SurfSense reads and allows the rest, so a field a newer version adds does not break parsing. The pinned version's OpenAPI document, `GET /doc` ([`server/routes/instance/httpapi/server.ts`](https://github.com/anomalyco/opencode/blob/v1.18.34/packages/opencode/src/server/routes/instance/httpapi/server.ts) L190), describes 472 schemas, of which SurfSense reads about ten, so they are not generated.
- The client waits on every call except the event stream with a timeout: right after it starts, opencode accepts a connection before it answers on it.
- One module holds everything that differs between opencode's 1.x and 2.x lines: the health check, the routes, the event envelope and names, the permission payload and the configuration writer. Moving to 2.x changes that module only.
- A turn is sent once, with a message id SurfSense makes, and never resent automatically.
- Stopping a turn aborts the session and its child sessions, waits for `session.idle`, then rejects any permission request still pending.

## The model endpoint

opencode's only provider is an OpenAI-compatible chat completions route in the API, on loopback. It serves the selected text model:

- **Remote:** through `_connection()` in [`resolution.py`](../../../surfsense_local/backend/modules/llm/resolution.py), so the API key and `egress.require()` stay in SurfSense, and the host is the one that connection already uses.
- **Local:** through llama-server's router, which loads the model ([runtime](../../architecture/local-models/runtime.md)).

What it does for opencode:

- It passes `tools` and `tool_choice` through to the model.
- It joins every `system` and `developer` message into one system message at the start and drops empty assistant turns, because local chat templates expect one system message first ([#15059](https://github.com/anomalyco/opencode/issues/15059)).
- It keeps tool schemas within what llama.cpp turns into a grammar ([`common/json-schema-to-grammar.cpp`](https://github.com/ggml-org/llama.cpp/blob/b11050/common/json-schema-to-grammar.cpp)).
- It neutralises chat-template control tokens in user and tool text, because tool results carry text from the user's documents.
- It passes the model's own status and error through. opencode reads a full window from the error's wording, and llama-server's "exceeds the available context size" is among the phrases it knows ([`llm/src/provider-error.ts`](https://github.com/anomalyco/opencode/blob/v1.18.34/packages/llm/src/provider-error.ts)), so it compacts. An error SurfSense raises itself, such as no selected model or a host egress refuses, comes back as `{"error": {"message": …}}`. Every stream ends with `[DONE]`, added when the model leaves it out.
- It sets no limit on waiting for the model, since a local model can take minutes to load and read a prompt before its first byte. opencode drops a request after 300 s without headers or without a chunk unless its provider's `headerTimeout` and `chunkTimeout` say otherwise ([`opencode/src/provider/provider.ts`](https://github.com/anomalyco/opencode/blob/v1.18.34/packages/opencode/src/provider/provider.ts) L94–100), so the configuration sets both (Configuration, below).
- It turns tool calls a model writes as plain text, such as `<tool_call>` or `<function=`, into real ones, only when the request declared tools and only for the names it declared. A model that writes them as text otherwise stalls the turn ([#24316](https://github.com/anomalyco/opencode/issues/24316)).
- It accepts only the key made at each launch. The key is written into opencode's configuration file, which only SurfSense can read, never into its environment, which shell commands inherit.

## Configuration

The backend writes one configuration file at each launch and whenever the selected model changes, and opencode reads it through `OPENCODE_CONFIG`.

- **Waiting:** the provider's `headerTimeout` and `chunkTimeout` are raised past 300 s, for the model endpoint's unlimited wait (The model endpoint, above).
- **Provider:** one, SurfSense's, on `@ai-sdk/openai-compatible`, which is built into the binary ([`opencode/src/provider/provider.ts`](https://github.com/anomalyco/opencode/blob/v1.18.34/packages/opencode/src/provider/provider.ts)), pointing at the model endpoint. `enabled_providers` lists only it ([`core/src/v1/config/config.ts`](https://github.com/anomalyco/opencode/blob/v1.18.34/packages/core/src/v1/config/config.ts)).
- **Models:** `model` and `small_model` both name the selected model. A second model would unload the first, because the router holds one at a time ([runtime](../../architecture/local-models/runtime.md)).
- **Limits**, with W the window llama-server loaded for that model, read from `/props`, or the `context` the remote catalog records:
  - `limit.context` and `limit.input` are W.
  - `limit.output` is min(W/4, 32,000).
  - `compaction.reserved` is min(output, max(W/10, 8,192)).

  With `limit.input` set, opencode compacts when the input reaches `input − reserved`. Without it, it ignores `reserved` and uses `context − output`, and an unset output counts as 32,000 ([`opencode/src/session/overflow.ts`](https://github.com/anomalyco/opencode/blob/v1.18.34/packages/opencode/src/session/overflow.ts) L10–19, [`opencode/src/provider/transform.ts`](https://github.com/anomalyco/opencode/blob/v1.18.34/packages/opencode/src/provider/transform.ts)). At W = 32,768, output is 8,192 and compaction starts at 24,576 tokens. At W = 8,192 it starts at 6,144, which the fixed prompt alone nearly fills (below), so the tested list starts at 32,768 ([`01-which-engine.md`](01-which-engine.md)).
- **Titles:** every session is created with a title, so opencode makes no title call. It generates one only while a session keeps its default title ([`opencode/src/session/prompt.ts`](https://github.com/anomalyco/opencode/blob/v1.18.34/packages/opencode/src/session/prompt.ts) L193–200).
- **Agent:** SurfSense's own primary agent, set as the default. Its `prompt` replaces opencode's coding prompt with instructions for working on sources: read the text folder, cite what `search_sources` returned, write only to the output folder, and hand a finished file over with `create_artifact` ([`02-tools.md`](02-tools.md)). It stays under 4,000 characters.
- **Off:** `"share": "disabled"`, `"snapshot": false`, `"autoupdate": false`.
- **MCP:** SurfSense's server, remote, by loopback URL, with the launch key in `headers` and `"oauth": false` ([`02-tools.md`](02-tools.md)).

**Fixed prompt size.** The default system prompt is 8,528 characters ([`opencode/src/session/prompt/default.txt`](https://github.com/anomalyco/opencode/blob/v1.18.34/packages/opencode/src/session/prompt/default.txt)). A custom agent's `prompt` replaces it, and opencode still appends more system text after it ([`opencode/src/session/llm/request.ts`](https://github.com/anomalyco/opencode/blob/v1.18.34/packages/opencode/src/session/llm/request.ts)). Each tool sent adds its description ([`opencode/src/tool/`](https://github.com/anomalyco/opencode/tree/v1.18.34/packages/opencode/src/tool)):

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

Those eleven add up to 11,716 characters. A tool denied with the pattern `*` is left out of the list sent to the model ([`opencode/src/permission/index.ts`](https://github.com/anomalyco/opencode/blob/v1.18.34/packages/opencode/src/permission/index.ts)). Measure the real token cost with llama-server's `/tokenize`, which the app already calls, once SurfSense's prompt and MCP tools exist.

## No network

| What opencode would fetch | Defined in | How SurfSense prevents it |
|---|---|---|
| Its model catalog, when `serve` starts and every hour | [`core/src/models-dev.ts`](https://github.com/anomalyco/opencode/blob/v1.18.34/packages/core/src/models-dev.ts) | `OPENCODE_DISABLE_MODELS_FETCH=1` |
| `@opencode-ai/plugin` from npm, into each config folder, at startup | [`opencode/src/config/config.ts`](https://github.com/anomalyco/opencode/blob/v1.18.34/packages/opencode/src/config/config.ts), [`core/src/npm.ts`](https://github.com/anomalyco/opencode/blob/v1.18.34/packages/core/src/npm.ts) | Ship the config folder with the package installed (Packaging, above), plus `npm_config_audit=false` and `npm_config_fetch_retries=0` |
| ripgrep from GitHub | [`core/src/ripgrep/binary.ts`](https://github.com/anomalyco/opencode/blob/v1.18.34/packages/core/src/ripgrep/binary.ts) | Ship `rg` (Packaging, above) |
| Its update check | [`opencode/src/cli/upgrade.ts`](https://github.com/anomalyco/opencode/blob/v1.18.34/packages/opencode/src/cli/upgrade.ts) | `OPENCODE_DISABLE_AUTOUPDATE=1` and `"autoupdate": false` |
| Shared sessions on opencode's servers | [`opencode/src/share/share-next.ts`](https://github.com/anomalyco/opencode/blob/v1.18.34/packages/opencode/src/share/share-next.ts) | `OPENCODE_DISABLE_SHARE=1` and `"share": "disabled"` |
| LSP server downloads | [`opencode/src/effect/runtime-flags.ts`](https://github.com/anomalyco/opencode/blob/v1.18.34/packages/opencode/src/effect/runtime-flags.ts) | `OPENCODE_DISABLE_LSP_DOWNLOAD=1` |
| Web pages and web search | the `webfetch` and `websearch` tools | `deny` both |
| opencode's own hosted provider | `enabled_providers` in [`core/src/v1/config/config.ts`](https://github.com/anomalyco/opencode/blob/v1.18.34/packages/core/src/v1/config/config.ts) | List only SurfSense's provider |
| Its built-in plugins, which sign in to hosted providers | [`opencode/src/plugin/index.ts`](https://github.com/anomalyco/opencode/blob/v1.18.34/packages/opencode/src/plugin/index.ts) L67–79, L170 | `OPENCODE_DISABLE_DEFAULT_PLUGINS=1` |
| Configured plugins, including plugin files on disk | [`opencode/src/plugin/index.ts`](https://github.com/anomalyco/opencode/blob/v1.18.34/packages/opencode/src/plugin/index.ts) L181, [`opencode/src/effect/runtime-flags.ts`](https://github.com/anomalyco/opencode/blob/v1.18.34/packages/opencode/src/effect/runtime-flags.ts) | `OPENCODE_PURE=1`; SurfSense ships no opencode plugins |
| Config, plugins and MCP servers from a `.opencode` folder or `opencode.json` in the working folder | [`opencode/src/config/paths.ts`](https://github.com/anomalyco/opencode/blob/v1.18.34/packages/opencode/src/config/paths.ts) | `OPENCODE_DISABLE_PROJECT_CONFIG=1` |
| Skills and instructions from other tools' folders | [`opencode/src/effect/runtime-flags.ts`](https://github.com/anomalyco/opencode/blob/v1.18.34/packages/opencode/src/effect/runtime-flags.ts) | `OPENCODE_DISABLE_EXTERNAL_SKILLS=1` and `OPENCODE_DISABLE_CLAUDE_CODE=1`; with its home inside SurfSense's data folder, those folders are empty anyway |
| OpenTelemetry export | [`core/src/observability/otlp.ts`](https://github.com/anomalyco/opencode/blob/v1.18.34/packages/core/src/observability/otlp.ts) | Leave `OTEL_EXPORTER_OTLP_ENDPOINT` unset |
| Its web UI from `https://app.opencode.ai` | [`opencode/src/server/shared/ui.ts`](https://github.com/anomalyco/opencode/blob/v1.18.34/packages/opencode/src/server/shared/ui.ts) | Never set `OPENCODE_DISABLE_EMBEDDED_WEB_UI`, which forces that fallback; confirm the staged binary embeds the UI |

**Enforcing it.** opencode needs no host beyond loopback: models go through the model endpoint, tools through SurfSense's MCP server, and everything else above is switched off or shipped. So SurfSense launches it with `HTTP_PROXY`, `HTTPS_PROXY` and `ALL_PROXY` pointing at a loopback port nothing listens on, and `NO_PROXY` covering `127.0.0.1`, `localhost` and `::1`. Bun's `fetch` reads those variables on each request ([Bun docs](https://bun.com/docs/runtime/networking/fetch)), and opencode's HTTP client is Effect's `FetchHttpClient` over the global `fetch` ([`core/src/effect/app-node-platform.ts`](https://github.com/anomalyco/opencode/blob/v1.18.34/packages/core/src/effect/app-node-platform.ts)). Anything this table misses fails instead of leaving the machine. Settings › Network gains nothing: opencode is never a destination, and a remote model's host is the one its connection already uses ([egress](../../architecture/egress.md)). What it does not cover:

- WebSockets: Bun does not apply these variables to them, and opencode passes a proxy by hand only on its OpenAI Responses WebSocket path ([`opencode/src/plugin/openai/ws.ts`](https://github.com/anomalyco/opencode/blob/v1.18.34/packages/opencode/src/plugin/openai/ws.ts)).
- Programs a shell command starts, which can ignore the variables ([ADR 0028](../../adr/0028-model-written-code-runs-with-approval.md)).

A test runs opencode with every connection beyond loopback refused and fails if it tries one.

## Permissions

- opencode's built-in default is `allow` for every tool, with `doom_loop` and `external_directory` set to `ask` ([`opencode/src/agent/agent.ts`](https://github.com/anomalyco/opencode/blob/v1.18.34/packages/opencode/src/agent/agent.ts) L119–126), so SurfSense's agent sets each rule it needs:
  - `bash` is `ask`.
  - `edit` and `write` are allowed inside the output folder and denied elsewhere, and `external_directory` is `deny`. The shell tool also checks `external_directory` for paths outside the working folder ([`opencode/src/tool/shell.ts`](https://github.com/anomalyco/opencode/blob/v1.18.34/packages/opencode/src/tool/shell.ts)). Write this rule set and test it before shipping.
  - `webfetch`, `websearch`, `task`, `question` and `skill` are `deny`. `task` starts child sessions that wait on the same single llama-server slot, `question` needs a form SurfSense does not build in this phase, and SurfSense ships no skills.
- opencode publishes each request as `permission.asked`, with the tool, its patterns and, for `bash`, the full command in `metadata.command`. The backend relays it to the thread, the app shows the command in full with the folder it runs in, and the backend answers `once` or `reject` through `POST /permission/:requestID/reply` ([ADR 0028](../../adr/0028-model-written-code-runs-with-approval.md)).
- SurfSense never answers `always`. ADR 0028 asks before every command, and `always` adds an allow rule to the running opencode that covers every session in that folder until it restarts ([`opencode/src/permission/index.ts`](https://github.com/anomalyco/opencode/blob/v1.18.34/packages/opencode/src/permission/index.ts) L145–163).
- `reject` also rejects every other request pending in the same session (the same file, L121–139), so when several are waiting the app says so before the user rejects one.
- Snapshots are off with `"snapshot": false`. They are also off in any folder that is not a git repository ([`opencode/src/snapshot/index.ts`](https://github.com/anomalyco/opencode/blob/v1.18.34/packages/opencode/src/snapshot/index.ts)).
- `OPENCODE_EXPERIMENTAL` and `OPENCODE_EXPERIMENTAL_CODE_MODE` stay unset; the first turns on the second ([`opencode/src/effect/runtime-flags.ts`](https://github.com/anomalyco/opencode/blob/v1.18.34/packages/opencode/src/effect/runtime-flags.ts)).

## Working folders

opencode's working folder belongs to SurfSense, not the user:

- **A text view:** each ready source's extracted markdown as a `.md` file. opencode's own `read`, `grep` and `glob` then work on Docling text. The agent can only read it.
- **An output folder** the agent can write to.

Neither may sit inside a git repository. opencode treats a git repository's root as the project ([`opencode/src/project/project.ts`](https://github.com/anomalyco/opencode/blob/v1.18.34/packages/opencode/src/project/project.ts) L306), which would widen what counts as inside the working folder. A test checks that opencode reports the working folder itself as its project root.

Each source's file is `<title> [<id>].md`: the title with the characters a file system refuses or a path needs replaced, cut at 100 characters, and the document's id, which keeps two sources with one title apart. The text view is brought in line with the workspace's ready `FILE` and `NOTE` documents before each turn, writing only files whose text changed; artifacts are outputs, not sources, and stay out. Sources from a linked folder will keep their relative paths ([`05-sources-folder.md`](05-sources-folder.md)).

A custom tool named `read` replaces the built-in one. Custom tools load from a `tool/` or `tools/` folder in a config folder and are keyed by id, with custom tools added after built-ins ([`opencode/src/tool/registry.ts`](https://github.com/anomalyco/opencode/blob/v1.18.34/packages/opencode/src/tool/registry.ts), [`opencode/src/session/tools.ts`](https://github.com/anomalyco/opencode/blob/v1.18.34/packages/opencode/src/session/tools.ts)). That is the fallback if the text view is not enough.

## The conversation

- A thread that uses the agent stores its opencode session id in one nullable column on `chat_threads` ([`modules/chat/models.py`](../../../surfsense_local/backend/modules/chat/models.py)). Its turns live in opencode's sessions database, inside SurfSense's data folder, and SurfSense does not copy them.
- Deleting the thread deletes the session. Deleting a workspace stops its running turns first, then deletes its sessions.
- Where the thread appears and which engine it gets are in [`01-which-engine.md`](01-which-engine.md).

## Open questions

- What the agent does when SurfSense's data folder sits inside a git repository, such as a home folder kept in git.
- Whether `todowrite` earns its 2,012 characters on a 32,768-token window, once the fixed prompt is measured.
