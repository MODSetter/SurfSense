# Agent

A chat thread can be the agent's. opencode, started by Electron, then answers it in steps: it finds passages with SurfSense's search, reads a folder of the workspace's extracted text with its own tools, cites what it found as a chat answer does, makes Word documents and PDFs as versioned scripts that SurfSense runs and lets it look at, starts other Studio jobs, writes what else it produces to an output folder, and reaches every model through SurfSense. It has no shell ([ADR 0039](../adr/0039-document-scripts-run-without-approval.md)). Which engine a thread gets is decided when the thread opens. No model is on the tested list yet, so opencode is off: no installer or dev run carries it unless `SURFSENSE_LOCAL_OPENCODE_ENABLED=1` is set when it is staged, and even then only a developer switch lets a model in. How to run it from a dev build is in [07-dev-setup](../proposals/file-agent/07-dev-setup.md).

**Code:** [`surfsense_local/backend/modules/agent/`](../../surfsense_local/backend/modules/agent/), [`surfsense_local/electron/src/main/sidecars/opencode.ts`](../../surfsense_local/electron/src/main/sidecars/opencode.ts), [`surfsense_local/electron/src/main/docx-snapshot/`](../../surfsense_local/electron/src/main/docx-snapshot/), [`surfsense_local/electron/scripts/opencode/`](../../surfsense_local/electron/scripts/opencode/), [`surfsense_local/frontend/src/features/agent/`](../../surfsense_local/frontend/src/features/agent/), [`surfsense_local/frontend/src/features/docx-snapshot/`](../../surfsense_local/frontend/src/features/docx-snapshot/)
**Decisions:** [ADR 0039](../adr/0039-document-scripts-run-without-approval.md), which supersedes [ADR 0028](../adr/0028-model-written-code-runs-with-approval.md) in part. The remaining work is in the [agent proposal](../proposals/agent/README.md) and the [file agent proposal](../proposals/file-agent/README.md).

## The parts

