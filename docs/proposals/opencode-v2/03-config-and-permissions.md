# Configuration and permissions

[`opencode_config.py`](../../../surfsense_local/backend/modules/agent/opencode_config.py) writes 2.x's native shape. 1.x syntax still loads, but mixing the two inside one agent or provider is not recognised, and the native keys are the ones 2.x documents ([migration guide](https://github.com/anomalyco/opencode/blob/v2.1.2/services/www/src/docs/content/migrate-v1.mdx)).

## Keys

| 1.x | 2.x |
|---|---|
| `provider.surfsense.npm` `@ai-sdk/openai-compatible` / `@ai-sdk/openai` | `providers.surfsense.package` `@opencode/ai/providers/openai-compatible` / `@opencode/ai/providers/openai`, built into the binary ([`core/src/aisdk-native.ts`](https://github.com/anomalyco/opencode/blob/v2.1.2/packages/core/src/aisdk-native.ts)) |
| `options.{baseURL, apiKey, headerTimeout, chunkTimeout}` | `settings.{…}` |
| a model's `tool_call`, `modalities`, `attachment` | `capabilities.{tools, input, output}`. `attachment` is ignored, and a model 2.x does not know is assumed to read images, so a text-only model declares `input: ["text"]` |
| `limit` | unchanged |
| `compaction.reserved` | `compaction.buffer`; `keep.tokens` is set too, since its default of 15,000 is half a 32,768 window |
| `small_model` | `agents.title.model` |
| `agent.surfsense.{prompt, permission}` | `agents.surfsense.system`; rules at the top level apply to every agent |
| `permission` map | `permissions`, an ordered list (below) |
| `enabled_providers` | `policies`: `provider.use` denied for `*`, allowed for `surfsense` |
| `snapshot`, `autoupdate`, `skills.paths` | `snapshots`, `update`, `skills: [...]` |
| `todowrite`, on by default | `experimental.todo: true`; off by default in 2.x, and an experimental key that a later release may change. Its description is 512 characters, against 2,012 in 1.x |
| `OPENCODE_DISABLE_DEFAULT_PLUGINS`, `OPENCODE_PURE` | `plugins: ["-opencode.provider.ollama", "-opencode.provider.lmstudio", "-opencode.provider.vllm", "-opencode.skill", "-opencode.tools"]` |

The minus-list matters: without the first three, 2.x probes Ollama, LM Studio and vLLM on loopback every 30 s from a folder's first use; without the last two it lists its own `opencode` and `report` skills and tells the model to use `execute`. With all five the system prompt fell from 2,412 to 1,546 characters. An unknown id is ignored silently.

## Permissions

2.x matches rules in order and the last that matches wins; no match asks ([`core/src/permission.ts`](https://github.com/anomalyco/opencode/blob/v2.1.2/packages/core/src/permission.ts)). `*` matches any text including `/`, case-insensitively on Windows ([`core/src/util/wildcard.ts`](https://github.com/anomalyco/opencode/blob/v2.1.2/packages/core/src/util/wildcard.ts)). Actions are renamed: `bash` → `shell`, `task` → `subagent`, `write` and `patch` → `edit`. `doom_loop` is gone.

An edit's resource is now relative to the session's folder when the path is inside it (`outputs/a.md`) and absolute outside it ([`core/src/file-access.ts`](https://github.com/anomalyco/opencode/blob/v2.1.2/packages/core/src/file-access.ts)), so today's `*/agent/threads/*/outputs/*` would match nothing. The rules:

| Action | Resource | Effect |
|---|---|---|
| `shell`, `execute`, `subagent`, `question`, `webfetch`, `websearch` | `*` | deny |
| `edit` | `*` | deny |
| `edit` | `outputs/*` | allow |
| `edit` | `*AGENTS.md`, `*agents.md`, `*Agents.md`, `.opencode/*`, `*/.opencode/*` | deny |
| `external_directory` | `*` | deny |
| `external_directory` | `<skills>/*`, `<data>/opencode/tool-output/*` | allow |
| `skill` | `*` | deny |
| `skill` | each SurfSense skill | allow |

- 2.x allows `external_directory` by default, and no longer allows its own tool-output folder by itself, so both are explicit.
- `CLAUDE.md` and `CONTEXT.md` drop out: 2.x reads only `AGENTS.md`. `*/../*` drops out: paths are normalised before matching.
- Measured on macOS and Windows: writes land only under `outputs/`; `sources/`, `sources/Lib/outputs/`, `AGENTS.md` in any case and `.opencode/` are refused; reads outside the folder are refused except the skills and tool-output folders.
- With a git repository above the thread folder, 2.x takes the repository as the project and lets `read`, `glob` and `grep` reach sibling folders unchecked. [`repo_fence.py`](../../../surfsense_local/backend/modules/agent/thread_folder/repo_fence.py)'s `.git` file keeps the project at the thread folder on both systems.

**Policies** repeat the denies for `shell`, `execute`, `webfetch`, `websearch` and `subagent` as `tool.use`. A policy cannot be lifted by a session rule or a saved approval; it does not hide a tool, which only a permission deny does, so both are written.

## Verification

2.x fails open. An unknown key is dropped without a word; one invalid value drops the object holding it, so a single malformed rule inside the agent removes the agent and every prompt fails with "Agent not found"; the only trace is a warning in opencode's log. After each write the backend reads `GET /api/config` with the folder and compares the file's normalised entry with what it wrote, and refuses a turn on any difference. `GET /api/agent/surfsense` and `/api/provider/surfsense` are not used for this: on a folder's first use they answer 404 for about half a second even for a good file.
