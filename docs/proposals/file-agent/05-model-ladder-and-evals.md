---
status: proposed
code:
  - surfsense_local/backend/modules/llm/providers/anthropic_messages/
  - surfsense_local/backend/modules/llm/providers/openai_compatible/
  - surfsense_local/backend/modules/llm/connections/wire.py
  - surfsense_local/backend/modules/llm/resolution.py
  - surfsense_local/backend/modules/llm/capability/
  - surfsense_local/backend/modules/llm/spend/
  - surfsense_local/backend/modules/llm/catalog/remote/manifest/schema.py
  - surfsense_local/backend/scripts/remote_manifest/translate.py
  - surfsense_local/backend/modules/agent/model_endpoint/
  - surfsense_local/backend/modules/agent/launch_key.py
  - surfsense_local/backend/modules/agent/engine_choice.py
  - surfsense_local/backend/modules/agent/opencode_config.py
  - surfsense_local/backend/modules/agent/agent_threads/turn.py
  - surfsense_local/backend/modules/agent/agent_threads/active_turns.py
  - surfsense_local/backend/modules/agent/tool_endpoint/create_artifact.py
  - surfsense_local/backend/modules/artifacts/service.py
  - surfsense_local/backend/modules/run_reports/
  - surfsense_local/backend/modules/llm/fit/
  - surfsense_local/backend/alembic/versions/<next>_capability_and_spend.py
  - surfsense_local/backend/scripts/job_eval/
  - surfsense_local/backend/scripts/run_job_eval.py
  - surfsense_local/backend/scripts/local_manifest/llamacpp/refresh.py
  - surfsense_local/electron/scripts/fetch-llamacpp.mjs
  - surfsense_local/electron/scripts/opencode/enabled.mjs
  - surfsense_local/frontend/src/features/models/
  - surfsense_local/frontend/src/features/onboarding/model-step/
  - surfsense_local/frontend/src/features/studio/
  - .github/workflows/model-evals.yml
  - docs/architecture/model-capabilities.md
---

# Model ladder and evals

> SurfSense learns what each model can do by measuring it, never by its size or its prompt tier. Claude reaches the app through Anthropic's own Messages API, with prompt caching, enforced schemas and a spend ledger, so the first column of the matrix measures Claude rather than a compatibility layer. A job × model matrix, run at the app's own settings with the skills project's graders, measures the jobs and the free-form file work users are offered, walks down from Opus to a 4B local model, and holds one OpenAI and one Gemini column beside Claude. Each result lands in a reviewed capability manifest shipped with the app. One function, `capability_of()`, reads that manifest and returns the capability that the product shape in [06](06-product-shape.md) shows: which engine new threads get, how each job runs, which Studio formats and edit rungs are offered, whether the agent may ask for the shell, and the window it needs. An unmeasured model keeps everything it has today, labelled "not measured"; only a measured failure takes something away.

## Today

Everything in this section was checked in the repo on 2026-10-03 unless marked otherwise.