| Part | Where | Does |
|---|---|---|
| Staging | `electron/scripts/opencode/` | `pnpm build:opencode` fetches opencode `1.18.34` and ripgrep `15.1.0`, each checked against its SHA-256, into `electron/opencode/` ([packaging](packaging.md)), only when [`enabled.mjs`](../../surfsense_local/electron/scripts/opencode/enabled.mjs) says opencode is on |
| Process | `electron/src/main/sidecars/opencode.ts`, `opencode-home.ts`, `opencode-leftovers.ts`, `watchAgentConfig` in `index.ts` | starts, stops and cleans up `opencode serve` ([overview](overview.md)) |
| Engine choice | `backend/modules/agent/engine_choice.py` | whether a thread opened now is the agent's |
| Configuration | `opencode_config.py`, `prompts/agent.md`, `skills/` | the file opencode runs with, and the one skill it may load |
| Readiness | `opencode_runtime.py`, `model_window.py`, `model_reads_images.py` | an opencode serving the current configuration |
| Model endpoint | `model_endpoint/` | the one route opencode's provider calls, for every model |
| Tools | `tool_endpoint/` | SurfSense's search, Studio and document tools, served to opencode over MCP, one address per workspace |
| Sources folder | `sources_folder.py` | each ready source's extracted text as a file the agent can read, and copies of the figures it listed |
| Previews | `previews/`, `electron/src/main/docx-snapshot/`, `frontend/src/features/docx-snapshot/` | page images of a document the agent made, so it can check them |
| Client | `opencode_client/` | the only code that knows opencode 1.x's HTTP API |
| Threads | `agent_threads/`, and the chat routes that hand over to it | opening, sending to, reading and deleting an agent thread ([chat](chat.md#agent-threads)) |
| Screen | `frontend/src/features/agent/` | a reply's steps, the versions it made, and the approval dialog |

## Which threads get it

A new thread is the agent's when the selected text model is in `TESTED_MODELS`, or `SURFSENSE_LOCAL_AGENT_UNTESTED_MODELS=1` is set in the environment Electron starts the API from, and the model is known to call tools: llama-server reports `supports_tool_calls` for a local model's template, or the remote catalog records `tool_call: true` for the model under its connection's catalog provider. A runtime that cannot be read counts as no. A catalog that says nothing counts as no for a tested model and as yes under the developer switch, because the packaged catalog lags the providers and a model released after it is the one most worth trying; a stated `tool_call: false` keeps a model out either way ([`engine_choice.py`](../../surfsense_local/backend/modules/agent/engine_choice.py)). `TESTED_MODELS` is empty: a model goes on it once it passes the agent test at a window of 32,768 tokens or more ([proposal](../proposals/agent/01-which-engine.md#what-tested-means)). When opencode is not staged, or does not become ready, the thread opens as a chat. A thread keeps its engine; its row stores the opencode session that holds its turns ([data model](data-model.md)). Once the selected model changes to one that fails the check, a turn sent to the thread is refused with `409` before any prompt is sent: the user chooses another model or starts a new chat.

## From a thread to a running opencode

1. **Electron, at boot.** Where an opencode is staged, Electron picks its port, a random password and a random Word snapshot key, passes them to the API alone, and removes any `agent/opencode.json` the last run left. opencode does not start yet. Where none is staged, Electron passes nothing, and the API mounts none of the routes opencode calls or that answer it: the model endpoint, the tool endpoint, the permission answer and the Word snapshot routes.
2. **The API, when a thread first needs the agent.** `ready_opencode()` reads the selected model's window: what llama-server loaded a local model with, or the `context` the remote catalog records, else 32,768. It reads whether the model reads images ([Image input](#image-input)). It writes `<data>/agent/opencode.json`, readable by this user only, and only when its contents change.
3. **Electron, on that file.** Checked every 2 seconds: opencode starts once the file exists and stops when it goes. A crash restarts it, at most once every 10 seconds. A rewrite does not restart it.
4. **The API, until opencode serves it.** opencode reads its configuration per folder, the first time the folder is used, and keeps what it read. So the API checks the running server's version is `1.18.34`, reads `GET /config`, and calls `POST /global/dispose` once if what is loaded is not the launch key, window and image input just written. It returns when they match, or after 60 seconds with "not ready". Every call has a timeout, because opencode accepts a connection a moment before it answers it.

## The configuration

| Setting | Value |
|---|---|
| Provider | one, `surfsense`, on `@ai-sdk/openai-compatible`, at `http://<API host>:<API port>/agent/model/v1`, with the launch key as its API key; `enabled_providers` lists only it |
| Models | `model` and `small_model` both name the selected model, so nothing asks for a second one the router would load in its place. Its entry declares `tool_call`, and image input (`modalities.input` `["text", "image"]` and `attachment: true`) only for a model that reads images |
| Limits | `context` and `input` are the window W; `output` is min(W/4, 32,000); `compaction.reserved` is min(output, max(W/10, 8,192)), with `compaction.auto` on |
| Waiting | `headerTimeout` off and `chunkTimeout` 30 minutes, because a local model can take minutes before its first byte |
| Skills | `skills.paths` names the shipped skills folder, inside the API's own files when frozen |
| Permissions | `bash` is denied; `edit` and `write` are allowed under `outputs/` and denied elsewhere; `external_directory` is denied except the skills folder, with any path holding `/../` denied after that allow; `skill` allows only `surfsense-documents`; `webfetch`, `websearch`, `task` and `question` are denied; SurfSense's tools run without asking, by opencode's default |
| Agent | `surfsense`, the default, whose prompt replaces opencode's coding prompt with how to work on the user's sources ([`prompts/agent.md`](../../surfsense_local/backend/modules/agent/prompts/agent.md)) |
| Off | `share`, `snapshot`, `autoupdate` |

The API makes a new launch key at every start ([`launch_key.py`](../../surfsense_local/backend/modules/agent/launch_key.py)), so a configuration from an earlier run never opens the model endpoint or the tools. opencode adds its own allow for its tool-output folder after these rules, where it keeps a long tool result for the agent to page through; nothing here denies it.

## The documents skill

[`skills/surfsense-documents/SKILL.md`](../../surfsense_local/backend/modules/agent/skills/surfsense-documents/SKILL.md) is SurfSense's own text. It teaches the script contract (write the file to `OUTPUT_PATH`, open source images at `IMAGES_DIR/<name>.png`, python-docx for Word, ReportLab for PDF, matplotlib for charts saved as a PNG and placed), clean-document habits (built-in heading and list styles, real tables with a header row, A4 unless the user is in the US or Canada, images at most the text width), charts from a source figure's values, editing (read the script, change only what was asked, make every requested change and say what was assumed, render with `artifact_id`), checking the previews, and the stop rule. Its Word and PDF examples run through the real runner in a test.

opencode finds it through `skills.paths` and offers it by its name and description; the agent loads it with opencode's `skill` tool, which the permission allows for this skill only, so neither opencode's built-in skills nor any the user installed for their own opencode load. The prompt tells the agent to load it before a Word document or a PDF and repeats the editing rule in one line, because a compaction can drop a loaded skill from the context while the prompt stays. `bundling/api.spec` ships it ([packaging](packaging.md)).

## Image input

[`model_reads_images.py`](../../surfsense_local/backend/modules/agent/model_reads_images.py) answers whether the selected model reads images as the chat does ([ADR 0034](../adr/0034-vision-is-the-runtimes-answer-stored-nowhere.md)): llama-server's `/models` for a local model, the remote catalog's `modalities.input` under the connection's catalog provider for a remote one. A model the catalog does not know, or whose entries disagree, answers no, with no developer switch, because an image a text-only model refuses fails the request and opencode re-sends it with every later one.

When the entry declares image input, an image opencode's `read` returns reaches the model: the openai-compatible SDK cannot carry media in a tool result, so opencode moves it into a user message, and the model endpoint passes the part through as an OpenAI `image_url`. Without the declaration, opencode replaces each image with an error text before the request leaves it, and the skill tells the agent to check the script and the returned text instead and not to open the previews again. A live run carried page images to Claude Sonnet 5.5 through Anthropic's OpenAI-compatible API, and the model described them correctly.

## Folders

```text
<data>/agent/
├── opencode.json             the configuration the API writes
├── opencode-process.json     the running opencode's pid, port and password, for the next boot
└── opencode/                 opencode's home: its XDG config, data, cache and state, sessions included
<data>/data/workspaces/<id>/agent/
├── sources/                  one `<title> [<id>].md` per ready FILE or NOTE, rewritten only when its text changed
│   └── figures/              `<source id>-<n>.png`, a copy of each figure `surfsense_list_images` listed
└── outputs/                  what the agent writes; never touched by SurfSense except previews/
    └── previews/<artifact id>-v<n>/page-<k>.png
```

The workspace's folder is opencode's working folder for its sessions, and it goes when the workspace does. A title's characters that a file system refuses or a path needs are replaced, it is cut at 100 characters, and the id keeps two sources with one title apart. Artifacts are outputs, not sources, and stay out. A figure copy goes when its source does, as the source's text does.

## The model endpoint

`POST /agent/model/v1/chat/completions` ([`model_endpoint/`](../../surfsense_local/backend/modules/agent/model_endpoint/)) is opencode's only way to a model. It refuses a request without this process's launch key with `401`, resolves the selected model on every request, and marks it in use while the turn runs.

- **Local:** llama-server's router at `{llamacpp_base_url}/v1`, under the selected model's name.
- **Remote:** the connection's URL with its own key, once `egress.require()` allows its host; a refused host answers `403` naming it, before any connection opens ([egress](egress.md)).
- **The request:** `tools` and `tool_choice` pass through; every `system` and `developer` message is joined into one system message first, because local chat templates want one there; assistant turns with no text and no call are dropped; control tokens such as `<|im_end|>` in user and tool text are split by a zero-width space, because tool results carry the user's documents. Image parts pass through untouched.
- **The reply:** the model's own status and body pass through, so opencode reads a full window from llama-server's own wording and compacts. SurfSense's own errors are `{"error": {"message": …}}`. Every stream ends with `[DONE]`, added when the model leaves it out. There is no limit on waiting; opencode's configuration sets its own.

## SurfSense's tools

`POST /agent/tools/workspaces/{workspace_id}` ([`tool_endpoint/`](../../surfsense_local/backend/modules/agent/tool_endpoint/)) answers opencode's MCP client: MCP `2025-11-25` over Streamable HTTP, stateless and JSON only, written without an MCP library. It answers `initialize`, `tools/list`, `tools/call` and `ping`, and `202` to a notification. It refuses a request without the launch key with `401`, one carrying an `Origin` header, as a web page's does, with `403`, another protocol version with `400`, a workspace that does not exist with `404`, and `GET` with `405`. The workspace in the path scopes every tool, because a tool call names neither its folder nor its session.

| Tool, as the model sees it | Takes | Does |
|---|---|---|
| `surfsense_search_sources` | `query` | the chat's own `retrieve()` over the workspace's ready files and notes, never artifacts; up to 5 passages, each as `<passage cite="[<chunk id>]" source="sources/<file>" lines="<a>-<b>">`, the lines being that file's |
| `surfsense_create_artifact` | `format`, one of Studio's formats except `docx` and `pdf`; `source_ids`, the numbers at the end of the source files' names; `instructions`, at most 2,000 characters | Studio's own `create_artifact_job()`, which returns at once with the artifact pending. Asked for `docx` or `pdf`, it refuses and names `surfsense_render_document`, because Studio's draft keeps no script to edit |
| `surfsense_render_document` | `title`; `format`, `docx` or `pdf`; `script`; `artifact_id`, to make the next version of; `images`, names from `surfsense_list_images` | runs the script as a new version in Studio and waits for it ([below](#documents-the-agent-makes)) |
| `surfsense_read_document` | `artifact_id`, of any version | the newest version's number, artifact id, title, format, status, the images it places and its script |
| `surfsense_list_images` | `source_ids` | each source's figures, one line each: its name, size in pixels, page and caption when known, and its copy under `sources/figures/` to open with `read`; or that the source has none, is not in this workspace, or has its figures being extracted, which queues the figures-only pass ([documents](documents.md#figures)) |

The schemas are flat, in a fixed order, and the same on every turn, and a test pins them. A call the tool cannot carry out comes back as a tool error the model reads: no query, no sources named, Studio's own reason such as "Needs a chat model", or a search before onboarding has chosen an embedder or while its files are missing, which points the model at `grep`. A source's own text loses any `passage` tag, so it cannot make up a label. A tool runs in one transaction off the event loop, except a tool that waits on another process (`waits` on [`tool.py`](../../surfsense_local/backend/modules/agent/tool_endpoint/tool.py)), which commits its own short transactions so the write lock never stays held while it waits.

Before each turn the API adds the tools to the turn's working folder with opencode's `POST /mcp?directory=…`: the server `surfsense`, the workspace's URL, the launch key as a header, OAuth off, and a call timeout of 200 seconds, where a call would otherwise get the MCP SDK's 60 ([`registration.py`](../../surfsense_local/backend/modules/agent/tool_endpoint/registration.py)). opencode keeps it in memory for that folder alone and drops it when it reloads, so it is added on every turn, and nothing is written to `opencode.json`, which every folder shares. opencode then lists the tools and names them `surfsense_<tool>`. When it cannot reach them, the turn runs with its own tools and the API logs why. The chat panel shows their steps as "Searched the sources for …", "Started … in Studio", "Created *Title* v1", "Read the script behind a document" and "Looked for images in 2 sources".

## Documents the agent makes

[`render_document.py`](../../surfsense_local/backend/modules/agent/tool_endpoint/render_document.py) gives each call one deadline when it starts, 190 seconds, 10 inside the registration's timeout, so opencode never reports a bare timeout for a version that was made:

1. **Create.** Studio's script-documents service makes the version in one short transaction: v1 of a new document, or the next version of the one `artifact_id` names, and queues Studio's job to run it ([studio](studio.md#script-documents)). A refusal, such as an image name the workspace does not hold, comes back as a tool error.
2. **Wait.** Up to 150 seconds, within the deadline, it looks at the version's status every half second, each look its own committed read; a look that finds the database locked rolls back and tries again on the next ([`job_outcome.py`](../../surfsense_local/backend/modules/agent/tool_endpoint/job_outcome.py)).
3. **Ready.** The result starts with `Rendered artifact <id>, version <n>: <title>` ([`rendered_label.py`](../../surfsense_local/backend/modules/agent/tool_endpoint/rendered_label.py)), then the page count of a PDF or the paragraph count of a Word file, the first 1,500 characters of its text, and the page previews to open with `read`, or why there are none. A Word version's list adds that Word previews leave out headers and footers.
4. **Failed.** A tool error with the run's error and the traceback's last lines, the `artifact_id` to render the fix from, and the stop rule: "If this is your third failed run for this request, stop and tell the user what failed." Studio does not retry a failed script document, so the version stays failed and the fix is the next version.
5. **Not done in time.** A version still being made, behind other Studio work, comes back as a plain result saying it appears in Studio when ready and must not be rendered again. A cancelled or deleted version is a tool error without the stop rule.

The script, not the file, is what a version keeps, so the next edit reads it with `surfsense_read_document`, changes it and renders it again. Another format, such as a PDF of a Word document, is a new document at v1.

## Previews

`previews_for()` ([`previews/`](../../surfsense_local/backend/modules/agent/previews/)) draws up to four pages of a ready version as PNGs 1,000 pixels wide, at most 4,000 high, into `outputs/previews/<artifact id>-v<n>/`, with pypdfium2 under one lock for the API. A page that would come out under 100 pixels on a side is skipped and named in the reason. It is called after the version's files are read and the transaction committed, with the time the call has left.

- **PDF:** the file's own pages.
- **Word:** the app has no Word converter, so Electron prints the file. The API queues a request and waits up to 30 seconds, or what the call has left, and skips the preview below 3 seconds. Electron polls the routes below every 2 seconds, opens the frontend's snapshot page ([`docx-snapshot.html`](../../surfsense_local/frontend/docx-snapshot.html)) in a hidden window with the file's URL, lays it out with docx-preview, the in-app viewer's library, and prints pages 1 to 4 with `printToPDF`; pypdfium2 then draws that PDF. The pages show the document as the app's viewer lays it out, not as Microsoft Word does, and without headers and footers, which docx-preview places in a page box that print pagination replaces.
- **No Electron**, as in the Docker stack and the tests: the snapshot service counts Electron gone after 60 seconds without a poll, and a Word version gets no pages and the reason.

The Word snapshot routes, mounted only beside an opencode ([`previews/router.py`](../../surfsense_local/backend/modules/agent/previews/router.py)):

| Method | Path | Does |
|---|---|---|
| `GET` | `/agent/previews/docx-snapshots/next` | takes the oldest waiting request: its id and the artifact's `files/primary` URL; `204` when none |
| `POST` | `/agent/previews/docx-snapshots/{request_id}/pdf` | the printed PDF; `413` over 50 MB, `422` for a body that is not a PDF, `404` when no one waits for it |
| `POST` | `/agent/previews/docx-snapshots/{request_id}/failure` | why it could not be printed, at most 500 characters |

Each refuses a caller with an `Origin` header, and one without `Authorization: Bearer <key>`, the key Electron made at boot and passed to the API as `SURFSENSE_LOCAL_DOCX_SNAPSHOT_KEY` ([`snapshot_key.py`](../../surfsense_local/backend/modules/agent/previews/snapshot_key.py)), because any process on the machine can reach loopback.

Electron's side ([`docx-snapshot/`](../../surfsense_local/electron/src/main/docx-snapshot/)) takes the next request at once after taking one, prints up to three at a time, gives each print 25 seconds, under the API's 30, and each call to the API 10. A PDF the API refuses is reported as the request's failure. The document is untrusted, since a source can steer the script that wrote it, so the hidden window runs sandboxed with no preload, in its own in-memory session whose requests may reach only the page's own files and the one Word file, and it never navigates. The page's policy allows only its own script, inline styles, data-URL images and fonts, and connections to loopback; docx-preview renders no altChunk, whose HTML it would put in an unsandboxed frame. A page whose script did not start is reported as such, with the window's first console error.

## A turn

The thread routes in [chat](chat.md#agent-threads) hand an agent thread to `agent_threads/`:

1. The workspace's sources folder is brought in line, opencode is made ready, and the workspace's tools are added to its folder.
2. The folder's event stream is opened before the message is sent, so no event of the turn is missed. The message goes with `prompt_async`, naming the selected model, so a thread keeps working after a model change.
3. Events for the thread's session become the chat's frames, plus `agent-step`, `permission-request` and `permission-replied` ([`turn_frames.py`](../../surfsense_local/backend/modules/agent/agent_threads/turn_frames.py)). A completed `surfsense_render_document` step carries `artifact: {id, title, version}`, read from its result's first line, which only a ready version gets; it is null while the call runs, when the script failed and when the version was not ready in time ([`steps.py`](../../surfsense_local/backend/modules/agent/agent_threads/steps.py)). The screen then reads "Created *Title* v1" or "Updated *Title* to v2", and a click opens that version in Studio.
4. A stream silent for 20 seconds, twice opencode's heartbeat, is reopened, and so is one that drops; after a reopen, an idle session ends the turn. Twenty failures in a row end it with an error.
5. On `session.idle`, `completed` carries the reply as opencode stored it: the text of every assistant message opencode wrote for this turn, joined. A label one of the session's searches returned becomes `[citation:<chunk id>]` through the chat's own `resolve_citations()`, and any other bracketed number is dropped ([`citations.py`](../../surfsense_local/backend/modules/agent/agent_threads/citations.py)). A `citations` frame comes first when the reply cites anything.
6. When the client hangs up before that, the session's turn is aborted.

**Compaction.** When the window fills, opencode compacts the session mid-turn: a user message holding a compaction part, a summary it writes for itself, then a user message that carries the turn on. [`compaction.py`](../../surfsense_local/backend/modules/agent/agent_threads/compaction.py) tells them apart, so they fold into the turn they happened in: the summary is never streamed as the reply nor joined into the stored one, and the carrying-on message opens no new turn when the thread is read back. opencode's `ContextOverflowError` is not shown, since opencode compacts and carries on from it. A summary that fails ends the turn with one error frame, and one that failed because even the summary was too long says "The conversation is too long to continue here; start a new thread."

## Approvals

The agent has no shell, so it asks for no command. opencode still asks for a permission left at its default, such as `doom_loop` when the same tool call with the same input comes a third time in a row. The request reaches the thread as `permission-request`. The screen shows the oldest waiting one in an alert dialog, with Deny and Allow once, and Esc answering Deny. The answer goes to `POST /chat/threads/{thread_id}/permissions/{request_id}`, which passes `once` or `reject` to opencode. SurfSense never answers `always`. opencode rejects every other request waiting in the same session when one is rejected, and the dialog says so when others wait.

## Network

opencode needs no host beyond loopback: its model is the model endpoint, and its tools are its own and SurfSense's, on the API's port. Its environment is built from a few system variables rather than inherited. It sets `OPENCODE_DISABLE_MODELS_FETCH`, `OPENCODE_DISABLE_SHARE`, `OPENCODE_DISABLE_LSP_DOWNLOAD`, `OPENCODE_DISABLE_AUTOUPDATE`, `OPENCODE_DISABLE_DEFAULT_PLUGINS`, `OPENCODE_PURE`, `OPENCODE_DISABLE_PROJECT_CONFIG`, `OPENCODE_DISABLE_EXTERNAL_SKILLS` and `OPENCODE_DISABLE_CLAUDE_CODE`. Its proxy variables point at `127.0.0.1:9`, where nothing listens, with loopback exempted, so a fetch this misses fails rather than leaving the machine. The npm install opencode would otherwise run at startup is skipped: its config folder holds an empty `node_modules` and a lockfile naming the package. ripgrep is the shipped one, first on its `PATH`. Settings › Network gains nothing: opencode is never a destination, and a remote model's host is checked as its connection's.

A document script is another matter: it runs in the Studio worker's runner, which gives it an environment of a few system variables and no secrets but does not stop it opening connections ([ADR 0039](../adr/0039-document-scripts-run-without-approval.md), [studio](studio.md#script-documents)).

## Tests

- **Backend:** [`tests/integration/agent/`](../../surfsense_local/backend/tests/integration/agent/) and [`tests/unit/agent/`](../../surfsense_local/backend/tests/unit/agent/). The client, readiness and thread tests start the staged opencode against a scripted model, and the thread tests also run the real API on a port. The tool endpoint tests drive the app in-process, as opencode's MCP client calls it. They skip where `pnpm build:opencode` has not staged a build. Each builds the app as Electron starts it beside an opencode; `test_routes_without_opencode.py` builds it without one. `test_document_flow.py` plays a whole document flow through the tool endpoint with no model: a logo's figure, Word v1 with the logo and a chart, its script read back, v2, and a PDF whose previews are drawn. `test_documents_skill.py` runs the skill's examples through the real runner, and `test_compacted_turns.py` reads compacted sessions back.
- **Live:** [`tests/live/`](../../surfsense_local/backend/tests/live/) drives the real path against Claude Sonnet on a spend budget, skipped unless asked for ([07-dev-setup](../proposals/file-agent/07-dev-setup.md#live-tests)).
- **Electron:** the sidecar tests in [`electron/src/main/sidecars/`](../../surfsense_local/electron/src/main/sidecars/), the snapshot poller, session and page-answer tests in `electron/src/main/docx-snapshot/`, and the pins and switch tests in `electron/scripts/opencode/`.
- **Frontend:** [`features/agent/agent-thread.test.tsx`](../../surfsense_local/frontend/src/features/agent/agent-thread.test.tsx), on the real dashboard against a stream that waits for the test's answer, and the snapshot page's layout, altChunk and policy tests in `features/docx-snapshot/`.

## Known gaps

- No model is on the tested list, and no agent test exists to put one there; only the developer switch lets a model in.
- A turn refused because the selected model cannot run the agent shows as an error with Retry; the composer does not offer a new thread, as the [proposal](../proposals/agent/01-which-engine.md#when-a-thread-gets-its-engine) has it.
- The model endpoint neither simplifies tool schemas to what llama.cpp's grammar takes nor turns a tool call a model writes as text into a real one, so small local models stall where a remote one would not.
- A file the agent writes to `outputs/` with its own tools does not become an artifact; only `surfsense_render_document` makes one.
- A Studio job the agent starts with `surfsense_create_artifact` runs on the same local model as the agent, so the agent's next step waits behind it.
- An artifact the agent starts or renders records neither the thread nor the step that made it: the tool call reaches SurfSense without either.
- Sources unticked in the sources panel still reach the agent: `sources/` holds every ready source and `surfsense_search_sources` searches them all, where a chat thread searches only the ticked ones. The ticks can change with each message, while every thread of a workspace shares one `sources/`.
- A passage's label is its chunk id, a number of several digits, which a small local model copies less reliably than a chat answer's `[1]` to `[5]`. A mistyped label is dropped, so the citation is lost rather than wrong. Nothing has measured how many are lost.
- A bracketed number the agent writes that no search returned is dropped from the stored reply but not from the streamed one, so the two differ. In a live run Claude cited files it had read without searching by the `[n]` at the end of their names, as labels, and the saved reply lost them.
- Bringing `sources/` in line reads every ready source's text from the database before each turn, to compare it with the files, so a workspace with many large sources pays for that on every turn.
- A configuration rewrite, which a change of model, window or image input causes, ends every running agent turn in every workspace.
- Opening the first agent thread waits for opencode to start and for a local model to load, up to a minute, with nothing on screen but the thread being created.
- When SurfSense's data folder sits inside a git repository, such as a home folder kept in git, opencode counts the repository's root as its project. Nothing detects it.
- No test runs opencode with every connection beyond loopback refused to check that it opens none.
- No signed installer has carried opencode: a notarized build on macOS and a signed build under Defender on Windows are untried. It adds about 180 MB unpacked.
- On macOS and Linux, opencode checks an absolute path as written, so its own allow for its tool-output folder also matches a path that climbs out of it with `..`. The skills folder's allow has a `..` deny after it; the tool-output folder's cannot, since opencode adds that allow after SurfSense's rules. Windows normalises the path first.
- Every page image the agent opens stays in its context for the rest of the thread, and Anthropic's OpenAI-compatible API reports no prompt caching, so each request bills them again: by the demo's third turn each request carried 8 page images and about 39,000 input tokens.
- claude-sonnet-5-5's window is the 1,000,000 tokens the catalog records, not confirmed against Anthropic's OpenAI-compatible endpoint. No live run has come near it; if the real window is smaller, a request fails on it before compaction starts.
- Word previews leave out headers and footers, and lay a document out as docx-preview does, which can differ from Word. The agent is told the first.
- The Word preview path through a real Electron window has no automated test; it was checked by hand, and the live tests print Word with LibreOffice behind the same routes.
- A fourth Word snapshot requested while three print waits for a free print, and the API's 30 seconds start when the request is queued, so it can time out before Electron answers.
