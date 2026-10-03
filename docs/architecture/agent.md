# Agent

A chat thread can be the agent's. opencode, bundled in the installer and started by Electron, then answers it in steps: it finds passages with SurfSense's search, reads a folder of the workspace's extracted text with its own tools, cites what it found as a chat answer does, starts Studio jobs, writes what it produces to an output folder, reaches every model through SurfSense, and asks the user before every shell command. Which engine a thread gets is decided when the thread opens. No model is on the tested list yet, so only a developer switch lets one in.

**Code:** [`surfsense_local/backend/modules/agent/`](../../surfsense_local/backend/modules/agent/), [`surfsense_local/electron/src/main/sidecars/opencode.ts`](../../surfsense_local/electron/src/main/sidecars/opencode.ts), [`surfsense_local/electron/scripts/opencode/`](../../surfsense_local/electron/scripts/opencode/), [`surfsense_local/frontend/src/features/agent/`](../../surfsense_local/frontend/src/features/agent/)
**Decisions:** [ADR 0028](../adr/0028-model-written-code-runs-with-approval.md). The remaining work is in the [agent proposal](../proposals/agent/README.md).

## The parts

| Part | Where | Does |
|---|---|---|
| Staging | `electron/scripts/opencode/` | `pnpm build:opencode` fetches opencode `1.18.34` and ripgrep `15.1.0`, each checked against its SHA-256, into `electron/opencode/` ([packaging](packaging.md)) |
| Process | `electron/src/main/sidecars/opencode.ts`, `opencode-home.ts`, `opencode-leftovers.ts`, `watchAgentConfig` in `index.ts` | starts, stops and cleans up `opencode serve` ([overview](overview.md)) |
| Engine choice | `backend/modules/agent/engine_choice.py` | whether a thread opened now is the agent's |
| Configuration | `opencode_config.py`, `prompts/agent.md` | the file opencode runs with |
| Readiness | `opencode_runtime.py`, `model_window.py` | an opencode serving the current configuration |
| Model endpoint | `model_endpoint/` | the one route opencode's provider calls, for every model |
| Tools | `tool_endpoint/` | SurfSense's search and Studio, served to opencode over MCP, one address per workspace |
| Sources folder | `sources_folder.py` | each ready source's extracted text as a file the agent can read |
| Client | `opencode_client/` | the only code that knows opencode 1.x's HTTP API |
| Threads | `agent_threads/`, and the chat routes that hand over to it | opening, sending to, reading and deleting an agent thread ([chat](chat.md#agent-threads)) |
| Screen | `frontend/src/features/agent/` | a reply's steps, and the approval dialog |

## Which threads get it

A new thread is the agent's when the selected text model is in `TESTED_MODELS`, or `SURFSENSE_LOCAL_AGENT_UNTESTED_MODELS=1` is set in the environment Electron starts the API from, and the model is known to call tools: llama-server reports `supports_tool_calls` for a local model's template, or the remote catalog records `tool_call: true` for the model under its connection's catalog provider. A runtime that cannot be read counts as no. A catalog that says nothing counts as no for a tested model and as yes under the developer switch, because the packaged catalog lags the providers and a model released after it is the one most worth trying; a stated `tool_call: false` keeps a model out either way ([`engine_choice.py`](../../surfsense_local/backend/modules/agent/engine_choice.py)). `TESTED_MODELS` is empty: a model goes on it once it passes the agent test at a window of 32,768 tokens or more ([proposal](../proposals/agent/01-which-engine.md#what-tested-means)). When opencode is not staged, or does not become ready, the thread opens as a chat. A thread keeps its engine; its row stores the opencode session that holds its turns ([data model](data-model.md)). Once the selected model changes to one that fails the check, a turn sent to the thread is refused with `409` before any prompt is sent: the user chooses another model or starts a new chat.

## From a thread to a running opencode

1. **Electron, at boot.** Where an opencode is staged, Electron picks its port and a random password, passes both to the API alone, and removes any `agent/opencode.json` the last run left. opencode does not start yet.
2. **The API, when a thread first needs the agent.** `ready_opencode()` reads the selected model's window: what llama-server loaded a local model with, or the `context` the remote catalog records, else 32,768. It writes `<data>/agent/opencode.json`, readable by this user only, and only when its contents change.
3. **Electron, on that file.** Checked every 2 seconds: opencode starts once the file exists and stops when it goes. A crash restarts it, at most once every 10 seconds. A rewrite does not restart it.
4. **The API, until opencode serves it.** opencode reads its configuration per folder, the first time the folder is used, and keeps what it read. So the API checks the running server's version is `1.18.34`, reads `GET /config`, and calls `POST /global/dispose` once if what is loaded is not the launch key and window just written. It returns when they match, or after 60 seconds with "not ready". Every call has a timeout, because opencode accepts a connection a moment before it answers it.

## The configuration

| Setting | Value |
|---|---|
| Provider | one, `surfsense`, on `@ai-sdk/openai-compatible`, at `http://<API host>:<API port>/agent/model/v1`, with the launch key as its API key; `enabled_providers` lists only it |
| Models | `model` and `small_model` both name the selected model, so nothing asks for a second one the router would load in its place |
| Limits | `context` and `input` are the window W; `output` is min(W/4, 32,000); `compaction.reserved` is min(output, max(W/10, 8,192)) |
| Waiting | `headerTimeout` off and `chunkTimeout` 30 minutes, because a local model can take minutes before its first byte |
| Permissions | `bash` asks; `edit` and `write` are allowed under `outputs/` and denied elsewhere; `external_directory`, `webfetch`, `websearch`, `task`, `question` and `skill` are denied; SurfSense's two tools run without asking, by opencode's default |
| Agent | `surfsense`, the default, whose prompt replaces opencode's coding prompt with how to work on the user's sources ([`prompts/agent.md`](../../surfsense_local/backend/modules/agent/prompts/agent.md)) |
| Off | `share`, `snapshot`, `autoupdate` |

The API makes a new launch key at every start ([`launch_key.py`](../../surfsense_local/backend/modules/agent/launch_key.py)), so a configuration from an earlier run never opens the model endpoint or the tools.

## Folders

```text
<data>/agent/
├── opencode.json             the configuration the API writes
├── opencode-process.json     the running opencode's pid, port and password, for the next boot
└── opencode/                 opencode's home: its XDG config, data, cache and state, sessions included
<data>/data/workspaces/<id>/agent/
├── sources/                  one `<title> [<id>].md` per ready FILE or NOTE, rewritten only when its text changed
└── outputs/                  what the agent writes; never touched by SurfSense
```

The workspace's folder is opencode's working folder for its sessions, and it goes when the workspace does. A title's characters that a file system refuses or a path needs are replaced, it is cut at 100 characters, and the id keeps two sources with one title apart. Artifacts are outputs, not sources, and stay out.

## The model endpoint

`POST /agent/model/v1/chat/completions` ([`model_endpoint/`](../../surfsense_local/backend/modules/agent/model_endpoint/)) is opencode's only way to a model. It refuses a request without this process's launch key with `401`, resolves the selected model on every request, and marks it in use while the turn runs.

- **Local:** llama-server's router at `{llamacpp_base_url}/v1`, under the selected model's name.
- **Remote:** the connection's URL with its own key, once `egress.require()` allows its host; a refused host answers `403` naming it, before any connection opens ([egress](egress.md)).
- **The request:** `tools` and `tool_choice` pass through; every `system` and `developer` message is joined into one system message first, because local chat templates want one there; assistant turns with no text and no call are dropped; control tokens such as `<|im_end|>` in user and tool text are split by a zero-width space, because tool results carry the user's documents.
- **The reply:** the model's own status and body pass through, so opencode reads a full window from llama-server's own wording and compacts. SurfSense's own errors are `{"error": {"message": …}}`. Every stream ends with `[DONE]`, added when the model leaves it out. There is no limit on waiting; opencode's configuration sets its own.

## SurfSense's tools

`POST /agent/tools/workspaces/{workspace_id}` ([`tool_endpoint/`](../../surfsense_local/backend/modules/agent/tool_endpoint/)) answers opencode's MCP client: MCP `2025-11-25` over Streamable HTTP, stateless and JSON only, written without an MCP library. It answers `initialize`, `tools/list`, `tools/call` and `ping`, and `202` to a notification. It refuses a request without the launch key with `401`, one carrying an `Origin` header, as a web page's does, with `403`, another protocol version with `400`, a workspace that does not exist with `404`, and `GET` with `405`. The workspace in the path scopes every tool, because a tool call names neither its folder nor its session.

| Tool, as the model sees it | Takes | Does |
|---|---|---|
| `surfsense_search_sources` | `query` | the chat's own `retrieve()` over the workspace's ready files and notes, never artifacts; up to 5 passages, each as `<passage cite="[<chunk id>]" source="sources/<file>" lines="<a>-<b>">`, the lines being that file's |
| `surfsense_create_artifact` | `format`, one of Studio's 12; `source_ids`, the numbers at the end of the source files' names; `instructions`, at most 2,000 characters | Studio's own `create_artifact_job()`, which returns at once with the artifact pending |

Both schemas are flat and the same on every turn. A call the tool cannot carry out comes back as a tool error the model reads: no query, no sources named, Studio's own reason such as "Needs a chat model", or a search before onboarding has chosen an embedder or while its files are missing, which points the model at `grep`. A source's own text loses any `passage` tag, so it cannot make up a label.

Before each turn the API adds the tools to the turn's working folder with opencode's `POST /mcp?directory=…`: the server `surfsense`, the workspace's URL, the launch key as a header and OAuth off ([`registration.py`](../../surfsense_local/backend/modules/agent/tool_endpoint/registration.py)). opencode keeps it in memory for that folder alone and drops it when it reloads, so it is added on every turn, and nothing is written to `opencode.json`, which every folder shares. opencode then lists the tools and names them `surfsense_<tool>`. When it cannot reach them, the turn runs with its own tools and the API logs why. The chat panel shows their steps as "Searched the sources for …" and "Started … in Studio".

## A turn

The thread routes in [chat](chat.md#agent-threads) hand an agent thread to `agent_threads/`:

1. The workspace's sources folder is brought in line, opencode is made ready, and the workspace's tools are added to its folder.
2. The folder's event stream is opened before the message is sent, so no event of the turn is missed. The message goes with `prompt_async`, naming the selected model, so a thread keeps working after a model change.
3. Events for the thread's session become the chat's frames, plus `agent-step`, `permission-request` and `permission-replied` ([`turn_frames.py`](../../surfsense_local/backend/modules/agent/agent_threads/turn_frames.py)).
4. A stream silent for 20 seconds, twice opencode's heartbeat, is reopened, and so is one that drops; after a reopen, an idle session ends the turn. Twenty failures in a row end it with an error.
5. On `session.idle`, `completed` carries the reply as opencode stored it: the text of every assistant message opencode wrote for this turn, joined. A label one of the session's searches returned becomes `[citation:<chunk id>]` through the chat's own `resolve_citations()`, and any other bracketed number is dropped ([`citations.py`](../../surfsense_local/backend/modules/agent/agent_threads/citations.py)). A `citations` frame comes first when the reply cites anything.
6. When the client hangs up before that, the session's turn is aborted.

## Approvals

opencode asks before every shell command, because the configuration sets `bash` to `ask`. The request reaches the thread as `permission-request` with the full command. The screen shows the oldest waiting one in an alert dialog, with Deny and Allow once, and Esc answering Deny. The answer goes to `POST /chat/threads/{thread_id}/permissions/{request_id}`, which passes `once` or `reject` to opencode. SurfSense never answers `always` ([ADR 0028](../adr/0028-model-written-code-runs-with-approval.md)). opencode rejects every other request waiting in the same session when one is rejected, and the dialog says so when others wait.

## Network

opencode needs no host beyond loopback: its model is the model endpoint, and its tools are its own and SurfSense's, on the API's port. Its environment is built from a few system variables rather than inherited. It sets `OPENCODE_DISABLE_MODELS_FETCH`, `OPENCODE_DISABLE_SHARE`, `OPENCODE_DISABLE_LSP_DOWNLOAD`, `OPENCODE_DISABLE_AUTOUPDATE`, `OPENCODE_DISABLE_DEFAULT_PLUGINS`, `OPENCODE_PURE`, `OPENCODE_DISABLE_PROJECT_CONFIG`, `OPENCODE_DISABLE_EXTERNAL_SKILLS` and `OPENCODE_DISABLE_CLAUDE_CODE`. Its proxy variables point at `127.0.0.1:9`, where nothing listens, with loopback exempted, so a fetch this misses fails rather than leaving the machine. The npm install opencode would otherwise run at startup is skipped: its config folder holds an empty `node_modules` and a lockfile naming the package. ripgrep is the shipped one, first on its `PATH`. Settings › Network gains nothing: opencode is never a destination, and a remote model's host is checked as its connection's.

## Tests

- **Backend:** [`tests/integration/agent/`](../../surfsense_local/backend/tests/integration/agent/) and [`tests/unit/agent/`](../../surfsense_local/backend/tests/unit/agent/). The client, readiness and thread tests start the staged opencode against a scripted model, and the thread tests also run the real API on a port. The tool endpoint tests drive the app in-process, as opencode's MCP client calls it. They skip where `pnpm build:opencode` has not staged a build.
- **Electron:** the sidecar tests in [`electron/src/main/sidecars/`](../../surfsense_local/electron/src/main/sidecars/) and the pins test in `electron/scripts/opencode/`.
- **Frontend:** [`features/agent/agent-thread.test.tsx`](../../surfsense_local/frontend/src/features/agent/agent-thread.test.tsx), on the real dashboard against a stream that waits for the test's answer.

## Known gaps

- No model is on the tested list, and no agent test exists to put one there; only the developer switch lets a model in.
- A turn refused because the selected model cannot run the agent shows as an error with Retry; the composer does not offer a new thread, as the [proposal](../proposals/agent/01-which-engine.md#when-a-thread-gets-its-engine) has it.
- The model endpoint neither simplifies tool schemas to what llama.cpp's grammar takes nor turns a tool call a model writes as text into a real one, so small local models stall where a remote one would not.
- A file the agent writes to `outputs/` does not become an artifact.
- A Studio job the agent starts runs on the same local model as the agent, so the agent's next step waits behind it.
- An artifact the agent starts records neither the thread nor the step that started it: the tool call reaches SurfSense without either.
- Sources unticked in the sources panel still reach the agent: `sources/` holds every ready source and `surfsense_search_sources` searches them all, where a chat thread searches only the ticked ones. The ticks can change with each message, while every thread of a workspace shares one `sources/`.
- A passage's label is its chunk id, a number of several digits, which a small local model copies less reliably than a chat answer's `[1]` to `[5]`. A mistyped label is dropped, so the citation is lost rather than wrong. Nothing has measured how many are lost.
- Bringing `sources/` in line reads every ready source's text from the database before each turn, to compare it with the files, so a workspace with many large sources pays for that on every turn.
- A configuration rewrite, which a change of model or window causes, ends every running agent turn in every workspace.
- Opening the first agent thread waits for opencode to start and for a local model to load, up to a minute, with nothing on screen but the thread being created.
- A shell command the agent runs inherits opencode's environment, `OPENCODE_SERVER_PASSWORD` included, so a command the user approved can call opencode's own API, approval replies among it. The approval prompt shows the command in full.
- When SurfSense's data folder sits inside a git repository, such as a home folder kept in git, opencode counts the repository's root as its project. Nothing detects it.
- No test runs opencode with every connection beyond loopback refused to check that it opens none.
- The installers have not been measured or tried with opencode: its size, a notarized build on macOS, and a signed build under Defender on Windows.
