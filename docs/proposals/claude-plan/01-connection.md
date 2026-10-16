# The Claude plan connection

> A `claude_plan` row in `provider_connections` holds no credential: it names the Claude Code binary SurfSense found and the account Claude Code reported. Every run of Claude Code, chat or agent, is launched by one function with one fixed set of options, so no caller can forget the path, the proxy or the isolation.

Part of [Use your Claude plan](README.md).

## Finding Claude Code

`subscriptions/claude/locate.py` returns the first `claude` it finds that can run: each directory on the API's own `PATH`, then the places Claude Code's installers put it ([setup](https://code.claude.com/docs/en/setup)), which a GUI app's `PATH` usually lacks on macOS and Linux:

| System | Searched after `PATH` |
|---|---|
| macOS, Linux | `~/.local/bin/claude` (native installer), `~/.claude/local/claude` (older local install), `~/.npm-global/bin/claude`, `~/.volta/bin/claude`, the newest `~/.nvm/versions/node/*/bin/claude`, `/opt/homebrew/bin/claude` and `/usr/local/bin/claude` (Homebrew), `/home/linuxbrew/.linuxbrew/bin/claude` (Linuxbrew), `/usr/bin/claude` (apt, dnf, apk) |
| Windows | `%USERPROFILE%\.local\bin\claude.exe` (native installer), `%LOCALAPPDATA%\Microsoft\WinGet\Links\claude.exe` (WinGet), `%APPDATA%\npm\node_modules\@anthropic-ai\claude-code\bin\claude.exe` (npm) |

On Windows only a `claude.exe` counts: npm's `claude.cmd` launcher on `PATH` is passed over for the executable behind it, since the Agent SDK refuses a `.cmd`. On macOS and Linux a file without the executable bit is passed over. The binary is found again before each run, so one that moved or was reinstalled elsewhere is still used.

## Status

`subscriptions/claude/status.py` runs the binary twice, each with a 15-second timeout, the [launch environment](#launching-a-run), and on Windows `CREATE_NO_WINDOW`, so a check from the windowless API never flashes a console. A run that fails, times out or prints something unreadable counts as no answer: no version is `too_old`, no sign-in is `signed_out`.

- `claude --version`, read as `major.minor.patch`. Below `MIN_VERSION`, the lowest version the contract test passed on, the state is `too_old`.
- `claude auth status`, which prints JSON. `loggedIn: false` is `signed_out`; `authMethod` other than `"claude.ai"` is `signed_out` too, since a Console login is not a plan. Otherwise the state is `ready`, with `email`, `orgName` and `subscriptionType`.

| State | Meaning | Dialog says |
|---|---|---|
| `not_installed` | no binary found | install Claude Code |
| `too_old` | version below `MIN_VERSION` | update Claude Code |
| `signed_out` | no claude.ai login | run `claude` and sign in |
| `ready` | signed in to a plan | connected as `email` · plan |

The status is read when the dialog opens, on **Check again**, and before each run that starts a new Claude Code process. Nothing polls.

## The connection

- `ProviderConnection.auth_kind` gains `'claude_plan'`, the only schema change. Revision `0031` widens the `CHECK` in [`models.py`](../../../surfsense_local/backend/modules/llm/models.py) by rebuilding the table from its own stored definition, keeping every remote selection aside and putting it back, since dropping the table cascades through `selected_models.connection_id`. `api_key_ciphertext` and `oauth_ciphertext` stay `NULL`, `provider` stays `openai_compatible` read as "remote connection" ([ADR 0038](../../adr/0038-chatgpt-plans-sign-in-through-openai-not-codex.md)), `base_url` is `https://api.anthropic.com`, `catalog_provider` is `anthropic`.
- Nothing Claude Code reports is stored: the binary's path, its version, the account's email and plan, and the [model list](#models) are read live. Measured on macOS, a status check took 0.13 s after the first (0.58 s) and the model list 0.34 to 0.42 s, and a stored copy would go stale the moment the user signs out or switches account in Claude Code.
- [`serves.py`](../../../surfsense_local/backend/modules/llm/connections/serves.py) gains `"claude_plan": (TEXT_GEN,)` in step 2 of the [build order](README.md#build-order) and the agent's slot in step 4.
- One connection per install. A second **Use your Claude plan** opens the existing one.
- Deleting the connection deletes the row. Claude Code's login is untouched; signing out of Claude is the user's, in Claude Code.

## Routes

Mounted beside the ChatGPT routes, before the connections router:

| Route | Does |
|---|---|
| `GET /llm/connections/claude` | the status, the `serves` a plan would fill, and `hosts` still to allow (`api.anthropic.com` until allowed) |
| `POST /llm/connections/claude/check` | reads the status again and, when a connection exists, updates its hints |
| `POST /llm/connections/claude` | creates the connection; `409` when one exists, `422` with the state when not `ready`; refused with `egress_disabled` until `host:api.anthropic.com` is on |

Listing, renaming and deleting go through the existing connection routes. `_read` in the connections router reports the email and plan for a `claude_plan` row as it reports `signed_in` and `email` for a ChatGPT one.

## Models

`client.get_server_info()["models"]` lists what the account's Claude Code offers: `value` (`opus`, `sonnet`, `haiku`, `claude-fable-5-1[1m]`), `displayName`, `resolvedModel` and supported effort levels. `default` is dropped, since it only names another entry. The list is read live, and may be held in the API's memory for a few minutes; `connection_models` in [`listing.py`](../../../surfsense_local/backend/modules/llm/connections/listing.py) returns it as `DiscoveredModel`s with source `declared`. A model is selected by its `value`, the alias Claude Code resolves to the current release.

## Launching a run

`subscriptions/claude/launch.py` is the only code that builds `ClaudeAgentOptions`. Chat and the agent pass what differs (tools, MCP servers, hooks, prompt, `cwd`); `launch.py` adds, and callers cannot override:

| Option | Value | Why |
|---|---|---|
| `cli_path` | the located binary | with none set, the SDK runs its bundled copy before `PATH` |
| `setting_sources` | `[]` | the user's `~/.claude` settings, hooks, CLAUDE.md, skills and plugins never apply |
| `strict_mcp_config` | `True` | only the MCP servers SurfSense passes |
| `verbatim_prompts` | `True` | `@path` and `/command` in a user's message are text, not a file read or a command |
| `permission_mode` | `"default"` | 2.1.301 defaults to `auto`, which approves tools before `can_use_tool` runs |
| `env["ANTHROPIC_API_KEY"]` | `""` | a key in the API's environment silently replaces the plan |
| `env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"]` | `"1"` | no telemetry or error-reporting hosts |
| `env["HTTPS_PROXY"]`, `env["HTTP_PROXY"]` | SurfSense's proxy | [Network](#network) |
| `env["NO_PROXY"]` | `127.0.0.1,localhost` | the agent's MCP servers on loopback |

`CLAUDE_CONFIG_DIR` is not set: Claude Code's login lives under the user's own config directory, and a separate one signs out ([Measurements](README.md#measurements)).

## Network

Claude Code makes its own HTTPS calls, which no `egress.require()` in the API would see. So every run's proxy variables point at the API's [plugin proxy](../../../surfsense_local/backend/modules/agent/plugin_proxy/), which tunnels `CONNECT api.anthropic.com:443` only when `host:api.anthropic.com` is enabled and refuses every other host. Measured, Claude Code honours `HTTPS_PROXY` and, with non-essential traffic off, asks for nothing but `api.anthropic.com`.

A refused tunnel does not fail the request: Claude Code retries up to 10 times, the first after about a second, reporting each as a `system` message of subtype `api_retry`. The proxy records each refusal against the run it was opened for, and on the first `api_retry` after one the run is interrupted and ends with `egress_disabled` naming `api.anthropic.com`, the same refusal every other model call gives ([egress](../../architecture/egress.md#asking-for-consent)).

Electron starts the plugin proxy only where opencode is staged. Whether that becomes "always" or the chat path gets a proxy of its own is decided in step 2.

## Errors

`subscriptions/claude/errors.py` maps what Claude Code reports onto the existing provider errors in [`openai_responses/errors.py`](../../../surfsense_local/backend/modules/llm/providers/openai_responses/errors.py), which move to a provider-neutral module in the same change:

| Claude Code reports | Raised | The user sees |
|---|---|---|
| `AssistantMessage.error == "authentication_failed"` | `SignInRequiredError` | `subscription_sign_in`: run `claude` and sign in |
| `RateLimitEvent` with `status` not `allowed` | `PlanLimitError`, with `resetsAt` | `subscription_limit`, with the reset time |
| binary missing or not executable at launch | `SignInRequiredError` with `reason: not_installed` | the connection's not-found state |
| version below `MIN_VERSION` at launch | the same, `reason: too_old` | update Claude Code |
| refused tunnel then `api_retry` | `EgressDeniedError` | the egress prompt |
| any other `ResultMessage.is_error` | `ProviderError` | `unknown` |

[`chat/errors.py`](../../../surfsense_local/backend/modules/chat/errors.py), the model route's failure frames and the agent's error kinds already map the first two.

## Packaging

The Python `claude-agent-sdk` wheel carries Claude Code as `claude_agent_sdk/_bundled/claude`, 241 MB, and the SDK prefers it over `PATH` whenever `cli_path` is unset. SurfSense ships none:

- [`bundling/api.spec`](../../../surfsense_local/backend/bundling/api.spec) excludes `claude_agent_sdk/_bundled`.
- A packaging test fails when any `claude` binary is inside the frozen API.
- `launch.py` refuses to build options without a located `cli_path`, so a development venv, which does carry `_bundled`, behaves as the packaged app does.

`claude-agent-sdk` is pinned exactly in [`pyproject.toml`](../../../surfsense_local/backend/pyproject.toml): it and the user's Claude Code move independently, and the contract test runs the pinned SDK against the oldest and newest Claude Code accepted.