**Claude has no native path.**
- `resolve_generation()` builds an `OpenAICompatibleChatProvider` for every remote row that is not a ChatGPT sign-in ([`resolution.py`](../../../surfsense_local/backend/modules/llm/resolution.py)). For `api.anthropic.com`, `key_headers()` sends `x-api-key` and `anthropic-version: 2023-06-01` to `/chat/completions`, Anthropic's OpenAI compatibility layer ([`key_headers.py`](../../../surfsense_local/backend/modules/llm/connections/key_headers.py)). Anthropic's page on that layer says `response_format` and `strict` are ignored, prompt caching is unsupported, thinking is not returned, and the layer is "not considered a long-term or production-ready solution" ([OpenAI SDK compatibility](https://platform.claude.com/docs/en/api/openai-sdk), read by research report I6 on 2026-10-03).
- The agent's model endpoint forwards every model to `{base}/chat/completions` ([`model_address.py`](../../../surfsense_local/backend/modules/agent/model_endpoint/model_address.py)). It merges every system message into one string and defuses chat-template tokens ([`request_shaping.py`](../../../surfsense_local/backend/modules/agent/model_endpoint/request_shaping.py)). Its relay always closes a stream with `data: [DONE]` and reports a broken stream as an OpenAI-shaped `{"error": {"message": …}}` frame ([`relay.py`](../../../surfsense_local/backend/modules/agent/model_endpoint/relay.py) `_frames`). Every error the route raises itself (409 `model_not_selected`, 403 `egress_disabled`, 409 `model_busy`) goes through `error_reply()`, whose docstring says "Errors as opencode's OpenAI-compatible provider reads them" ([`error_replies.py`](../../../surfsense_local/backend/modules/agent/model_endpoint/error_replies.py), [`router.py`](../../../surfsense_local/backend/modules/agent/model_endpoint/router.py)).
- The remote manifest's `anthropic` provider has `connect.base_url = "https://api.anthropic.com/v1"`, and every Claude model has `call: null` ([`models.json`](../../../surfsense_local/backend/modules/llm/catalog/remote/manifest/models.json)). `call` means "How a model is called, when it differs from its provider" ([`schema.py`](../../../surfsense_local/backend/modules/llm/catalog/remote/manifest/schema.py) `Call`). Any non-null `call` without `route: "responses"` makes `call_reason()` answer "Served through the {protocol} protocol, which SurfSense does not speak", and `unusable_reason()` returns that for the row ([`lookup.py`](../../../surfsense_local/backend/modules/llm/catalog/remote/manifest/lookup.py)). `translate.py::_call()` sets `call` only when a model's own `provider.npm` differs from its provider's.
- The manifest carries no prices (`translate.py` drops models.dev's cost fields) and, refreshed on 2026-09-23, no `claude-sonnet-5-5`. It lists `reasoning_options` per model: `effort` (low to max) for Opus 5.5, and only `budget_tokens` (min 1,024) for `claude-haiku-4-5`.
- Claude has no other direct route. The manifest marks `amazon-bedrock` unreachable ("Signs requests with AWS credentials, not an API key"), and `google-vertex` and `google-vertex-anthropic` unreachable ("Needs a Google Cloud sign-in, not an API key"). Claude through OpenRouter or a custom gateway goes over the OpenAI chat wire. The `openai` provider's base URL is `https://api.openai.com/v1`, and the `google` provider's is Gemini's OpenAI-compatible endpoint, `https://generativelanguage.googleapis.com/v1beta/openai`; both are `ready` ([`models.json`](../../../surfsense_local/backend/modules/llm/catalog/remote/manifest/models.json)).
- No path records token usage. Neither the OpenAI-compatible provider nor the agent relay reads a `usage` field (a grep for `usage` and `include_usage` under `providers/` and `model_endpoint/` finds only the ChatGPT plan's usage-limit error).

**The routing signals are an empty list and a size guess.**
- `selected_model_can_run_agent()` returns true only for a name in `TESTED_MODELS`, which is an empty frozenset, or under the developer switch. It never checks the window its own comment cites, nor the connection's `auth_kind`. For a local model it confirms tool calls through `_local_calls_tools()`, which loads the model if it is not resident ([`engine_choice.py`](../../../surfsense_local/backend/modules/agent/engine_choice.py)). Its callers are `chat/router.py` (thread creation) and `agent_threads/turn.py`.
- `classify()` maps a fingerprint to `compact` (< 7B), `capable` (< 100B) or `frontier`, falling back to vendor, line word and loopback ([`classify.py`](../../../surfsense_local/backend/modules/llm/profile/classify.py)). Run on real listing shapes, Claude Sonnet on an Anthropic key gets `capable`, every model on an OpenAI key gets `frontier` (gpt-5-nano included), and an Ollama model with no size in its id gets `frontier` (I6 §b). `SelectedModel.tier` is a synchronous ORM property that calls `classify()` ([`models.py`](../../../surfsense_local/backend/modules/llm/models.py)); `ResolvedGeneration.tier` returns it, and every Studio pipeline and chat's `build_context` read that ([`resolution.py`](../../../surfsense_local/backend/modules/llm/resolution.py)).
- `SelectedModel.settings` is cleared whenever the slot takes another model: "Settings are the model's own; another model starts without them" ([`selection.py`](../../../surfsense_local/backend/modules/llm/selection.py)).
- Studio's `_availability()` is synchronous and gates a format only on whether its model slots are filled ([`artifacts/service.py`](../../../surfsense_local/backend/modules/artifacts/service.py)).

**Almost nothing is measured.**
- The [chat eval](../chat-eval.md) has run only Qwen3 1.7B. Its grounded rate went from 73% to 91% after prompt fixes in local runs that are not published: the files are under `.progress/eval/`, excluded from git (I6 §d). No run exists for Qwen3 4B, any Studio format, the agent, or any frontier model inside SurfSense.
- The agent test is prose in [`01-which-engine.md`](../agent/01-which-engine.md#what-tested-means); its smoke uses only `search_sources` and `create_artifact`, which exist today. [agent](../../architecture/agent.md#known-gaps) lists "no agent test exists". `ENABLED_BY_DEFAULT` is `false`, so no installer stages opencode, and its comment reads "Off until a model passes the agent test (docs/architecture/agent.md); flip the default when one does" ([`enabled.mjs`](../../../surfsense_local/electron/scripts/opencode/enabled.mjs)).
- Studio's Word, PowerPoint, Excel and PDF formats run model-written Python through `exec()` in `execute()` ([`runner.py`](../../../surfsense_local/backend/worker/studio/office/runner.py)). That path has never been measured on any model.
- The skills project's harness (`references/skills_to_improve/tools/eval/`, git-ignored) has code graders proven on negative controls, gates that force a score of 0, a blind LLM grader that counts only after 100% calibration agreement, and `opencode_run.py --model … matrix`. Executors are hard-wired to Haiku (`evalkit.py:100`), every cell is n=1, and acceptance ran on OpenCode 2.0.12, not the bundled 1.18.34 (I3 §d). Its graders validate against `tools/eval/graders/schemas/`, a data copy whose `SOURCE.json` names `original_skills/docx/scripts/office/schemas` as the source and says it is "otherwise byte-identical to the source" (`xsd.py` `SCHEMA_DIR`); [02](02-skills-and-engines.md) re-sources it.

**Retrieval does not scale with the window.**
- Chat retrieves with `retrieve(session, workspace_id, payload.text, document_ids=…)` at `top_k = 5`, whatever the model's window ([`chat/router.py`](../../../surfsense_local/backend/modules/chat/router.py), [`search.py`](../../../surfsense_local/backend/shared/search.py)). Studio grounding is 24,000 characters split across the selection ([`01`](01-sources-and-folders.md)).
- Chat prices each history turn with the generator's `token_count`, one call per turn on every chat turn ([`history.py`](../../../surfsense_local/backend/modules/chat/history.py) `_cost`, [`chat/router.py`](../../../surfsense_local/backend/modules/chat/router.py) `_token_counter`).

**Local runtime limits.**
- The curated chat ladder is Qwen3 0.6B/1.7B/4B/8B/14B/32B and Gemma 3 4B. No chat build has `validated` set; `VALIDATED` in `scripts/local_manifest/llamacpp/refresh.py` is `{}` ([`models.json`](../../../surfsense_local/backend/modules/llm/catalog/local/manifest/models.json)).
- Each install records its `repo`, `revision` and `quantization` in `installs.json`, keyed by the runtime's model id, the first weights file without `.gguf` ([`installs.py`](../../../surfsense_local/backend/modules/llm/catalog/local/installs.py) `InstalledBuild`).
- Windows come from `CONTEXT_RUNGS = (8192, 16384, 32768)` and are fixed at load ([`fit/estimate.py`](../../../surfsense_local/backend/modules/llm/fit/estimate.py)). `plan_load(shape, weights_bytes, budget, live=None)` is pure; the live budget "caps widening only", and it prefers f16 over `q8_0` because a quantized cache needs a working flash-attention kernel, without which llama.cpp "falls back to CPU attention silently" ([`plan_load.py`](../../../surfsense_local/backend/modules/llm/fit/plan_load.py)). The preset writer calls it with the live budget ([`preset.py`](../../../surfsense_local/backend/modules/llm/catalog/local/engines/llamacpp/models_folder/preset.py)). The fit code has no term for recurrent state (a grep for `recurrent`, `ssm`, `mamba` and `deltanet` under `fit/` and `gguf/` finds nothing).
- `selected_model_window()` reads a local window from llama-server, "loading it if it is not resident" ([`model_window.py`](../../../surfsense_local/backend/modules/agent/model_window.py) `_local_window`).
- llama-server runs with `--models-max 1` and `parallel = 1` ([runtime](../../architecture/local-models/runtime.md)). "A Studio job the agent starts runs on the same local model as the agent, so the agent's next step waits behind it" ([agent](../../architecture/agent.md#known-gaps)). `create_artifact.start(session, workspace_id, arguments)` receives no thread id ([`create_artifact.py`](../../../surfsense_local/backend/modules/agent/tool_endpoint/create_artifact.py)).
- llama.cpp is pinned at `b11050` (`BUILD` in [`fetch-llamacpp.mjs`](../../../surfsense_local/electron/scripts/fetch-llamacpp.mjs)). [fit](../../architecture/local-models/fit.md) measured two machines, an RTX 3050 6 GB with a Ryzen 5 9600X and an M2 8 GB; its 16 GB M4 statement is computed from the manifest, not measured.

**What opencode does with Anthropic and with errors** (read in `references/opencode-dev` 1.18.32, two patches behind the pin; re-check on 1.18.34):
- `@ai-sdk/anthropic` is compiled into the binary (`BUNDLED_PROVIDERS`, `provider/provider.ts:113–116`), so it needs no npm install.
- `applyCaching()` in `provider/transform.ts` marks the first two system messages and the last two others with an ephemeral cache mark for any `claude` model. Through `@ai-sdk/openai-compatible` the mark goes out as `cache_control`, which SurfSense's endpoint flattens and the compatibility layer ignores. The same file sends adaptive thinking with effort variants.
- `session/retry.ts` retries an API error up to `RETRY_MAX_RETRIES = 5` times with exponential backoff when the provider marks it retryable, when the status is 5xx, or when its message or response body matches `RETRYABLE_MESSAGE_PATTERNS`. Those include `/429|500|502|503|504|524/`, `/rate limit|rate-limit|rate_limit|too many requests/i`, `/overloaded|…/i`, `/try your request again|retry your request|resource exhausted/i` and `/try again (later|in)|(currently|temporarily) at capacity/i`.

**What the Claude API requires** (Anthropic's [migration guide](https://platform.claude.com/docs/en/about-claude/models/migration-guide), [adaptive thinking](https://platform.claude.com/docs/en/build-with-claude/adaptive-thinking) and [effort](https://platform.claude.com/docs/en/build-with-claude/effort) pages, as cached on 2026-09-25 in the Claude API reference this design was checked against):
- On Opus 5.5, `thinking: {type: "disabled"}` and `budget_tokens` return 400 at every effort, and so does a forced `tool_choice` (`any` or `tool`). Effort defaults to `medium`. On Sonnet 5.5, `disabled` returns 400; `{type: "between_tools"}` turns thinking off at effort `high` or below. Haiku 4.5 takes `budget_tokens` (minimum 1,024) and rejects `effort`.
- Prices per million tokens, input / output / cache read: Opus 5.5 $4 / $20 / $0.20, Sonnet 5.5 $2 / $10 / $0.20, Haiku 4.5 $1 / $5 / $0.10 ([pricing](https://platform.claude.com/docs/en/about-claude/pricing)). A 5-minute cache write costs 1.25× input ([prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)). Haiku 4.5's retirement is "not sooner than" 2026-10-15 (E4 §6).
- The `anthropic` SDK appends `/v1/messages` to its `base_url`, and its default `max_retries = 2` retries 408, 409, 429 and 5xx.

## Decisions

1. **Claude goes through Anthropic's Messages API, in two places.** Chat, titles and Studio get a native provider, `AnthropicMessagesProvider`. opencode gets a SurfSense passthrough route that its own `@ai-sdk/anthropic` provider calls. Keys and egress stay in SurfSense in both cases. *Reason:* the compatibility layer drops caching, schemas and thinking. Every agent step re-bills the whole context, and a frontier baseline taken through it measures the layer, not Claude.
2. **The wire is derived in one place, `connections/wire.py`, from the connection's host and `auth_kind`. The manifest's `call` slot is not used for it.** *Reason:* `call` means "differs from its provider", and any non-null `call` other than `responses` makes `call_reason()` mark the model unusable, so setting it on Claude would remove every Claude model from selection. A new `provider` value is also out: `provider_connections.provider` is checked to `'openai_compatible'`, and changing that CHECK needs a batch rebuild that cascades through `selected_models.connection_id` and deletes every remote selection (the warning in [`0023_connection_sign_in.py`](../../../surfsense_local/backend/alembic/versions/0023_connection_sign_in.py)). `key_headers()` already keys on the host.
3. **The native provider uses the official `anthropic` Python SDK.** *Reason:* the Messages rules on thinking, tool choice and history changed several times in 2026 (on Opus 5.5, `thinking: disabled` and forced `tool_choice` both return 400, and thinking blocks are bound to their conversation; [migration guide](https://platform.claude.com/docs/en/about-claude/models/migration-guide)). An SDK tracks that for the cost of one dependency in the frozen API and worker ([04](04-runtime-and-packs.md) budgets it). The opencode route relays bytes and needs none.
4. **A measured capability profile replaces both `TESTED_MODELS` and the tier as the capability signal; the tier stays only to choose prompt shape.** Profiles live in a reviewed manifest shipped with the app, `modules/llm/capability/manifest/profiles.json`, and are never fetched at runtime. *Reason:* the same rule already holds for both catalogs ([ADR 0014](../../adr/0014-two-tier-model-catalog.md)). With no telemetry ([ADR 0016](../../adr/0016-no-telemetry.md)), evals are the only evidence. This is the product shape the design panel chose, one workspace kind with a measured capability; [06](06-product-shape.md) decides how it appears.
5. **A profile is keyed by path, model, build, window and effort.** The path is the request path the app uses (`anthropic-native`, `anthropic-compat`, `openai-chat:<catalog provider>`, `chatgpt-plan`, `custom`, `llamacpp`). The build is the curated entry's quantization, bits and llama.cpp tag. The window is the smallest one measured. *Reason:* the same Claude differs by path, a 4-bit file is not the FP16 one Featherless serves, and a 4B at 16K cannot run opencode at all.
6. **The capability is derived in code from the measurements, with thresholds as constants.** *Reason:* a threshold can then move without re-measuring, the property [selection](../../architecture/local-models/selection.md#prompt-tiers) keeps for the tier.
7. **An unmeasured model keeps today's behaviour, labelled "not measured", and loses something only on a measured failure.** Its threads use the chat engine; jobs that ship a workflow run as workflows, except a job whose catalogue entry needs a passing row ([06](06-product-shape.md)'s `needs_passing_row`, today `contract-redline`), which waits for one; every format offered today stays offered. The agent and job threads are offered as untested after one confirmation per model, given confirmed tool calls, a window at or above the floor and a route that carries tools; [06](06-product-shape.md) decides where that confirmation sits. *Reason:* agent quality collapses below the 27–35B tier (AgentFloor, BFCL; E4 §2–3), so the agent is not a default; but shipping profiles must not take formats away from free 4B users who have them now.
8. **The eval matrix reuses the skills harness's discipline but not its executor.** Graders, gates, calibration, promotion rule, fixtures and truth carry over; every committed run drives SurfSense's own request path at the app's own sampling (the app's providers and llama-server for single calls, the agent thread API for agent jobs) on a packaged build. *Reason:* evalkit is tied to Claude Code subagents and Haiku, and only behaviour inside the shipped app is worth shipping (I3 §d; [04](04-runtime-and-packs.md) adds a frozen-build check because frozen builds differ).
9. **A gate is read over cases, not pooled runs.** Each family defines a run-level pass; a case's rate is its passes over its runs; a gate needs a minimum number of distinct cases and a lower bound from a cluster bootstrap over cases. *Reason:* runs of one case are correlated, so pooling them overstates confidence, and every result so far is n=1 (I3 gap 4).
10. **The matrix targets the bundled opencode only.** Today that is 1.18.34. A 2.x column runs only when [04](04-runtime-and-packs.md) decides to move (its decision 20). *Reason:* users run the bundled build, and the skills' 2.0.12 acceptance does not carry over.
11. **Spending is recorded on every remote route and visible before and during a job.** A local ledger, a pre-job estimate from measured token medians, and app-wide caps the providers and the model endpoint enforce. Usage comes from the Messages stream on Anthropic and from the final usage chunk on OpenAI-compatible routes; where a route returns none, the ledger estimates and says so. *Reason:* frontier-first means the user pays per token, with no hosted inference to absorb it ([ADR 0038](../../adr/0038-chatgpt-plans-sign-in-through-openai-not-codex.md)), and a cap that covers only Claude would not cover OpenAI or OpenRouter users.
12. **A runtime fallback never moves a thread between engines.** A failed job thread offers a workflow run, which becomes its own artifact version linked from the failed turn. *Reason:* the locked decision "A thread gets its engine when it is created … and keeps it" ([agent README](../agent/README.md#locked-decisions); `engine_choice.py`: "A thread keeps what it got.").
13. **Learning without telemetry comes from a user-saved run bundle and a local self-test.** Nothing is uploaded by the app, and a bundle holds no document text unless the user ticks it. *Reason:* ADR 0016, and the [issue reports](../../architecture/issue-reports.md) precedent, where the user carries the log to a public issue.
14. **A verdict reflects eval rows and live gates only, never a release policy.** A job is offered on a model once its row passes the job gate. Nothing in the capability holds a job back for another reason, such as a pending legal review, and "Not on this model" is never used for one; the starter-playbook label is [02](02-skills-and-engines.md)'s and [06](06-product-shape.md)'s. The one exception is the administrator's organization policy, which 06's `apply_org_policy()` applies last and which may only lower a verdict. *Reason:* every verdict must trace to an eval row ([06](06-product-shape.md) decision 2), or users cannot tell a measured failure from a business hold.
15. **Frontier-first measures the free agent too, and every frontier failure is explained before the descent.** The free agent is gated on free-form file tasks as well as on its smoke, one OpenAI and one Gemini model get columns beside Claude, and each failed frontier case is labelled `skill`, `tool`, `prompt` or `model` and, unless it is `model`, fixed before lower rungs run that family. *Reason:* "Work on files" is offered for general file work that the job cases never exercise, many users bring OpenAI or Google keys, and a lower rung read against an unexplained frontier failure measures SurfSense's bug, not the model.

## Design

### 1. The native Anthropic provider (chat, titles, Studio)

New package `modules/llm/providers/anthropic_messages/`, one responsibility per file:

| File | Holds |
|---|---|
| `provider.py` | `AnthropicMessagesProvider`, implementing the `Generator` protocol ([`protocols.py`](../../../surfsense_local/backend/modules/llm/providers/protocols.py)) |
| `request.py` | `messages_request(model, messages, *, max_tokens, reasoning, effort, json_schema, rules) -> dict` |
| `schema.py` | `for_messages(json_schema)`: adds `additionalProperties: false` and `required` where the API needs them; refuses unsupported features at build time |
| `stream.py` | stream events → `Delta` plus a `Usage` record; `stop_reason` handling |
| `rules.py` | `ModelRules` from the remote manifest: sampling accepted, `reasoning_options` (effort values or `budget_tokens`), `output_limit` |
| `counting.py` | `TokenCounts`: `count_tokens` with a per-process cache keyed by sha256 of the text |
| `errors.py` | `RefusalError(category)`, `KeyRejectedError`, `RateLimitedError(retry_after)`, `OverloadedError` |

How each Generator argument maps onto the API:

- **Caching.** The system prompt is a list of text blocks with an explicit `cache_control` on the last one, and the request carries top-level automatic caching so chat history caches as it grows. Studio's grounding gets its own breakpoint, so the formatting call of a write-then-format job ([04-workflows](../agent/04-workflows.md), decision 3) and any repair call read it from cache. TTL is the default 5 minutes.
- **`json_schema`** goes out as `output_config.format` ([structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)). Studio's schemas are then enforced on Claude, so [04-workflows](../agent/04-workflows.md) decision 4's "a local model formats" no longer applies to it.
- **Effort and thinking are two settings, not one.** `run_model()` always sends `reasoning=False` ([`generate.py`](../../../surfsense_local/backend/worker/studio/shared/generate.py)), a switch added because "a small model can reason until the window runs out". On Claude it means "no visible thinking", nothing more:
  - **Effort** comes from the capability (section 4: the lowest effort that cleared that job's gate), else the manifest's default. It is sent as `output_config.effort` only where `reasoning_options` lists `effort`.
  - **`reasoning=False`**: `thinking` is omitted. That runs adaptive thinking with its default `display: "omitted"` on Opus 5.5 and Sonnet 5.5, and no thinking on Haiku 4.5. The provider never sends `{type: "disabled"}`.
  - **`reasoning=True`**: adaptive thinking with `display: "summarized"` where `reasoning_options` lists `effort`; `{type: "enabled", budget_tokens: N}` where it lists only `budget_tokens` (Haiku 4.5), with N at least 1,024 and below `max_tokens`.
- **`max_tokens`** is capped at `output_limit`. **Refusal** (`stop_reason: "refusal"`) raises `RefusalError` with its category; the provider never switches models on its own.
- **`token_count`** calls `POST /v1/messages/count_tokens` once per distinct text and caches the answer by sha256 (2,048 entries, per process). History turns are therefore counted once over a thread's life, and an ordinary chat turn costs at most two calls: the new question and the previous answer. When `count_tokens` fails or is rate-limited, the call falls back to the heuristic `budget.py` uses today and the turn proceeds. **`context_tokens`** reads `max_input_tokens` from `GET /v1/models/{id}`, else the manifest.

**Resolution.** `modules/llm/connections/wire.py`:
- `connection_wire(connection) -> Wire` (`OPENAI_CHAT | ANTHROPIC_MESSAGES | OPENAI_RESPONSES`) from `auth_kind` and the host. `api.anthropic.com` with a key is `ANTHROPIC_MESSAGES`; a ChatGPT sign-in is `OPENAI_RESPONSES`; everything else is `OPENAI_CHAT`.
- `sdk_base_url(connection) -> str` strips a trailing `/v1` (the SDK appends `/v1/messages`), and `messages_url(connection) -> str` ensures `/v1/messages` for the relay. Both spellings of the stored URL resolve to the same request URL.

`resolve_generation()` branches on the wire. The SDK client is built per call with SurfSense's own `httpx.AsyncClient`, after `egress.require()` has passed in `_connection()`, with `max_retries=2`. *Reason for per call:* `run_model()` runs each call under its own `asyncio.run`, so a client bound to one event loop cannot be reused across calls.

**Manifest.** `RemoteModel` in [`schema.py`](../../../surfsense_local/backend/modules/llm/catalog/remote/manifest/schema.py) gains `cost: Cost | None` (input, output, cache read and cache write per million tokens), and `translate.py::_model()` keeps models.dev's cost fields. A refresh adds `claude-sonnet-5-5`. `call` stays `null` on every Claude model. A test asserts that `claude-opus-5-5` on an Anthropic connection stays selectable after the refresh (`unusable_reason()` is `None`, the catalog row is usable, the selection route accepts it).

### 2. Serving Claude to opencode

**Choice: point opencode's own Anthropic provider at a SurfSense passthrough.** When the selected wire is `ANTHROPIC_MESSAGES`, `opencode_config()` writes this provider block:

```json
"surfsense": {
  "npm": "@ai-sdk/anthropic",
  "options": { "baseURL": "http://127.0.0.1:<api>/agent/model/anthropic/v1", "apiKey": "<launch key>" },
  "models": { "<model>": { "tool_call": true, "reasoning": true, "limit": "<from the window, as today>" } }
}
```

`AgentSetup` gains `wire`. A change of model already rewrites the config and restarts opencode ([agent](../../architecture/agent.md#known-gaps)), so switching wires costs nothing new.

The route is `POST /agent/model/anthropic/v1/messages` in [`model_endpoint/router.py`](../../../surfsense_local/backend/modules/agent/model_endpoint/router.py). Its handler, `relay_messages()`, does the following:

1. **Launch key.** `require_launch_key()` ([`launch_key.py`](../../../surfsense_local/backend/modules/agent/launch_key.py)) also accepts the key as `x-api-key`, which is where `@ai-sdk/anthropic` puts it.
2. **Address.** `address_selected_model()` returns a `ModelAddress` that now carries `wire`. For Anthropic the URL is `messages_url(connection)`, with `key_headers()` plus any `anthropic-beta` values that pass the allowlist in `model_endpoint/anthropic_betas.py`. Egress and `model_activity` work as today.
3. **Body allowlist** (`model_endpoint/messages_body.py::allowed_body()`). These keys pass: `model` (overwritten with the selected name), `messages`, `system`, `tools`, `tool_choice`, `max_tokens`, `stream`, `thinking`, `output_config`, `stop_sequences`, the sampling keys, `cache_control` and `context_management`. `metadata` and any unknown key are dropped. `mcp_servers` or `container` in the body refuses the request. **`tools` is an allowlist:** every entry must have no `type` or `type == "custom"`, the client-defined tools opencode sends; any other entry refuses the whole request with an Anthropic-shaped 400 naming the type. *Reason:* server tools (web search, web fetch, code execution and whatever Anthropic adds next) make Anthropic fetch the web or run code on the user's documents, an egress path the locked decision "opencode and the network: None beyond loopback" forbids ([agent README](../agent/README.md#locked-decisions)); a denylist of known type names fails open on a new one. `max_tokens` is capped at the model's output limit.
4. **No reshaping.** `shaped_messages()` is not applied. It merges system messages and edits text, which would break cache prefixes and the conversation-bound thinking blocks current Claude models check. The control-token defusing it does guards llama.cpp templates, which this route never reaches.
5. **Errors in Anthropic's shape.** Every error on this route goes through a new `error_replies.anthropic_error(status, type, message)`: `{"type":"error","error":{"type":…,"message":…}}`. Today's statuses stay (409 `model_not_selected` and `model_busy`, 403 `egress_disabled`), with Anthropic error types. `relay()` gains a `wire` parameter: on the Messages wire `_frames()` appends no `[DONE]` and reports a broken stream as `event: error` with an Anthropic error body.
6. **Spend.** Before relaying, `spend.allow(scope)` refuses a request once a cap is reached (section 3). It answers **403 `permission_error`**, never 429, with a message that matches none of opencode's retry patterns: "SurfSense stopped this job: its spending cap is reached. Raise the cap in Settings, Models, Spending." *Reason:* opencode retries any 429, any `rate_limit` wording and any message containing `429` or `500` up to five times with backoff (`retry.ts`), and the SDKs mark 408, 409, 429 and 5xx retryable; a 403 with plain wording ends the turn on the first reply. A unit test runs the message through a copy of `RETRYABLE_MESSAGE_PATTERNS`. After relaying, `relay()` gains a `usage_tap`. It reads `message_start.message.usage` and the last `message_delta.usage` from the SSE lines it already forwards, and writes one ledger row per request.

Translating OpenAI chat to Messages inside SurfSense, and handing opencode the user's key, are both rejected (see Options). The compatibility path stays for one eval column, "Sonnet via compat", which prices what the native route gains.

### 3. Cost controls

- **Usage on every remote route.**
  - Anthropic: the native provider's `Usage` and the relay's `usage_tap` (section 2).
  - OpenAI-compatible remotes: `OpenAICompatibleChatProvider` sends `stream_options: {"include_usage": true}` to catalog providers that accept it and reads the final chunk's `usage`. On the agent route, `opencode_config()` sets `includeUsage: true` on the `@ai-sdk/openai-compatible` provider block (an option of that package; confirm on 1.18.34), and the existing relay gains the same `usage_tap` for `data:` chunks.
  - A remote stream that ends without usage writes a row with `usage_source = "estimate"`: characters sent and received divided by four.
  - Local models write nothing.
- **Ledger.** New table `model_spend`, created by revision `<next>_capability_and_spend.py` (the number is assigned at merge, as in [01](01-sources-and-folders.md); [03](03-editable-artifacts.md) also adds a revision), all new tables so no rebuild is involved. Columns: `id`, `at`, `route` (`chat | title | studio | agent | workflow | self_test`), `connection_id`, `model`, `input_tokens`, `cache_write_tokens`, `cache_read_tokens`, `output_tokens`, `usage_source` (`reported | estimate`), `usd` (from the manifest's `cost`, null when unknown) and `scope` (an artifact id, a thread id, or null). The code lives in `modules/llm/spend/ledger.py::record()`.
- **Settings outlive a model switch.** Caps live in a single-row table `spend_settings` (`per_job_usd`, `monthly_usd`, `estimate_threshold_usd`), read and written by `modules/llm/spend/settings.py`, never in `SelectedModel.settings`, which is cleared on every model change. The monthly sum is computed from the ledger over the current calendar month in local time.
- **Estimate before a long job.** `modules/llm/spend/estimate.py::estimate_job(job, capability, prompt_tokens) -> Estimate(low, typical, high)`. `prompt_tokens` is counted on the prompt actually built; steps and output size come from the profile's measured p50/p90 for that job; prices from the manifest. Studio's generate dialog (`frontend/src/features/studio/`) and the agent composer show it when `typical` exceeds `estimate_threshold_usd` ($0.25 by default). An unmeasured job says "not measured on this model" instead of a number.
- **Caps.** Settings › Models › Spending holds a per-job cap ($5 by default) and an optional monthly cap; both apply to every remote route. Studio pipelines and workflows call `spend.allow()` before each model call, and the model endpoint before each opencode request. A model request carries no thread id (I1); [01](01-sources-and-folders.md)'s per-thread tool URL names the thread for tool calls only. The scope therefore comes from a registry P2 adds, `modules/agent/agent_threads/active_turns.py`, which `turn.py` fills when a turn starts streaming and clears in a `finally` when it ends: with one streaming turn in the workspace, the request counts against that turn; with two, against their sum, which errs towards stopping early. The screen says the figure is an estimate and the provider's bill is authoritative.

### 4. The capability profile

This is the profile the chosen product shape reads; [06](06-product-shape.md) turns its fields into what the user sees. Code lives in `modules/llm/capability/`:

| File | Holds |
|---|---|
| `manifest/profiles.json` | the reviewed rows |
| `schema.py` | pydantic models with `extra="forbid"`, checked on write and on load as the catalogs are |
| `loader.py` | `load_profiles()`, cached |
| `key.py` | `remote_key(selected, connection) -> ProfileKey`; `local_key(build: InstalledBuild, capacity_window: int) -> ProfileKey` |
| `resolve.py` | `capability_of(session) -> Capability`: synchronous, reads the database, the manifests, `installs.json` and cached GGUF shapes; never calls a server or loads a model. [06](06-product-shape.md)'s `org_policy.py::apply_org_policy()` runs last in it |
| `gate.py` | `agent_gate(session, capability) -> Capability`: async; confirms tool calls (which may load a local model) and is called only when a thread is created or an agent turn starts |
| `derive.py` | `derive(rows, key, confirmations) -> Capability`: the thresholds below |
| `schema.py` (also) | `Reason(code, values)`, the coded reasons [06](06-product-shape.md) renders through the ICU catalogs |
| `rungs.py` | the fallback table both the eval and the app read |
| `self_test/` | the in-app self-test (section 9) |

**The key.**
- `path`: `anthropic-native`, `anthropic-compat` (the eval column only), `openai-chat:<catalog provider>` (the `openai`, `google` and `openrouter` catalog providers are `openai-chat:openai`, `openai-chat:google` and `openai-chat:openrouter`), `chatgpt-plan`, `custom` (a connection naming no catalog provider) or `llamacpp`.
- `model`: the provider's id remotely. Locally, the curated entry id (`qwen3-4b`, not the file stem), found by matching `installs.json`'s `repo` and `quantization` for the selected model id against the local manifest's builds. A file with no `installs.json` entry, or one no curated build matches (any searched Hugging Face GGUF), has no key and gets the unmeasured default.
- `build` (local only): quantization, bits and llama.cpp tag, from the matched manifest build.
- `window`: remotely, the catalog's context; locally, the **capacity window**, `plan_load(shape, weights_bytes, budget, live=None).n_ctx`, cached per (file, size, hardware budget). The live budget never sets the capability, so the same machine does not flip between engines with free memory (section 8).
- `effort` where the route has it.

A local row matches on the same entry id with at least the measured bits and a capacity window of at least the row's `min_window`; another llama.cpp tag still matches, with the reason `measured_on_build` (`{tag}`). A remote row may carry `same_as: <key>` once a smoke run confirms it, so OpenRouter's Claude can borrow native measurements (Open question 7). Claude through any other gateway is a `custom` path and stays unmeasured until it has a row; Bedrock and Vertex cannot be selected at all (Today).

**Resolution order**: an exact measured row; a hand-written family row such as `claude-sonnet-5*` on `anthropic-native`, marked `provisional`; a local self-test row from `model_checks` (section 9), which can change formats and edit rungs only; the unmeasured default.

**What is measured.** Eleven families. Each defines the run-level pass its gate counts.

| Family | What it tests | Run-level pass | Grader |
|---|---|---|---|
| `grounded_qa` | answer from supplied passages with `[n]` citations; the chat eval cases, grown to at least 30 | judged grounded and no invented citation | `chat_eval/score.py` rules plus the chat eval rubric |
| `folder_qa` | the same over [01](01-sources-and-folders.md)'s synthetic 50–200-source folder, with server-side scope, at the app's retrieval settings | as `grounded_qa`, plus the expected sources cited | expected facts and citations |
| `schema` | each Studio JSON format and the Office spec formats from [02](02-skills-and-engines.md): valid first try, valid after one repair, semantic checks. The Office cases are content requests graded on the built file, so the same cases also run through today's `exec()` path (the baseline below) | valid after at most one repair and semantic score ≥ 0.80; for an Office format, the file opens and the per-case content checks pass | schema validator plus per-format checks (quiz answers in passages, mind-map nodes cite sources; headings, tables and figures present in the Word, PowerPoint, Excel or PDF file) |
| `refine_spec` | [03](03-editable-artifacts.md) rung 1, Refine: rewrite a whole small spec under the format's schema | valid, the requested change present, and every spec item the request did not name identical | schema validator, identity check over untouched items, a per-case check of the change |
| `selection_content` | 03 rung 1, selection edit: replacement text or values for one scope, which the server applies | applied, only the scope changed, content check passed | 03's resolver and apply report, identity check |
| `multi_op_plan` | 03 rung 2: a multi-operation engine plan on a revised copy (docx first) | the engine applies every op, no `G-*` gate fails, gated score ≥ the case's truth threshold | [02](02-skills-and-engines.md)'s engine report and graders |
| `agent_smoke` | [`01-which-engine.md`](../agent/01-which-engine.md#what-tested-means)'s smoke, on the free agent `surfsense` and on each job's agent `surfsense-job-<key>` | completes with the expected tool calls | scripted checks |
| `free_agent_tasks` | the free-form file work "Work on files" is offered for, through the free agent, at least 10 cases: a brief from several sources written to a Word file; a draft revised over 3 turns; a CSV summarized on a machine with no system Python (the driver runs opencode with `python` absent from `PATH`, as on a packaged Windows install); a fact found and cited across a 200-file folder; and others of the same kinds | the expected file or answer exists, the per-case facts and citations are present, nothing is written outside `outputs/`, and no `G-*` gate fails on a case that edits a file | per-case checks on the output and citations, blind grader calibrated for the written briefs |
| `skill_choice` | the free agent with up to three skills listed: prompts that need one of them or none | the right skill (or none) loaded first | scripted checks |
| `agent_job` | contract-redline E01/E02/E07/E11, docx D01/D03/D05, and the questionnaire jobs once [02](02-skills-and-engines.md) builds them; each through the free agent, a job thread and the workflow | no `G-*` gate fails and the gated score ≥ the case's truth threshold (0.80 where the truth file names none) | the skills project's graders and `G-*` gates, blind grader calibrated |
| `edit_session` | 3–5 sequential edit requests on one artifact, each building on the last ([03](03-editable-artifacts.md) versions) | every step identity-clean and the final state matches truth | per-step identity check plus final-state truth |

**The `exec()` baseline.** Before [02](02-skills-and-engines.md)'s phase B deletes `runner.py`, P0 runs the Office `schema` cases through today's `exec()` path on the default curated model, and on the other curated local rows it measures, and records the case rates as `exec_baseline` in each row. A builder replaces `exec()` for a format on a model where the builder scores at least that baseline (section 4, Formats).

**Languages.** Each job family (every job's `agent_job` cases, `free_agent_tasks` and `edit_session`) has at least one case whose documents are not in English. Each job skill states its supported document languages in its frontmatter ([02](02-skills-and-engines.md) section 5), and a language joins that list only when its cases pass here. A row records, per job, the languages its passing cases cover (`languages`), and [06](06-product-shape.md)'s job card shows them.

`long_context` is not a family. No pipeline packs whole documents up to the window: chat sends five passages and Studio 24,000 characters whatever the window, so such a family would measure retrieval, not the model. It returns when [01](01-sources-and-folders.md)'s `gather()` takes its budget from the window through a function such as `worker/studio/shared/gather.py::budget_chars(window)` (Open question 6).

Each result records the gated and ungated scores, case-level rates, pass^k where defined, p50/p90 tokens (input, cache read, output), steps and wall time, shell asks per run and unsafe asks (a command writing outside `outputs/` or naming a network tool), the sampling settings and seeds, the app build, and the harness, rubric, prompt and opencode versions with the date.

**Example row** (the shape is the proposal; the numbers are placeholders):

```json
{
  "key": {"path": "llamacpp", "model": "qwen3.5-4b", "build": {"quant": "UD-Q4_K_XL", "bits": 4, "llama_cpp": "b11xxx"}, "min_window": 16384},
  "source": "measured",
  "prompt_tier": "compact",
  "results": {
    "grounded_qa": {"cases": 30, "runs": 90, "mean": 0.90, "lower": 0.84},
    "schema": {"quiz": {"cases": 12, "mean": 0.98}, "mindmap": {"cases": 12, "mean": 0.91}, "docx": {"cases": 10, "mean": 0.70, "exec_baseline": 0.60}},
    "refine_spec": {"quiz": {"cases": 8, "mean": 0.85}},
    "agent_job": {"contract-redline": {"workflow": {"cases": 4, "mean": 0.41}}}
  },
  "app": "2.2.0", "measured": "2026-11-02", "harness": "job_eval 1"
}
```

**The capability.** `derive()` returns:

```python
@dataclass(frozen=True)
class Capability:
    source: Literal["measured", "provisional", "self_test", "unmeasured"]
    prompt_tier: Tier
    engines: frozenset[Engine]           # chat always; agent when the free agent is granted or confirmed untested
    default_engine: Engine               # what a new thread gets; 06 decides whether the user can switch
    jobs: dict[str, JobLevel]            # job -> job_thread | workflow | off, each with verdict, reason and languages
    skills: tuple[str, ...]              # what the free agent lists; at most three
    workflows: tuple[str, ...]           # jobs whose level is workflow, for 02's start_workflow()
    bash: Literal["ask", "deny"]         # the free agent only; job threads and workflows always deny
    formats: dict[str, Offer]            # format -> verdict and reason
    edit_rungs: dict[str, frozenset[int]]  # format -> 03's rungs offered
    effort: dict[str, str]               # job or family -> effort to send, remote only
    min_window: int
    reasons: tuple[Reason, ...]          # Reason(code, values), rendered by 06
```

Every `Offer` and `JobLevel` carries one of the four verdicts the design panel adopted: `recommended` (the highest measured level for that item), `available` (measured and passing), `untested` (no row, or no result for this item) and `unavailable` (a measured failure or a failed live gate), each with a `Reason(code, values)` that [06](06-product-shape.md) renders through the ICU catalogs, such as `measured_failure` (`{family, score, bar}`) or `window_below_floor` (`{needed, has}`). Decision 14 holds: a verdict comes from rows and live gates, and only 06's organization policy may lower one.

**Derivation** (`derive.py`). Each constant carries its reason in a one-line comment. A "case-level gate" means: mean of case rates ≥ the floor, the 10th percentile of a 10,000-draw cluster bootstrap over cases ≥ the bound, at least the named number of distinct cases, and every case run at least 3 times. With 7 cases, case rates of 1, 1, 1, 1, 1, 0.67 and 0.33 give a mean of 0.86 and a bound of 0.71; two cases at 0 give 0.71 and 0.43 and fail.

- **Free agent** (`agent` joins `engines`): `agent_smoke` 3 of 3 on the free agent, and `free_agent_tasks` passes a case-level gate with `AGENT_MIN = 0.75`, bound 0.60, at least 10 cases. Once `agent_job` has free-agent results (P3b), they must pass the same gate over at least 7 cases as well. No `G-*` gate failure in any run of either family: one silent change or leak blocks the free agent whatever the score. The first Claude rows (P4b) grant it on `agent_smoke` and `free_agent_tasks` alone, because the engine tools `agent_job` needs ship later ([02](02-skills-and-engines.md) phase 1).
- **Skills listed** (`skills`): the format skills plus the job skills of jobs whose level is `job_thread`, at most three ([02](02-skills-and-engines.md) decision 11 and section 6). More than one is listed only when `skill_choice` ≥ 0.95 over at least 20 cases; otherwise the free agent lists only `surfsense-word-edit`, and jobs run as job threads, where each job's own agent carries its skill.
- **Job level, per job**: `job_thread` when `agent_smoke` passes 3 of 3 on that job's agent `surfsense-job-<key>`, that job's `agent_job` cases through a job thread pass with every case at 2 of 3 runs or better, and a case-level gate over all job cases holds (0.75, bound 0.60, at least 7 cases); `workflow` when the job's cases pass the same per-case rule through the workflow; `off` when the workflow was measured and failed. `recommended` is `job_thread` when it passed, else `workflow`. The redline job is offered on a model as soon as its row passes this gate (decision 14).
- **Bash** (`bash`): `deny` for every model until a sandbox exists ([ADR 0039](../../adr/0039-document-scripts-run-without-approval.md)): document scripts reach SurfSense's script runner through a tool, and the agent has no shell. The rule below is what applies once a sandbox lets the shell return: `ask` only when the free agent is granted on a remote path and the free-agent runs (`free_agent_tasks`, and `agent_job` once measured), made with bash `ask`, show zero unsafe asks and a median of at most two asks per run. Otherwise `deny`. Job threads and workflows deny always ([02](02-skills-and-engines.md) section 6). Local rows are measured with bash denied; a 27–35B row that passes is measured again with `ask` to see whether the shell adds anything. Putting a Python on the agent's `PATH` is a separate proposal ([04](04-runtime-and-packs.md) decision 5), gated on matrix evidence that frontier agents fail without one; the no-Python CSV case in `free_agent_tasks` is that evidence.
- **Formats**: offered when `schema` for that format has at least 10 cases with validity after one repair ≥ 0.98 and semantic mean ≥ 0.80. A measured failure marks it `unavailable` with the score; a format with no result stays as today, `untested`.
- **Office formats on local models**: a format's builder is used on a local model when its `schema` case rate is at least that format's `exec_baseline` on the same model, or on the default curated model where the model has no baseline. Where it is not, the format keeps the `exec()` path on local models until the builder catches up: today's behaviour, so no free user loses a format they have now. Remote models always use the builder ([02](02-skills-and-engines.md) phase B).
- **Edit rungs, per format**: rung 1 Refine when `refine_spec` ≥ 0.80 over at least 8 cases; rung 1 selection edits when `selection_content` ≥ 0.80 for that scope kind; rung 2 when `multi_op_plan` passes a case-level gate (0.75, bound 0.60, at least 5 cases) with no gate failure; rung 3 when a job thread or the free agent is granted. `edit_session` pass^3 ≥ 0.60 over at least 4 cases enables a multi-step edit thread ([06](06-product-shape.md)'s Refine thread).
- **Grounded Q&A**: chat is never removed. `grounded_qa` below 0.85, or invented citations above 5%, over at least 30 cases, marks Q&A `available` with `measured_failure` (`{family: grounded_qa, score: 0.78, bar: 0.85}`), which 06 renders as "answers fall below SurfSense's grounding bar on this model (0.78)".
- **Effort**: for each job, the lowest effort column that cleared its gate.
- **Engine default**: `agent` when the free agent is granted and the path caches prompts (`anthropic-native`, `llamacpp`); `chat` otherwise. *Reason:* on a path without caching every quick question would bill opencode's fixed prompt and tool definitions per step, estimated at 3–5K tokens in SurfSense's config (I1; 6–8K for stock opencode, E4) and measured from `usage.input_tokens` once P3a runs in M4. 06 shows the Answer / Work on files switch; whether this rule or Answer is the default on cached paths is the [README](README.md)'s maintainer question 7, settled by the Sonnet column's first-answer latency and cost.
- **Live gates** on every agent level: tool calls confirmed (`agent_gate`), `auth_kind != "chatgpt"`, a route that carries tools, and the window floor below. A failed live gate lowers the level and records its reason (`tool_calls_unconfirmed`, `chatgpt_plan_no_tools`, `window_below_floor`).

**The window floor** for opencode threads, `min_window = max(32_768, smallest CONTEXT_RUNG ≥ (fixed + skill + 2 × page + reply) / 0.75, the row's measured min_window)`. `fixed` is opencode's prompt and tool definitions for that agent, measured from `usage.input_tokens` on the first request of each thread kind. For `surfsense` it is estimated at 3–5K tokens in SurfSense's config (I1; 6–8K for stock opencode, E4); a job agent's is smaller, since it denies three tools (`skill`, `bash`, `todowrite`) and keeps `glob`, but its prompt also carries the job's skill. `skill` is the skill body: the one the free agent loads, which compaction never prunes, or the one a job agent carries as its `prompt`, which compaction cannot drop ([02](02-skills-and-engines.md) section 6). 02's lint caps a body at 6,000 characters, about 1,500 tokens; a job agent's prompt, `job.md` plus the skill, may run past the free agent's 4,000-character prompt test and is tested under 10,000 characters, and its long references sit in readable files in the skills folder (at most 20,000 characters each, about 5,000 tokens, [02](02-skills-and-engines.md) section 5). `page` is one `inspect_document` page (20,000 characters, about 5,000 tokens); `reply` is 4,000; 0.75 is where compaction starts. With these estimates a free agent with a 1,500-token skill needs (5,000 + 1,500 + 10,000 + 4,000) / 0.75 ≈ 27,300, so 32,768. A job thread whose agent reads one 5,000-token reference needs about (4,000 + 1,500 + 5,000 + 10,000 + 4,000) / 0.75 ≈ 32,700, so 32,768 with almost no margin; a job whose measured text comes out larger takes the next rung, 65,536. The matrix replaces the estimates per opencode version.

**The unmeasured default** (decision 7) is what a model with no row gets; [03](03-editable-artifacts.md)'s edit entry points and [06](06-product-shape.md)'s surfaces read it:
- `engines = {chat}`; the free agent and job threads are `untested`, offered after one confirmation per model, which `capability_confirmations` stores by profile key so it survives switching away and back.
- Jobs that ship a workflow: `workflow`, `untested`. A job with `needs_passing_row` gets no level here: it is `untested` with `not_measured` and offers no run until its row passes the job gate (decision 14).
- Formats: today's set, `untested` ("not measured"). Whether DOCX, PPTX, XLSX and PDF run through a builder or still through `exec()` follows [02](02-skills-and-engines.md)'s phase B and the `exec()` baseline rule above: on a local model with no row, the default curated model's baseline decides.
- Edit rungs: rung 0 always; rung 1 Refine and selection edits for summary, mind map, flashcards, quiz and html, `untested`; rung 2 closed until measured; rung 3 only under a confirmed untested agent.
- `bash = deny`; effort from the manifest's default.

**Release rule.** `profiles.json` does not ship in a release unless the default curated text model (the first chat row in the local manifest, [ADR 0026](../../adr/0026-curated-order-is-list-position.md)) clears `grounded_qa` and the `schema` gate for summary, quiz, flashcards and mind map. If it does not, the prompts are fixed or the default changes first. A test on the generated docs page checks this.

**Wiring.**
- `engine_choice.selected_model_can_run_agent()` becomes `selected_engine(session, requested: Engine | None = None) -> Engine`, which calls `capability_of()` then `agent_gate()`. `requested` is the engine [06](06-product-shape.md)'s Answer / Work on files switch sends with `ThreadCreate.engine`; an engine the capability does not allow is a coded 409, and `None` takes `default_engine`. `chat/router.py` and `agent_threads/turn.py` keep calling it; `TESTED_MODELS` is deleted; the developer switch stays for development and skips the confirmation.
- Until M5 flips `ENABLED_BY_DEFAULT` in [`enabled.mjs`](../../../surfsense_local/electron/scripts/opencode/enabled.mjs), no installer stages opencode, so `selected_engine()` answers `chat` outside developer runs and agent threads stay behind the developer switch. The flip waits for committed `agent_smoke` and `free_agent_tasks` rows on the `anthropic-native` path and for [03](03-editable-artifacts.md)'s phase 3, which makes agent files into versions (the [README](README.md) owns the flip and the macOS condition on it).
- `modules/artifacts/service.py::_availability()` stays synchronous and reads `capability_of(session).formats`. Format availability never loads a model or calls a server.
- `SelectedModel.tier` stays a database-only property over `classify()`. `ResolvedGeneration` gains `capability` at resolution, and its `tier` returns `capability.prompt_tier` when a row names one, else the selection's tier. Claude on an Anthropic key then gets frontier prompts without touching `classify()`.
- `opencode_config()` fills 02's `AgentSetup.skills` from `capability.skills` and the free agent's `bash` from `capability.bash`. These change only with the model, which already rewrites the config.
- `GET /llm/selection/text_gen` (`SelectionRead`) gains `capability`. The job list, Studio and the model picker read it ([06](06-product-shape.md)).

### 5. The eval matrix

**Harness.** New `surfsense_local/backend/scripts/job_eval/` beside `chat_eval/`, with CLI `scripts/run_job_eval.py`. The family code (cases, runners, run-level pass rules) lives in `modules/llm/capability/families/`, inside the frozen API, so that the harness and the in-app self-test import one definition.

```text
run      --family <f> [--case <id>] --column <column id> --runs 3 [--app <packaged app>]
matrix   --columns <file> --families <list>          # sweeps, resumable, one row per run
grade    <run dir>                                    # code graders; selftest must pass first
judge    <run dir> --judge <id>                       # blind, calibrated
summary  <run dirs…>                                  # case table, pass^k, bootstrap bounds, tokens, cost
publish  <summary>                                    # writes profiles.json rows and the docs page
import-run <bundle>                                   # a saved run bundle into a draft case
```

| Part | Reused from | Change |
|---|---|---|
| Single-call targets | `chat_eval/send.py` (`local`, `featherless`) | adds `anthropic`, which calls `AnthropicMessagesProvider`, and `openai_compatible`, which calls `OpenAICompatibleChatProvider` with `key_headers` and serves the OpenAI, Gemini and OpenRouter columns. Every request is what the app sends, streamed, at the app's sampling |
| Request building | `chat_eval/request.py`, Studio's `run_model()` and pipelines | the families call the pipeline functions, 03's `revise()`, 02's engines and `start_workflow()`, not copies |
| Agent driver | none (evalkit's subagents are not reusable) | `job_eval/agent_driver.py --app <path>` starts a packaged app (or the dev app for screening) with the column's model selected. It creates a thread through `agent_threads/router.py` (free agent or job thread), sends the case prompt, or each turn of a multi-turn case, and answers permission asks from a per-case policy file. A case that needs it starts the app with no `python` or `py` on `PATH`, which opencode's shell inherits. It records the asks, collects `outputs/` and artifact versions, then kills the turn at a wall-clock limit |
| Graders, gates, selftest, calibration, promotion rule | [02](02-skills-and-engines.md)'s `document_skills/graders/` | imported from there, never vendored into `job_eval`. The current grader XSDs are a byte copy of Anthropic's schema folder; 02's phase 0 re-sources them |
| Judge | `chat_eval/judge/` | rubrics per family. The judge id and rubric hash are recorded. On each vendor's columns, a 10% sample is judged again by another vendor's model to check self-preference |

**Fixtures** contain nothing a user wrote: the chat eval's cases; the skills project's hashed fixtures and truth (E01/E02/E07/E11, D01/D03/D05) once [02](02-skills-and-engines.md)'s question on their licence (its open question 2) clears; single-scope edit cases built from SurfSense-authored documents; [01](01-sources-and-folders.md)'s synthetic policy folder, which also serves the 200-file `free_agent_tasks` case; SurfSense-authored briefs, drafts and CSVs for the other `free_agent_tasks` cases; the non-English cases each job family needs, written or licensed for the purpose; questionnaire fixtures once 02 has the xlsx engine. They are hashed in `job_eval/fixtures/MANIFEST.json`; large binaries come from a release asset pinned by SHA-256, published only after that licence check.

**Runs and sampling.**
- Every run uses the app's own settings: the remote manifest's `sampling` where it has one, the route's defaults where sampling is refused (Opus 5.5 and Sonnet 5.5 reject non-default values), and the local manifest's sampling on llama.cpp. The seed varies by run (`seed = run index`) where the route takes one, and is recorded.
- At least 3 runs per case, 5 for any case whose family sits within 0.10 of a gate. `edit_session` runs n=5 and reports pass^1 and pass^3 with the unbiased estimator C(c,k)/C(n,k) (τ-bench's definition).
- **Screening** runs in the dev app and may use OpenRouter or Featherless. **Committed rows** come only from runs against a packaged build on the app's streaming path, with the build version in the row.

**Columns.** Each column is path + model + build + window + effort, and each says where it runs. Reference machines are named by their hardware.

| Rung | Columns (candidates; eval decides) | Runs on |
|---|---|---|
| Frontier | Opus 5.5 (effort medium and high), Sonnet 5.5 (low, medium, high), Haiku 4.5; Sonnet 5.5 via compat once | Anthropic API, a dedicated eval workspace with its own spend limit so cache and spend are isolated |
| Frontier, other vendors | one OpenAI model and one Gemini model, the newest frontier row in the manifest at sweep time (today candidates are `gpt-5.6` and `gemini-3.1-pro-preview`): `agent_smoke` and the single-call families | the `openai` and `google` catalog providers on the OpenAI chat wire (`openai-chat:openai`, `openai-chat:google`), with eval keys and their own spend limits |
| Open 100B+ | GLM-5.x, Qwen3.5-397B-A17B, DeepSeek V4, Kimi K2.6, gpt-oss-120b | OpenRouter, provider order pinned and fallbacks off; the provider that served each request is recorded |
| 27–35B local | Qwen3.8-27B, Qwen3.6-35B-A3B, Gemma 4 26B-A4B and 31B | screened on OpenRouter or Featherless; rows committed only from GGUF Q4 on a 24–32 GB machine, which does not exist yet (Open question 1) |
| 8–14B local | Qwen3.5-9B, Gemma 4 12B, Qwen3 8B/14B | GGUF on the RTX 3050 6 GB, on a 16 GB M4 (to be confirmed) and on a 16 GB Windows laptop with integrated graphics |
| 4B local | Qwen3.5-4B, Gemma 4 E4B, Qwen3 4B, Gemma 3 4B | GGUF on the RTX 3050, the M2 8 GB, the 16 GB M4 and the 16 GB integrated-graphics Windows laptop, at the capacity window each machine gives |

The RTX 3050 and the M2 8 GB are the machines [fit](../../architecture/local-models/fit.md) measured. The 16 GB M4 is computed there, not measured, and needs confirming like the 24–32 GB machine. The 16 GB Windows laptop with integrated graphics is a new reference machine, the typical business laptop; the [README](README.md)'s whole-stack memory budget is measured on it too.

**Order.** Single-call families do not wait for any ceiling: `grounded_qa` and `schema` run on every curated local row as soon as the harness exists (P0), and `refine_spec` and `selection_content` as soon as [03](03-editable-artifacts.md) builds Refine and selection edits. Only `free_agent_tasks`, `agent_job` and `edit_session` descend in order, Opus → Sonnet → Haiku → open 100B+ → 27–35B → 8–14B → 4B: a rung starts once the rung above has an `agent_job` column, committed or screened. Screening results from OpenRouter or Featherless satisfy the ordering; committed rows still come from GGUF on the named machines. A column that fails `agent_smoke` 0 of 3 skips `free_agent_tasks` and the free-agent and job-thread levels of `agent_job` and `edit_session`, and runs only the workflow level. This keeps a 4B column from spending a day failing redlines.

**Failure triage.** Every case that fails on a frontier column is labelled in the run summary as one of four causes, with a one-line note: `skill` (the SKILL.md text led the model wrong), `tool` (a SurfSense tool's schema, description, reply or error), `prompt` (SurfSense's agent or job prompt, or a Studio prompt) or `model` (the model erred with correct inputs). The first three are fixed in SurfSense and the case is re-run on the same column before any lower rung runs that family; only `model` failures stand as the ceiling lower rungs are read against. `summary` refuses to mark a frontier column complete while a failed case has no label. The labels live in the run directory's `triage.json` and appear on the docs page.

**Budget.** Estimated per column as runs × median tokens × price, to be replaced by measured medians after the first sweep. The medians assumed:
- an `agent_job` run: 1.2 M input-side tokens (contract-redline used 1.68 M per run and docx 0.52–0.74 M on Haiku, I3 §a; the mean over 4 + 3 cases is about 1.23 M), 85% cache reads and 15% cache writes, plus 30K output tokens (60K at high effort);
- an `edit_session` run: 0.4 M input-side tokens split the same way, plus 15K output;
- a `free_agent_tasks` run: 0.3 M input-side tokens split the same way, plus 15K output (30K at high effort), an estimate with no measurement behind it;
- single-call families: about 150 cases × 3 runs, each about 8K input and 1K output, uncached: about 4 M input and 0.45 M output per column.

Per run that gives, for an `agent_job` run, Opus 5.5 about $1.70 (medium) or $2.30 (high), Sonnet 5.5 $0.95 or $1.25 at high, Haiku 4.5 $0.48; through the compatibility layer, with no caching, Sonnet 5.5 about $2.70. A `free_agent_tasks` run costs about $0.58 on Opus 5.5 ($0.88 at high), $0.31 on Sonnet 5.5 ($0.46 at high) and $0.16 on Haiku 4.5.

A contract-redline run alone uses its own measured 1.68 M input-side tokens, not the 1.2 M mean over redline and docx cases. With the same split and 30K output, it costs about $0.61 on Haiku 4.5, $1.22 on Sonnet 5.5 and $2.15 on Opus 5.5 at medium, and $3.66 on Sonnet 5.5 through the compatibility layer. The per-job costs in the [business plan](../../../plans/community-local/file-agent-strategy.md) use these figures and this token assumption.

| Column | Contents | Estimated cost |
|---|---|---|
| Opus 5.5, medium | 30 `agent_job` runs (8 cases × 3, plus top-ups to 5), 20 `edit_session` runs, 30 `free_agent_tasks` runs (10 cases × 3), single-call families, +20% for lower-rung retries | about $125 |
| Opus 5.5, high | the same | about $160 |
| Sonnet 5.5, low and medium | the same, each | about $70 each |
| Sonnet 5.5, high | the same | about $85 |
| Haiku 4.5 | the same | about $35 |
| Sonnet 5.5 via compat | smoke plus two `agent_job` cases × 3, single-call families | about $45 |
| OpenAI and Gemini, each | `agent_smoke` × 3 and the single-call families, +20%; priced at Sonnet 5.5's rates until the manifest carries `cost` | about $20 each |
| Open 100B+, per model | OpenRouter rates | $10–30 |
| Smoke on an opencode bump | `agent_smoke` plus two `agent_job` cases × 3 (two `free_agent_tasks` cases until `agent_job` exists), on Haiku and Sonnet medium | about $15 |

A full frontier sweep, the Claude, OpenAI and Gemini columns, is therefore about $630, planned as about $650 per sweep with a $300 monthly cap outside sweeps (the [README](README.md)'s maintainer question 4). Each open 100B+ column adds $10–30 and runs when the descent reaches it (P5b); with five of them in one sweep the total would be about $680–780. No `long_context` cost is included because that family is cut. The Message Batches API is not used for committed rows: it is a different, non-streaming endpoint from the one the app calls; it may serve screening only. The [business plan](../../../plans/community-local/file-agent-strategy.md) owns who pays (I8 open question).

**Cadence.**
- Each opencode bump: `agent_smoke` and two `agent_job` cases (two `free_agent_tasks` cases until `agent_job` exists) on Haiku, Sonnet and every agent-capable local row.
- Each llama.cpp bump: `grounded_qa`, `schema`, `refine_spec` and `selection_content` on every curated local row, plus `agent_smoke` on agent-capable rows.
- Each model added to either catalog: its single-call families, then its place in the descent.
- Each prompt or skill change: the families it touches.
- Before a release that changes `profiles.json`: a sweep of the changed rows, and the release rule in section 4.

**Where paid runs may execute.** `.github/workflows/model-evals.yml` runs only on `workflow_dispatch` and on `push` to `dev` and `main`, never on `pull_request` or `pull_request_target`. The Anthropic, OpenAI, Google and OpenRouter keys sit in a GitHub environment, `model-evals`, with required reviewers, and each eval account has its own spend limit at its provider. An opencode or llama.cpp bump pull request (Dependabot's included, which gets no secrets) merges only after a maintainer has run the dispatch on the PR's head commit, after review, and linked the result; the merge rule names that manual gate.

**Publishing.** `publish` writes `profiles.json` rows, reviewed in a PR with the summary attached, and generates `docs/architecture/model-capabilities.md` (one table per family; each cell shows cases, runs, mean, bound, cost per run, app build and date). In the app, curated rows in Settings and the onboarding chat step (`frontend/src/features/models/`, `features/onboarding/model-step/`) say what the model does on this machine, such as "Agent", "Studio: 6 formats" or "Q&A", before download, with the date and n in a tooltip. Unmeasured rows say "Not measured by SurfSense". The words are [06](06-product-shape.md)'s.

### 6. Descent thresholds and the fallback ladder

Office exams put even frontier agents at 68.8% against 95.5% for humans (E4 §2.5), so the floors in section 4 are set where a user can trust the result with verification, not at frontier parity. Every pass rate on a lower rung is read against the measured ceiling above it.

The ladder has the rungs [02](02-skills-and-engines.md) builds, and no others:

| Rung | What the model gets | Used for |
|---|---|---|
| `agent` | the free agent `surfsense`, up to three listed skills, SurfSense tools, bash per the capability | free-form threads |
| `job_thread` | the job's own opencode agent, `surfsense-job-<key>`, written into the config once with the job's skill as its `prompt` and chosen per turn with `send_turn(agent=...)`, so compaction cannot drop the skill; `skill`, `bash` and `todowrite` denied, `glob` kept ([02](02-skills-and-engines.md) decision 11 and section 6) | jobs |
| `workflow` | no opencode; 02's plan, engine, verify, repair, each plan one call under a grammar or `output_config.format`, its unit sized to the window | jobs |

- `trimmed`, `few_tools`, `preselected_skill` and `constrained_plan` are cut. Each job's agent already carries its skill and drops three tools; 02's workflow already is a constrained plan, with its group size set by the window. A further rung is added only when the matrix shows a job failing at one level for a reason the next would remove.
- **In the eval**, lower rungs run only for jobs whose upper rung failed. The profile records the highest passing rung per job.
- **At runtime**, a job thread whose turn fails hard (step cap, loop detection, context overflow, the same malformed tool call twice) ends the turn with a reason and offers "Run this job step by step". That starts a workflow run through `start_workflow()`, which makes its own artifact version, linked from the failed turn by `chat_thread_id` and the turn's message id. The thread stays an agent thread. The offer is never taken automatically, so a remote user is not billed twice without asking.
- **Offline.** A remote route that stays unreachable after opencode's retries ends the turn the same way, with `model_unreachable` (`{host}`). [06](06-product-shape.md)'s offline state says the selected model is unreachable and offers the step-by-step run on the local model where the job's workflow allows it; an engine version in flight fails cleanly and keeps the head ([03](03-editable-artifacts.md)).
- Trigger detection lives in `agent_threads/turn.py` (step frames, error replies). The rule table lives in `modules/llm/capability/rungs.py`, so the eval and the app read one definition.

### 7. The small-model tier

For a 4B model, "simple Q&A and basic artifact generation through predetermined workflows" means:

- **Q&A:** today's grounded chat. Retrieval is model-independent (98% of 266 queries at mean rank 1.2, I6 §e), and small Qwen models are faithful summarizers (HHEM 5.7% for Qwen3-4B, E4 §3).
- **Studio formats:** today's set stays until measured. Each format the 4B fails on its own `schema` gate is then marked unavailable with its score. HTML and the Office formats move to [02](02-skills-and-engines.md)'s spec builders in its phase B, and no new code runs through `exec()`. On a local model an Office format keeps today's `exec()` path until its builder scores at least the `exec()` baseline (section 4), so the 4B never loses a format it has today.
- **Every JSON step gets a JSON schema** ([04-workflows](../agent/04-workflows.md) decisions 1–2). That includes mind map, HTML and the podcast outline, which rely on `parse_json` alone today. Schemas stay flat, because llama.cpp's grammar covers only part of real-world schemas (JSONSchemaBench, E4 §3). Writing formats use write-then-format (decision 3).
- **Thinking off** (`reasoning=False`, as `run_model()` already sends). The eval checks that each new chat template honours it: Qwen3.5 thinks by default (E4 §2.6).
- **Edits:** [03](03-editable-artifacts.md)'s rung 1. Refine has the model rewrite a small spec under its schema; a selection edit has it write only the replacement, and the server builds and applies the operation. They are offered untested on the five spec-backed formats and kept or removed by `refine_spec` and `selection_content`.
- **Jobs:** workflows only, with the skill picked by the harness.

| Target on the 4B column | Value |
|---|---|
| `grounded_qa` judge-grounded | ≥ 0.85 over at least 30 cases (Qwen3 1.7B reached 0.91 after tuning, in unpublished local runs) |
| invented citations | ≤ 5% (1.7B: 9–15%, same runs) |
| schema validity after one repair | ≥ 0.98 per format |
| format semantic score | ≥ 0.80 to keep the format |
| `refine_spec` and `selection_content` | ≥ 0.80 to keep Refine and selection edits |
| Office builder case rate | ≥ the `exec()` baseline, or the format stays on `exec()` |
| wall time per Studio job on the RTX 3050 and the integrated-graphics laptop | reported, not gated |

**Catalog update.** Candidates, added through `refresh_local_manifest.py` in one reviewed PR: Qwen3.5-4B and Gemma 4 E4B (small); Qwen3.5-9B and Gemma 4 12B (middle); Qwen3.6-35B-A3B, Qwen3.8-27B and Gemma 4 26B-A4B (agent tier). Sizes and licences come from E4 §2.6 and must be re-read from the model cards. Manifest order stays the only preference signal ([ADR 0026](../../adr/0026-curated-order-is-list-position.md)); Qwen3 rows stay until the new rows beat them on the same machines, 0.6B going first. The update needs:
- **a llama.cpp bump** (`BUILD` in `fetch-llamacpp.mjs`) if `b11050` does not load the Qwen3.5/3.8 hybrids or Gemma 4 (not verified here; the refresh script's first load answers it);
- **a fit change** in `fit/kv_cache.py` and `gguf/shape.py` to read the hybrids' recurrent-state and full-attention-interval keys; without it every layer is sized as attention and windows come out needlessly small;
- **`VALIDATED`** in `scripts/local_manifest/llamacpp/refresh.py` filled from eval runs, so each curated build's `validated.llama_cpp` names the tag it passed on;
- **re-runs** of the runtime measurements [runtime](../../architecture/local-models/runtime.md) took at `b11050`.

### 8. Local runtime limits

- **Window.** An opencode thread needs the capability's `min_window` (section 4), never less than 32,768.
  - The capability is decided on the capacity window (`live=None`), so it does not change with free memory. `plan_load()` keeps capping by the live budget, and `min_window` never overrides that cap: forcing a window into memory that is in use pages the model, as fit's measurements show.
  - When the live plan falls below `min_window`, the capability is unchanged and the agent turn does not start, with `window_below_floor` (`{needed, has}`); 06 renders it as "This model needs 32K of context for the agent; the computer has room for 16K now. Free about 1.2 GB, or ask in a chat thread." The figure comes from fit's estimate. This happens only when other programs hold memory.
  - `plan_load()` takes a `min_window` hint and may choose a `q8_0` cache to reach it only when the runtime reports a working flash-attention kernel: `HardwareBudget` gains `flash_attention: bool`, filled from llama-server's startup log line on the device probe. Otherwise it stays f16 at the shorter window.
  - `CONTEXT_RUNGS` gains 65,536, used only when the capacity plan allows it (widening already requires the model to stay resident), so 27–35B rows measured at 64K and job agents whose skill and references need more can run there.
- **One slot.** On the local runtime, `create_artifact` creates the artifact and its pending first version as today, but records it in a new table `deferred_studio_jobs(artifact_id, workspace_id, created_at)` instead of enqueueing. The tool's reply says the artifact will be made when the agent's turn ends.
  - The row also records the thread, which the tool URL names once [01](01-sources-and-folders.md)'s phase 3a registers tools per thread. Release is still keyed by workspace, because another turn in the workspace may hold the one slot after the starting turn ends. The `active_turns.py` registry P2 adds says which turns stream there; this phase reuses it.
  - `turn.py` calls `release_deferred(workspace_id)` in a `finally` at the end of every turn, including errors and aborts. It enqueues the workspace's deferred jobs once no turn streams there.
  - The API's startup calls the same release for every workspace, because no turn survives a restart; a job whose sources are gone fails visibly with Studio's reason.
  - The Studio panel shows a deferred job as "Waits for the agent to finish".
  - A chat turn sent while the slot serves a job or another turn waits for it and says "Waiting for the running job" rather than failing, and bulk ingest yields while a local model turn streams (the [README](README.md)'s whole-stack budget).
  - Remote routes are unchanged. *Rejected:* `parallel = 2`, which doubles the KV cache on machines that already spill at 16K ([fit](../../architecture/local-models/fit.md)).
- **One text model app-wide.** It stays. The formatting call that [04-workflows](../agent/04-workflows.md) decision 4 gives to a local model is still needed for remote routes without schemas. With Claude now native, that is no longer Claude.

### 9. Learning without telemetry

- **Save this run.** Every agent turn, Studio job and edit gets a "Save run for a bug report" action: `modules/run_reports/bundle.py::build_bundle(scope, include) -> bytes`, written through Electron's save dialog and never uploaded by the app.
  - By default a `surfsense-run/1` bundle holds only: the profile key and capability; app, opencode and llama.cpp versions and the window; prompt file hashes; per step, the tool name, argument keys with each value's length and sha256, error codes, operation indices and statuses, schema-error paths (never the offending text), repairs and fallback rungs; token usage, timings and the spend estimate.
  - Argument text, engine report text, schema-error excerpts, sources and outputs are included only under one "Include document text" tick. The home folder is replaced as in issue reports.
  - The dialog shows the bundle's exact contents before it is saved.
  - `run_job_eval.py import-run <bundle>` turns a bundle into a draft eval case, which a maintainer rebuilds from non-confidential data into a regression case.
- **Test this model.** Settings › Models runs a code-graded set (`grounded_qa`'s rule checks without the judge, `schema`, `refine_spec`, and `agent_smoke` where the route has tools) on fixtures shipped with the app, through `POST /llm/capability/self-test` and `modules/llm/capability/self_test/`, which import the same `families/` code as the harness. It shows the result and its cost first on a remote route, writes `route = self_test` to the ledger, and stores a `model_checks` row with `source: self_test`.
  - It ships in P6 (M10). Until then [06](06-product-shape.md) offers no "Test this model" fix, and an unmeasured model's row says only "Not measured".
  - Self-test rows have their own gates, in `derive.py`: they can mark formats and rung-1 edits available or unavailable, and never grant the free agent, job threads or bash.
  - A user can export a self-test row for a pull request; a maintainer re-runs the judge on import before it becomes a provisional row.
  - A community member with a 24–32 GB machine can run `run_job_eval.py matrix` on the local columns and submit the summary; maintainers re-judge and re-run a sample before committing rows.

## Options considered and rejected

| Option | Why not |
|---|---|
| Keep Claude on the compatibility layer and measure there first | No caching, no schemas, no thinking, and the vendor calls it not production-ready. The baseline would understate Claude and overstate cost |
| Record the wire in the manifest's `call.protocol` | `call_reason()` treats any non-`responses` call as unusable, so every Claude model would leave selection |
| Translate OpenAI chat to Messages for opencode | Streamed tool-call deltas map both ways, thinking blocks with signatures have no field to ride in, cache breakpoints are lost in flattening, and every Messages rule change lands in SurfSense; opencode already speaks Messages and its transforms are maintained upstream |
| Give opencode the user's key and `api.anthropic.com` | Breaks the locked decision that keys and egress stay in SurfSense ([agent proposal](../agent/README.md#locked-decisions)); opencode's network is pinned to loopback |
| A new `provider = 'anthropic'` value on connections | Needs a CHECK change, so a batch rebuild that deletes every remote selection (migration 0023's warning) |
| Hand-written httpx client, like `openai_responses/` | Matches repo style, but puts every Messages rule change on SurfSense; the SDK is MIT and small |
| A 429 for a reached spending cap | opencode and the SDKs retry it up to five times |
| Caps in `SelectedModel.settings` | Cleared on every model switch, which defeats a monthly cap |
| Keep `TESTED_MODELS` in code, fill it from evals | A boolean cannot say "workflow for redlines, these four formats, Refine on two" |
| Fix `classify()` and keep tiers as the signal | Size predicts prompt shape, not agent competence: Haiku 4.5 on an Anthropic key is `capable`, like Qwen3-14B, yet scores 53.6% against 34.8% on BFCL multi-turn (E4 §2.1) |
| An unmeasured default restricted to schema-enforced formats | Takes formats away from every unmeasured model, every curated 4B included, the day profiles ship |
| A six-rung fallback ladder with mid-job engine changes | Moves a thread between engines against the locked decision; three of the rungs have no mechanism in 02 |
| Pooled runs with a Wilson bound | Runs of one case are correlated; 21 runs of 7 cases behave like about 7 |
| Fetch profiles from a SurfSense server | A runtime fetch the user did not ask for; breaks ADR 0014's reviewed-manifest rule and air-gapped installs |
| Rely on public leaderboards | Harness changes move scores by 36 points for the same model (gpt-oss-120b, E4 §2.2), and none measure SurfSense's jobs |
| Featherless as the source of truth for local rows | FP8/FP16 safetensors against users' 4-bit GGUF ([chat eval](../chat-eval.md)); kept for screening only |
| Message Batches for committed single-call rows | A different, non-streaming endpoint from the app's; kept for screening only |
| Opt-in automatic upload of failed runs | Still telemetry under ADR 0016, and confidential documents would leave the machine on a default |
| `parallel = 2` for the agent plus Studio | Doubles KV memory on machines that already spill |
| Grant the free agent on redline and docx `agent_job` cases alone | Leaves the general file work "Work on files" is offered for unmeasured, and those cases need engine tools that ship a milestone after the agent |
| The job skill as a per-turn `system` string | opencode's auto-compaction writes a continuation message without it, and the request builder reads only the last user message's `system`, so a long job loses its skill ([02](02-skills-and-engines.md), Today: `session/compaction.ts`, `session/llm/request.ts`) |
| Replace `exec()` with builders on every model at once, whatever they score | A default 4B that fails a builder schema would lose Word, PowerPoint, Excel or PDF, which it has today |
| A verdict for a release hold, such as a lawyer's review | Users could not tell a measured failure from a business decision, and 06 traces every verdict to a row |

## Phases

Milestones are the [README](README.md)'s: P0 lands in M1, the Claude route and the seam in M4, the first Claude rows in M5 with the agent's switch-on, the job and edit families in M6, the descent in M9 and the learning loop in M10.

| Phase | Milestone | Scope | Depends on | Size |
|---|---|---|---|---|
| P0 Harness and local single calls | M1 | `job_eval/` with `run`, `summary` and the `local` and `openai_compatible` targets; `capability/families/` for `grounded_qa` and `schema`, with the Office cases; the chat eval cases grown to 30; case-level statistics; first rows on Qwen3 4B, Gemma 3 4B and Qwen3 8B on the RTX 3050 and M2; the `exec()` baseline for Word, PowerPoint, Excel and PDF through `runner.py`, before [02](02-skills-and-engines.md)'s phase B deletes it. Beside it, M1 re-runs the skills project's contract-redline and docx baselines on Haiku 4.5 and on Sonnet 5.5 at low effort, n=3, before 2026-10-15 ([02](02-skills-and-engines.md)'s no-regression gate; Open question 3) | nothing | S: wraps existing `chat_eval` code |
| P1 Native provider and spend | M4 | `anthropic_messages/`, `connections/wire.py`, `resolution.py` branch, manifest `cost`, `<next>_capability_and_spend.py`, ledger, usage on OpenAI-compatible routes, `spend_settings` and the Spending panel | nothing | M: one provider, new tables, one settings panel |
| P2 opencode passthrough | M4 | `/agent/model/anthropic/v1/messages`, launch key via `x-api-key`, body and tools allowlist, `usage_tap`, Anthropic errors and frames, the 403 cap and its turn scope through a new `agent_threads/active_turns.py`, `opencode_config()` anthropic block and `includeUsage` | P1 | M: one route and config branch, one registry, plus integration tests on staged opencode |
| P3a Frontier first results | M4 | the agent driver with `--app`; `agent_smoke`, `grounded_qa`, `schema` on the Claude native columns and once via compat, which also measures `fixed` for the window floor; judge calibration; the `model-evals.yml` workflow and environment | P1, P2 | M: one driver and the first paid runs, about $150 |
| P4a The seam | M4 | the `capability/` package with the unmeasured default and no rows: `capability_of` (with 06's `apply_org_policy()` last), `agent_gate` and the live gates, `Reason(code, values)`, `selected_engine(session, requested)`, format availability, tier through `ResolvedGeneration`, confirmations, `SelectionRead.capability`; delete `TESTED_MODELS` | P1 for the key's path; [06](06-product-shape.md)'s S1 builds its surface on it | M: mostly wiring existing hooks |
| P4b Rows | M5 for the first Claude rows, then with every sweep | `derive()`'s measured thresholds; the `free_agent_tasks` family, its fixtures (one non-English) and runs on the Claude columns; `agent_smoke` and single-call columns for one OpenAI and one Gemini model; triage labels; the first committed `profiles.json` rows; the release rule; the generated docs page; the `enabled.mjs` comment | P3a, P4a; [01](01-sources-and-folders.md) phases 2 and 3a for the 200-file folder and the scoped agent; [03](03-editable-artifacts.md) phase 3, so agent files become versions | M: one family and the first rows, about $140 of runs |
| P3b Jobs and edits | M6 | `refine_spec`, `selection_content`, `multi_op_plan`, `skill_choice`, `agent_job` on all three rungs, `edit_session`, `folder_qa`; graders imported from 02; fixtures release asset; the non-English case of each job family; `rungs.py` and the runtime fallback offer, which job threads need from the day they ship | P3a, P4b; [02](02-skills-and-engines.md) phases 0, 1, 3 and 4 and its fixture licence question; [03](03-editable-artifacts.md) phases 2 and 4 (`selection_content` waits for its phase 5, in M9); [01](01-sources-and-folders.md) for the folder fixture and scoping | L: seven families and the rest of the full frontier sweep, about $340 (about $650 with P3a and P4b) |
| P5a Local runtime | M9 | llama.cpp bump, hybrid fit, `flash_attention` in the budget, the `min_window` hint and 64K rung, deferred Studio jobs and their release | [04](04-runtime-and-packs.md) for the bump in packaging; P2's `active_turns`; [01](01-sources-and-folders.md) phase 3a for the thread in the tool URL | M: a pin change, a fit change, one table and one release path |
| P5b Descent columns | M9 | open 100B+, 27–35B, 8–14B and 4B columns for the agent families (`free_agent_tasks`, `agent_job`, `edit_session`); catalog candidates; `VALIDATED` | P3b, P5a; a 24–32 GB machine for committed 27–35B rows | L: many columns |
| P6 Learning loop | M10 | "Save run" bundles with the default-private contents, `import-run`, the self-test ("Test this model") and `model_checks` rows, community submissions | P4a, P4b | M: one bundle builder and one Settings flow |
| P7 Cadence | M4 | the bump and release sweeps on `model-evals.yml`, the manual gate in the merge rule | P3a | S: scripts and a workflow file, plus a standing budget |

## Tests

- **Provider** (`tests/unit/llm/providers/anthropic_messages/`): `cache_control` on the last system block plus top-level caching; `json_schema` → `output_config.format` with `additionalProperties: false`; `thinking` never `{type: "disabled"}`; `reasoning=False` omits `thinking` and leaves effort as the capability set it; `reasoning=True` gives adaptive thinking on an effort model and `budget_tokens` on Haiku 4.5; no `effort` where the manifest lists none; no sampling keys where sampling is refused; recorded SSE fixtures parse into the right `Delta` sequence and `Usage`; `refusal` raises `RefusalError`; 429 carries `retry_after`; `count_tokens` is called once per distinct text and its failure falls back to the heuristic.
- **Resolution:** `connection_wire()` for `api.anthropic.com`, OpenRouter, a loopback server and a ChatGPT row; `sdk_base_url()` and `messages_url()` for `https://api.anthropic.com` and `https://api.anthropic.com/v1`; `resolve_generation()` returns the matching class; after a manifest refresh, `claude-opus-5-5` on an Anthropic connection is usable and selectable.
- **Passthrough** (`tests/integration/agent/test_model_endpoint.py`): launch key accepted as `x-api-key`, wrong key refused; the user's key replaces it; `model` pinned; a tool with `type: "future_server_tool_2027"` refuses the request with a 400 in Anthropic's shape; `mcp_servers` and `container` refuse it; messages reach upstream byte-identical; no `[DONE]` on the Messages wire; egress denial answers 403 and an unselected model 409, both in Anthropic's shape; the usage tap writes one ledger row from a scripted stream; a reached cap answers 403 `permission_error` before any upstream call, and its message matches none of the retry patterns.
- **opencode** (`tests/integration/agent/`): staged opencode against a scripted Messages endpoint shows `cache_control` marks arriving and a tool round trip completing; a capped request ends the turn after exactly one reply with no retry; the 403 and 409 replies are shown as readable errors; a job agent `surfsense-job-<key>` still carries its skill text in the first request after a forced compaction ([02](02-skills-and-engines.md)'s test, run on the Messages route too). This checks the 1.18.32 source reading on 1.18.34.
- **Config** (`tests/unit/agent/test_opencode_config.py`): the anthropic block for an Anthropic selection, the openai-compatible block with `includeUsage` otherwise; skills and bash follow the capability.
- **Capability:** strict `profiles.json` schema; `local_key()` maps an `installs.json` entry to the curated entry id and bits, and a searched GGUF has no key; key matching on bits, window, llama.cpp tag and `same_as`; `derive()` at each threshold edge, case-level bounds against hand-worked tables, the free agent granted on `agent_smoke` and `free_agent_tasks` alone and then held to `agent_job` once it has free-agent results, a gate failure in either family blocking the free agent, `skill_choice` limiting the list and never more than three skills, an Office format kept on `exec()` on a local model whose builder scores below its `exec_baseline` and moved to the builder at or above it, `languages` carried from the row to the job, every reason a `Reason` with a known code, bash `ask` only on remote free agents with zero unsafe asks, the window floor formula, the ChatGPT and short-window gates; the unmeasured default keeps today's formats, offers rung 1 on the five spec-backed formats and offers no run of a `needs_passing_row` job; a confirmation survives switching models away and back; `capability_of()` and `_availability()` make no network call and load no model (a test fails any provider call); `SelectedModel.tier` unchanged and `ResolvedGeneration.tier` preferring the profile; `test_engine_choice.py` rewritten against `selected_engine`, including a `requested` engine the capability allows, one it does not (a coded 409) and `None` taking `default_engine`; the release rule fails on a default model below the bar.
- **Turn registry** (`tests/unit/agent/test_active_turns.py`): a turn is registered when it starts streaming and removed in `finally` on success, error and abort; spend scope with one streaming turn names it and with two names their sum.
- **Spend:** migration test for the new revision; caps survive a model switch; the monthly sum over a month boundary; an OpenAI-compatible stream with a usage chunk writes reported tokens, one without writes an estimate; `estimate_job` from medians and "not measured"; Studio and a workflow stop before a call over the cap.
- **Harness self-tests:** `grade` refuses to run until `selftest` passes on the negative controls; `summary` refuses to mark a frontier column complete while a failed case has no triage label; the agent driver's no-Python mode leaves neither `python` nor `py` resolvable in opencode's shell; the judge counts only after full calibration agreement; pass^k and the cluster bootstrap checked against hand-worked tables; a committed row without a packaged build version is refused by `publish`.
- **Live, opt-in:** `tests/live/test_anthropic_native.py`, skipped without `SURFSENSE_EVAL_ANTHROPIC_KEY`: a cache read on the second call, an enforced schema, `count_tokens` matching `usage.input_tokens`.
- **Runtime:** `plan_load` chooses `q8_0` for `min_window` only when `flash_attention` is true, and never widens past the live cap; a live window below the floor blocks an agent turn with the reason and leaves the capability unchanged; `create_artifact` defers on the local route; an aborted turn releases its workspace's deferred jobs; with two concurrent turns in one workspace, release waits for the second; startup releases leftovers.
- **Bundles:** a default bundle from a run on a fixture contract contains none of the contract's text (checked against every 8-word sequence of the fixture), and includes it only under the tick.

## What this changes in existing ADRs and proposals

**New ADRs** (numbers follow the [README](README.md#adrs-to-write-or-amend)'s order):
- **ADR 0043**, "Claude goes through Anthropic's Messages API." It amends [ADR 0015](../../adr/0015-openai-compatible-connections.md): a connection's wire follows its host and `auth_kind`, derived in `wire.py`. Anthropic's host speaks Messages for chat, Studio and the agent.
- **ADR 0044, written with [06](06-product-shape.md)**, "What a model may do comes from a reviewed, measured capability manifest." It extends [ADR 0014](../../adr/0014-two-tier-model-catalog.md) with a third reviewed manifest, records that the prompt tier is prompt shape only, that an unmeasured model keeps today's behaviour, and that committed rows come from packaged builds. 06 adds one workspace kind, that a verdict reflects eval rows and live gates only, that the license never changes a verdict, and that an organization policy may only lower one.

**Proposals and architecture docs:**
- [`01-which-engine.md`](../agent/01-which-engine.md):
  - the Decision's "tested list" becomes the capability's free-agent grant, plus the per-model untested confirmation;
  - "What tested means" becomes `agent_smoke` plus the `free_agent_tasks` gate, and the `agent_job` gates once measured;
  - "a quick question also goes through the agent" is amended, not reversed: the capability's `default_engine` keeps new threads on the chat engine on paths without prompt caching, and 06 decides the switch;
  - the prompt-cache check generalizes to `cache_read_input_tokens` on remote routes;
  - its open questions on where the list lives and who maintains it are answered.
- [Agent README](../agent/README.md), Locked decisions:
  - "Who gets opencode" becomes "models whose capability grants the free agent or a job thread, or that the user confirms as untested";
  - "A thread gets its engine when it is created … and keeps it" stands; the fallback ladder is built to keep it (decision 12);
  - "Models: one SurfSense endpoint" stands, now with two wires on it.
- [`04-workflows.md`](../agent/04-workflows.md):
  - decision 4 triggers on the measured `schema` result per route, not on models.dev's `structured_output`;
  - "Where Studio stands" is corrected: `run_model()` already sends `reasoning=False` and a schema for quiz and flashcards.
- [`chat-eval.md`](../chat-eval.md) becomes the `grounded_qa` family; Featherless is demoted to screening; the `anthropic` and `openai_compatible` targets are added; its 1.7B figures are committed as a summary or marked unpublished.
- [selection](../../architecture/local-models/selection.md) and [connections](../../architecture/connections.md) document the wire and the tier's new source.
- [agent](../../architecture/agent.md): its pointer to "the agent test" becomes `agent_smoke` and the capability rule in section 4. Known gaps: the entries on the empty list and the missing agent test are closed by P4a and P4b, and Studio blocking the agent by P5a.
- [`enabled.mjs`](../../../surfsense_local/electron/scripts/opencode/enabled.mjs): the comment points at `agent_smoke` and the capability rule instead of "the agent test". `ENABLED_BY_DEFAULT` becomes `true` in M5, on the evidence named under Wiring in section 4.
- [ADR 0016](../../adr/0016-no-telemetry.md) is unchanged. Run bundles and the self-test follow its "support runs on logs the user sends".

## Dependencies on other areas

- [01 Sources and folders](01-sources-and-folders.md): the folder-scale fixture and server-side scoping for `folder_qa` and the 200-file `free_agent_tasks` case; per-thread tool registration, which names the thread in deferred Studio jobs; a window-sized `gather()` budget (`budget_chars`) before any `long_context` family; `chat_threads.source_scope` and each user turn's recorded scope for replays and run bundles.
- [02 Skills and engines](02-skills-and-engines.md): the clean-room phase 0 (re-sourced XSDs, the graders in `document_skills/graders/`, the fixture licence check), the engines as tools, the job agents `surfsense-job-<key>` with each skill as the agent's prompt and their compaction test, `start_workflow()`, and the Office spec builders of phase B, which delete `runner.py` only after P0 has recorded the `exec()` baseline. This document supplies the `Capability` that 02's `policy_for()` reads: `AgentSetup.skills`, the workflows a model may run, bash per thread kind and the window floor.
- [03 Editable artifacts](03-editable-artifacts.md): versions and specs for `edit_session`; Refine, selection edits and revised copies for the rung families; phase 3, which turns agent files into versions, before the M5 switch-on and for grading `free_agent_tasks`. This document supplies the rungs per model (`capability_of(session).formats`, `edit_rungs`) and the unmeasured default its edit entry points read, and owns the `active_turns` registry.
- [04 Runtime and packs](04-runtime-and-packs.md): the Anthropic SDK in both binaries, the llama.cpp bump under the size gate, the opencode pin (its decision 20), the packaged worker and staged opencode the committed runs use. This document supplies the matrix evidence 04's decision 5 waits on before any Python goes on the agent's `PATH`.
- [06 Product shape](06-product-shape.md): how the capability, its verdicts and `Reason` codes, the untested confirmation, the Answer / Work on files switch, each job's supported languages and the spend estimate appear; `apply_org_policy()`, which runs last in `capability_of()`. 06's S1 builds on P4a, and its "Test this model" fix waits for P6. This document supplies `Capability` and `selected_engine(session, requested)`; 06 decides the surface.
- [README](README.md): the milestones these phases land in, the `ENABLED_BY_DEFAULT` flip and its macOS condition, the whole-stack memory budget on the integrated-graphics laptop, and the eval budget.

## Open questions

1. Who provides the 24–32 GB machine for committed 27–35B rows and the 16 GB Windows laptop with integrated graphics, and who confirms the 16 GB M4 figures? The [README](README.md) names an owner and a chase date for each. Until then those rows stay screened only, and community `matrix` submissions (section 9) are the other route.
2. Is about $650 per full frontier sweep and a $300 monthly cap outside sweeps acceptable (estimated, section 5), and which accounts hold the Anthropic, OpenAI, Google and OpenRouter eval keys and the `model-evals` environment's reviewers? The [README](README.md)'s maintainer question 4 recommends a dedicated Anthropic workspace and these figures.
3. Haiku 4.5's retirement is "not sooner than" 2026-10-15. M1 re-runs the contract-redline and docx baselines on Haiku 4.5 and on Sonnet 5.5 at low effort, n=3, before that date, so a baseline survives either way. If Haiku goes, does the skills project's executor move to Sonnet 5.5 at low effort, and does the bottom Claude rung become Sonnet at low effort?
4. Is $5 the right default per-job cap on every remote route, given that open models on OpenRouter cost a fraction of Claude?
5. Does `b11050` load Qwen3.5/3.8 and Gemma 4 GGUFs, or does the catalog update wait on a llama.cpp bump?
6. Should Studio's 24,000-character grounding and chat's five passages grow with the window for capabilities that would pass a `long_context` family? That change is [01](01-sources-and-folders.md)'s `gather()` budget; this area adds the family once it exists.
7. Should OpenRouter's Claude rows inherit native rows through `same_as` after a smoke run, or be measured in full, given that the route differs on caching and schemas?
8. Does `@ai-sdk/openai-compatible` in opencode 1.18.34 honour `includeUsage`, and which catalog providers refuse `stream_options`?
