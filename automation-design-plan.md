# SurfSense Automation Feature — Design Plan (v2)

A generic, extensible automation system for SurfSense that lets users (and
future SurfSense features) trigger agent work on a schedule, on an external
event, or on demand — with the ability to author automations either by hand
or from a natural-language description that yields an editable, structured
definition.

This document supersedes the v1 draft. It folds in the design audit pass and
the corrections from working through worked examples (notably: removing the
connector bias, clarifying the executor's role, integrating MCP cleanly, and
committing to JSON Schema as the single declarative language).

---

## 1. The load-bearing principle

> **The JSON definition is the program. Everything else is interpreter.**

Every decision in this document serves that principle. If we ever face a
design choice and one option lets some behavior leak out of the definition
into the engine, we pick the other option.

Three properties follow from this principle, and they're the reason the
system will survive feature growth:

- **Reproducibility** — same definition + same inputs → same observable
  behavior, regardless of which version of the engine runs it.
- **Portability** — definitions can be exported, imported, version-
  controlled, code-reviewed, and shared across SurfSense instances.
- **LLM tractability** — the NL authoring flow works because the LLM only
  needs to produce a self-contained JSON document that validates against a
  schema. It doesn't need to understand the engine.

---

## 2. The four-layer contract

The system is structured as four layers. Layers 1, 2, and 4 are defined by
SurfSense developers (at registration time). Layer 3 is what users write
(or the NL generator produces). The runtime reads all four to do its job.

| Layer | What it is | Defined by |
| ----- | ---------- | ---------- |
| **1. Capability registry** | What this SurfSense instance can do | Developers, at startup |
| **2. Action contract** | Per-action input/output schema | Developers, at startup |
| **3. Automation definition** | One concrete saved automation | Users (or NL generator) |
| **4. Trigger contract** | Per-trigger config and payload schemas | Developers, at startup |

Each layer constrains the one above. The runtime reads all four but doesn't
know what's in them ahead of time. That's how a new capability or trigger
type becomes available across the engine without code changes outside its
registration.

### Schema language

Every shape in every layer is described in **JSON Schema (draft 2020-12).**
No exceptions, no parallel languages, no inline shorthand. Two documented
extensions on top:

- `default: "$some_token"` — runtime-resolved defaults. The vocabulary is
  fixed: `$last_fired_at`, `$creator`, `$space_default`. The engine resolves
  these to values before validation.
- `x-surfsense-*` annotations — editor hints (widget type, autocomplete
  source). The validator ignores them; the form editor reads them.

---

## 3. Capability registry (Layer 1)

A `Capability` is one discrete thing the SurfSense backend exposes —
"post a Slack message," "query the Search Space," "generate a podcast." It
is the atomic unit of "things automations can do."

```python
@dataclass
class Capability:
    id: str                                # "slack.post_message"
    name: str                              # "Post Slack message"
    description: str                       # for the NL generator
    input_schema: dict                     # JSON Schema
    output_schema: dict                    # JSON Schema
    required_credentials: list[CredSpec]   # what creds the handler needs
    side_effects: set[SideEffect]          # READ, WRITE, EXTERNAL_WRITE,
                                           # COST_INCURRING, USER_VISIBLE
    expected_duration_seconds: int         # estimate or upper bound
    cost_estimate: Callable[[dict], Decimal]  # f(input) → estimated USD
    handler: AsyncHandler
```

### Where capabilities live: a two-tier registry

The capability registry has different storage requirements for different
kinds of capabilities. **Native capabilities and MCP capabilities have
different lifecycles**, so they're persisted differently:

| Tier | What's there | Where it lives | Lifetime |
| --- | --- | --- | --- |
| **Native** | Capabilities defined in SurfSense's codebase (`search_space.query`, `agent.run`, etc.) | In-memory dict, populated at startup from `automations/capabilities/native.py` | Process lifetime, identical across all workers |
| **MCP (durable)** | The fact that this SearchSpace has connected to this MCP server, the tool list it exposes, credentials | PostgreSQL: `mcp_connections` and `mcp_tools` tables | Persistent across restarts and across time |
| **MCP (cached)** | Handler closures wrapping `(connection_id, tool_name)` | Per-worker in-memory cache, lazily built from the database on first reference | Process lifetime, rebuilt on demand |

The reason this matters: **a user connects an MCP server on Monday, writes
an automation on Tuesday, the automation runs on Friday.** Between Monday
and Friday, workers will restart many times. Any state that only lives in
worker memory is gone. The closures generated at connection time would
not survive.

So we split persistence by lifecycle:

- Native capability handlers live in the codebase. Always available, no
  need for the database.
- MCP capability metadata lives in the database, so the knowledge "this
  SearchSpace has these capabilities" survives any restart.
- The actual closures are built on demand from the database state. They
  live in worker memory only until the worker dies, at which point they
  get rebuilt by the next worker that needs them.

### MCP database schema

```sql
CREATE TABLE mcp_connections (
    id                UUID PRIMARY KEY,
    search_space_id   INT REFERENCES search_spaces(id),
    server_url        TEXT,
    transport         TEXT,                  -- "http", "stdio", etc.
    name              TEXT,                  -- "Slack (Acme workspace)"
    access_token      BYTEA,                 -- encrypted at rest
    refresh_token     BYTEA,                 -- encrypted at rest
    expires_at        TIMESTAMPTZ,
    last_harvested_at TIMESTAMPTZ,
    created_at        TIMESTAMPTZ,
    created_by        INT REFERENCES users(id)
);

CREATE TABLE mcp_tools (
    id              UUID PRIMARY KEY,
    connection_id   UUID REFERENCES mcp_connections(id) ON DELETE CASCADE,
    name            TEXT,                    -- "post_message"
    description     TEXT,
    input_schema    JSONB,
    output_schema   JSONB,
    side_effects    TEXT[],                  -- inferred or admin-curated
    UNIQUE (connection_id, name)
);
```

### MCP lifecycle: connect, harvest, invoke

Three phases, each with distinct concerns.

**Phase 1 — Connect (one-time, on user action).** User clicks "Connect
Slack MCP." OAuth flow completes. A row is added to `mcp_connections`
with the encrypted tokens.

**Phase 2 — Harvest (right after connect, also re-runnable).** SurfSense
opens a temporary client to the MCP server, calls `tools/list`, and writes
one row to `mcp_tools` per discovered tool. The temporary client is then
discarded; only the database state persists.

```python
async def harvest_mcp_server(connection_id: UUID, ctx):
    connection = await ctx.db.get(MCPConnection, connection_id)
    client = build_temporary_client(connection)
    tools = await client.list_tools()
    
    # Replace existing tool rows for this connection
    await ctx.db.execute(
        delete(MCPTool).where(MCPTool.connection_id == connection_id)
    )
    for tool in tools:
        ctx.db.add(MCPTool(
            connection_id=connection_id,
            name=tool.name,
            description=tool.description,
            input_schema=tool.inputSchema,
            output_schema=tool.outputSchema,
            side_effects=infer_side_effects(tool),
        ))
    connection.last_harvested_at = now()
    await ctx.db.commit()
```

Harvesting can be re-run on a schedule (say, daily) or on user request,
to pick up new tools the server has added.

**Phase 3 — Invoke (every time a step references an MCP capability).**
This is where the closure gets built. The executor calls
`ctx.get_capability("slack.post_message")`. The worker's in-memory cache is
checked; on miss, the database is queried:

```python
async def get_capability(capability_id: str, ctx: ActionContext) -> Capability:
    cached = _WORKER_CAPABILITY_CACHE.get((ctx.search_space.id, capability_id))
    if cached:
        return cached
    
    if is_native(capability_id):
        capability = _NATIVE_REGISTRY[capability_id]
    else:
        # MCP path: look up tool metadata
        tool_row = await ctx.db.execute(
            select(MCPTool)
            .join(MCPConnection)
            .where(MCPConnection.search_space_id == ctx.search_space.id)
            .where(tool_qualified_name(MCPTool, MCPConnection) == capability_id)
        )
        capability = Capability(
            id=capability_id,
            input_schema=tool_row.input_schema,
            output_schema=tool_row.output_schema,
            side_effects=set(tool_row.side_effects),
            handler=make_mcp_handler(
                connection_id=tool_row.connection_id,
                tool_name=tool_row.name,
            ),
        )
    
    _WORKER_CAPABILITY_CACHE[(ctx.search_space.id, capability_id)] = capability
    return capability
```

The closure created by `make_mcp_handler` captures only the connection ID
and tool name. When invoked, it asks `ctx.resolve_mcp_client(connection_id)`
to build an authenticated client from the connection record (including
token refresh if needed). That client is also transient — built per call,
discarded after.

### Credentials: resolved at the moment of use

The handler doesn't carry credentials and the closure doesn't capture them.
When invoked, the handler asks `ActionContext` for what it needs:

```python
def make_mcp_handler(connection_id: UUID, tool_name: str):
    async def handler(ctx: ActionContext, args: dict) -> Any:
        # Credential resolution happens here, per call
        client = await ctx.resolve_mcp_client(connection_id)
        response = await client.call_tool(name=tool_name, arguments=args)
        return response.content
    return handler
```

`ctx.resolve_mcp_client(connection_id)`:
1. Loads the `mcp_connections` row
2. Decrypts the access token
3. Refreshes the token if it's expired (using the refresh token)
4. Constructs an `MCPClient` with the token set as a default authorization
   header

The HTTP library carries the auth header on every subsequent call the
client makes — the handler doesn't think about it after construction.

For native capabilities calling external APIs directly,
`ctx.resolve_http_client(provider)` returns an authenticated `httpx`
client. For LLM operations, `ctx.resolve_llm(provider)` returns a
configured LLM client. **Three resolution methods, one pattern: the
context returns a client already authenticated.**

Three properties this gives us:

- **Credentials never appear in the automation definition.** The JSON
  contains capability references and connection IDs, never tokens.
- **Credentials never appear in the LLM's context.** Even during
  `agent_task`, the LLM sees tool descriptions only; the host holds
  credentials and uses them when executing the tools the LLM requests.
- **Credentials are loaded per-call, not pre-loaded.** The credential
  exists in memory only during the moment a handler is making a call. No
  long-lived secrets in worker memory.

---

## 4. Action contract (Layer 2)

An `Action` is what a user references in a plan step. Most actions are
thin wrappers around one capability (e.g., `slack_post` wraps
`slack.post_message`). Some compose: `agent_task` is one action whose
handler invokes the LangGraph runtime, which in turn can call many
capabilities.

```python
@dataclass
class ActionDefinition:
    type: str                              # "agent_task", "slack_post"
    name: str                              # for the UI
    description: str                       # for the NL generator
    config_schema: dict                    # JSON Schema for action.config
    output_contract: dict | DynamicOutput  # what it produces
    uses_capabilities: list[str]           # IDs from the registry
    produces_artifacts: list[ArtifactSpec] # see §8
    handler: AsyncHandler
```

### Tight vs loose actions

Two patterns coexist by design:

- **Tight actions** (`slack_post`, `linear_create_issue`, `send_email`):
  config_schema is fully specified, output_contract is fixed, handler is a
  thin wrapper. ~20 LOC each. Used when the user knows exactly what they
  want done — no LLM tokens spent on trivial work.

- **Loose actions** (`agent_task`): config_schema accepts a `prompt` and a
  `tools` allowlist; output_contract is *dynamic* — the user declares the
  output shape they want via `output_schema` in the step config; the
  handler asks the LLM to return that shape and validates. Used when
  judgment is needed.

The agent's tool list is **the same capabilities** that tight actions call
directly. One registry, two invocation modes. Adding a new MCP server gives
both modes access to its tools automatically.

### How names in the definition become function calls

The definition contains strings like `"action": "slack_post"`. The string is
just a name — it does not point to a function. At runtime, the executor
performs a **name-based lookup** against the action registry:

```python
# step.action is a string from the JSON definition, e.g. "slack_post"
action_def = _ACTION_REGISTRY[step.action]   # dict lookup
handler = action_def.handler                  # Python callable
result = await handler(ctx, resolved_config)  # invocation
```

The registry is a Python dict (or a thin wrapper around one) populated at
process startup. Each entry in `automations/actions/*.py` calls a
`register_action(...)` function at module import time, putting its
`ActionDefinition` (including the handler function reference) into the
registry.

The same pattern applies to capabilities. The definition references
capabilities by ID (`"slack.post_message"`); the capability registry maps
the ID to a `Capability` object holding the handler. Definitions never
reference Python code directly — they reference names that the registry
resolves to code.

This separation is what makes the contract portable. The definition is
pure data. The registry is the engine's runtime vocabulary. They meet at
name-based lookup; nothing else crosses the boundary.

### The full expressive spectrum

The contract supports a continuous spectrum from purely deterministic to
fully agentic. Six practical shapes worth recognizing:

| Shape | Example | Cost / latency profile |
| --- | --- | --- |
| **1. Direct call** | `slack_post` with literal channel and template | No LLM. ~200ms. Fractions of a cent. |
| **2. Direct call with computed inputs** | `linear_create_issue` using `{{summary.title}}` from a prior step | No LLM for this step. Cheap. |
| **3. Single-domain agent task** | `agent_task` with `tools: ["slack.*"]` only | One LLM, bounded toolset. |
| **4. Multi-domain agent task, narrow** | `agent_task` with `tools: ["github.list_pull_requests", "linear.create_issue"]` | One LLM, named capabilities. |
| **5. Multi-domain agent task, broad** | `agent_task` with `tools: ["slack.*", "github.*", "linear.*"]` | One LLM, large toolset, most agentic. |
| **6. Composed plan** | `agent_task` (narrow) for thinking → `slack_post` + `linear_create_issue` for acting | Best cost-to-power ratio. |

Shape 6 is the underrated one and the cost-and-speed answer. The agent
reasons once (Shape 3 or 4) and its structured output drives several
deterministic actions. This is roughly 5–10x cheaper and 3–4x faster than
forcing the agent to do everything (Shape 5) and produces the same outcome.

**The NL generator's job is to propose Shape 6-style plans by default.**
The Review LLM flags proposals that use `agent_task` for steps a
deterministic action could handle. This is the discipline that keeps
automations cheap at scale.

The user navigates the spectrum by intent (describing what they want), not
by mechanism — the shape selection is the engine's responsibility, not the
user's.

---

## 5. Automation definition (Layer 3)

This is the JSON the user writes (or the NL generator produces). Stored in
`automations.definition` as JSONB.

### Top-level shape

```jsonc
{
  "schema_version": "1.0",
  "name": "Daily competitor digest",
  "goal": "Summarize new competitor content and post to Slack",

  "inputs": {
    "schema": {
      "type": "object",
      "required": ["since"],
      "properties": {
        "since": { "type": "string", "format": "date-time",
                   "default": "$last_fired_at" },
        "tags":  { "type": "array", "items": { "type": "string" },
                   "default": ["competitor"] }
      }
    }
  },

  "triggers": [
    {
      "type": "schedule",
      "config": { "cron": "0 9 * * 1-5", "timezone": "Africa/Kigali" }
    }
  ],

  "plan": [
    {
      "step_id": "research",
      "action": "agent_task",
      "config": {
        "prompt": "Find documents tagged {{inputs.tags}} indexed since {{inputs.since}}. Return JSON with bullets and source_doc_ids.",
        "tools": ["search_space.query", "search_space.fetch_document"],
        "model": "anthropic/claude-sonnet-4-7",
        "output_schema": {
          "type": "object",
          "required": ["bullets", "source_doc_ids"],
          "properties": {
            "bullets":        { "type": "array", "items": { "type": "string" } },
            "source_doc_ids": { "type": "array", "items": { "type": "string" } }
          }
        }
      },
      "output_as": "summary"
    },
    {
      "step_id": "deliver",
      "action": "slack_post",
      "config": {
        "channel_id": "C0123",
        "message_template": "*Competitor digest*\n\n{% for b in summary.bullets %}• {{b}}\n{% endfor %}"
      }
    }
  ],

  "execution": {
    "timeout_seconds": 600,
    "max_retries": 2,
    "retry_backoff": "exponential",
    "concurrency": "drop_if_running",
    "budget_cap_usd": 1.50,
    "on_failure": [ /* steps to run if main plan fails after retries */ ]
  },

  "metadata": { "tags": ["digest"], "created_from_nl": true }
}
```

### Plan steps

```jsonc
{
  "step_id": "...",                      // unique within plan
  "action": "...",                       // references an ActionDefinition.type
  "when": "{{ ... }}",                   // optional Jinja expr → bool; false = skip
  "config": { ... },                     // validated against action's config_schema
  "output_as": "...",                    // binds output to this name for later steps
  "max_retries": 0,                      // optional, overrides automation default
  "timeout_seconds": 1200                // optional, overrides automation default
}
```

Steps run **sequentially**. No parallelism, no DAGs, no loops. If a user
needs branching, they use `when:` on multiple steps. If they need
parallelism or iteration, they use `agent_task` and let the agent reason
about it, or they compose automations through events (§7.5).

---

## 6. Trigger contract (Layer 4)

Three trigger types. That's the entire taxonomy.

### `schedule`

```python
TriggerDefinition(
    type="schedule",
    config_schema={
        "type": "object",
        "required": ["cron", "timezone"],
        "properties": {
            "cron":     { "type": "string" },
            "timezone": { "type": "string", "format": "iana-timezone" }
        }
    },
    payload_schema={
        "type": "object",
        "properties": {
            "fired_at":      { "type": "string", "format": "date-time" },
            "scheduled_for": { "type": "string", "format": "date-time" },
            "last_fired_at": { "type": "string", "format": "date-time" }
        }
    }
)
```

Implementation: extends `app/utils/periodic_scheduler.py`, which already
reads connector sync schedules. Adds a second source — `automation_triggers
WHERE type='schedule'`. Same Celery Beat checker, two source tables.

Minimum interval: 1 minute (the existing checker's resolution). The form
editor warns when users set intervals under 15 minutes that they probably
want an event trigger instead.

### `webhook`

```python
TriggerDefinition(
    type="webhook",
    config_schema={
        "type": "object",
        "properties": {
            "input_mapping": {
                "type": "object",
                "additionalProperties": { "type": "string" }
                # values are JSONPath expressions
            }
        }
    },
    # payload is whatever the POST body is; user-defined shape via mapping
)
```

Endpoint: `POST /api/v1/automations/{id}/fire`. Bearer token shown once,
hashed at rest, rotatable, revocable. Returns `202 Accepted` with the
created run's URL. Caller polls for status; we do not push callbacks in
v1 (a `callback_webhook` action can be added later).

Idempotency: honors `Idempotency-Key` header or `idempotency_key` in body.
Dedups against runs in the last 24 hours.

### `event`

```python
TriggerDefinition(
    type="event",
    config_schema={
        "type": "object",
        "required": ["event_type"],
        "properties": {
            "event_type": { "type": "string" },   # e.g. "drive.file_added"
                                                   # or "surfsense.podcast.generated"
            "filters":    { "$ref": "#/definitions/filter_expression" }
        }
    }
    # payload shape is documented per event_type in a separate registry
)
```

**Events absorb both connector events and internal SurfSense events.** A
file added to Drive and a podcast finishing in SurfSense are both events
in the same `domain_events` table, both subscribable by automations, both
matched by the same dispatcher code. The engine doesn't distinguish.

### Filter grammar

Filters are JSON-structured operators, not expressions. This is the one
place we deliberately don't use Jinja, because filters run on a hot path
(every event matched against every subscribing trigger) and structured
filters can be indexed and short-circuited.

Vocabulary:
- Equality: `equals`, `not_equals`
- String: `starts_with`, `ends_with`, `contains`, `regex`
- Numeric: `gt`, `gte`, `lt`, `lte`
- Set: `in`, `not_in`
- Existence: `exists`
- Composition: `$and`, `$or`, `$not`

Inspired by AWS EventBridge and MongoDB query syntax. The filter grammar
itself is published as a JSON Schema, so users get inline error messages.

---

## 7. Runtime components

Each component is distinct, replaceable, and has one job.

### 7.1 Dispatcher

What it does: matches firing triggers to automations, creates `AutomationRun`
rows, enqueues executor tasks.

For schedule triggers: Celery Beat polls the trigger table, computes due
ones, fires.

For webhook triggers: the FastAPI handler is the dispatcher entry point.
Validates token, runs input_mapping, creates run.

For event triggers: subscribes to the `domain_events` table. For each new
event, evaluates all matching triggers' filters, fires the matches.

Common path (after a trigger has fired):
1. Resolve `inputs` from trigger payload and defaults
2. Validate resolved inputs against the automation's input schema
3. **Cost estimate** — sum capabilities' `cost_estimate(args)` for the plan;
   refuse if exceeds `budget_cap_usd`
4. **Idempotency check** — dedup against existing pending/running runs
5. **Snapshot the resolved definition** into the run row (immutable history)
6. Enqueue executor task on the appropriate Celery queue (per
   `expected_duration_seconds`)

### 7.2 Executor

What it is: **a Celery task wrapping a single function that walks a plan
step by step.** Not an agent, not a workflow engine, not a scheduler. A
loop with bookkeeping. Maybe 200 lines.

```python
async def execute_run(run_id: int) -> None:
    run = load_run(run_id); run.status = "running"; save(run)
    context = build_run_context(run)
    step_outputs = {}

    for step in run.plan:
        if step.when and not evaluate_predicate(step.when, context | step_outputs):
            record_step_skipped(run, step); continue

        resolved_config = render_config(step.config, context | step_outputs)
        action = action_registry.get(step.action)
        validate(resolved_config, action.config_schema)

        try:
            result = await with_retries(
                action.handler,
                ctx=build_action_context(run, action),
                args=resolved_config,
                policy=step.retry_policy or run.execution.retry_policy,
            )
            validate(result, step.output_schema)
            if step.output_as:
                step_outputs[step.output_as] = result
            record_step_succeeded(run, step, result)
        except Exception as e:
            record_step_failed(run, step, e)
            await run_on_failure(run, e)
            return

    run.status = "succeeded"; save(run)
    publish_event("automation.run.succeeded", run)   # see §7.5
```

Intelligence lives **inside handlers**, not in the executor. The most
intelligent handler is `agent_task`, which spins up a LangGraph Deep Agent
for one step and returns when the agent finishes. The executor sees a
validated dict come back; it doesn't know that step was "smart."

### 7.3 Action handlers

One handler per `ActionDefinition.type`. Receives `(ctx, args)`, returns
a dict matching `output_contract` (or matching the user-declared
`output_schema` for dynamic-output actions like `agent_task`).

Handlers handle their own credential resolution via `ctx.resolve_credentials`.
They do not know about retries, timeouts, or budget caps — those are the
executor's concern.

### 7.4 Template engine

#### Why it exists

Most fields in an automation definition contain literal strings the user
authored once — but the actual rendered value has to change per run, because
it includes data from the trigger payload or from prior step outputs. The
template engine is what turns `"Daily digest for {{run.started_at}}"` into
`"Daily digest for 2026-05-26"` at run time.

Three fields use it:
- `*_template` strings in tight action configs (Slack messages, email bodies,
  Linear titles, etc.)
- `prompt` in `agent_task` configs (so the agent sees resolved values, not
  `{{...}}` placeholders)
- `when:` step predicates (which need to evaluate to a boolean)

#### Public interface

Single module, ~80 lines. Three public functions — everything else in the
engine routes through these:

```python
def render_template(template: str, context: dict) -> str: ...
def evaluate_predicate(expression: str, context: dict) -> bool: ...
def build_run_context(run, step_outputs) -> dict: ...
```

Backed by Jinja2's `SandboxedEnvironment`. The whole module is the seam: if
the template language is ever swapped, only this file changes.

#### Security architecture: allowlist by default

`SandboxedEnvironment` starts empty. A freshly-created instance gives a
template access to:
- Variables in the context dict we pass in (`run`, `inputs`, prior step
  outputs)
- Public (non-underscore) attributes of those variables
- Jinja's built-in control flow (`{% if %}`, `{% for %}`, `{% set %}`)

Nothing else. No Python builtins, no modules, no I/O, no network, no
filesystem. Everything beyond the above must be **explicitly registered.**
This is the structurally important property: anything we didn't add is
inaccessible. The risk surface equals the size of what we registered.

The three sandbox rules that enforce this:
1. **Attribute access is filtered** — names starting with underscore are
   rejected. This blocks the entire family of `{{x.__class__.__mro__...}}`
   Python escape paths in one rule.
2. **Globals are allowlist-only** — `open`, `eval`, `exec`, `__import__`,
   `getattr`, every module name, are all absent unless we register them.
   We register zero globals.
3. **Unsafe callables are blocked** — `str.format` and `str.format_map`
   specifically (due to CVE-2016-10745), plus anything marked
   `unsafe_callable`.

#### What we register, exactly

- **Filters: a curated 15**, no more. `join`, `length`, `default`, `upper`,
  `lower`, `truncate`, `tojson`, `date`, `replace`, `trim`, `slugify`,
  `first`, `last`, `sort`, `reverse`. Each one is audited for what it does
  with its input; none of them takes a callable, runs `eval`, or reaches
  into Python objects beyond simple data transformation.
- **Globals: none.**
- **Tests: only the safe built-ins** (`defined`, `none`, `number`, `string`,
  `mapping`, `sequence`, `boolean`).

Adding a new filter requires a deliberate code change and review: does this
filter do anything dangerous with its input? If yes, don't add it. The list
only grows by audited additions.

#### Runtime limits (defense in depth)

The sandbox handles the attack surface inside the template language. Three
additional limits handle resource exhaustion that the language permits but
the runtime shouldn't tolerate:

- **Template source length capped at 8 KB.** Checked before parsing.
- **Render time capped at 100 ms per render.** Implemented via a watchdog
  thread; renders that exceed are killed and the step fails. Catches
  `{% for i in range(10**9) %}` and nested loop bombs.
- **Output size capped at 1 MB.** A small template can produce a multi-GB
  string via `{{ 'A' * 10**8 }}`-style multiplication; this catches it.

Plus `StrictUndefined`: any reference to a missing variable raises
immediately rather than silently rendering empty, so misconfigurations
fail fast.

#### Threat model and residual risk

The trust model from day one is:

- Templates are generated by an LLM from a user's natural-language input
  (see §10), or written/edited by humans in the editable form
- A second LLM reviews the proposal and produces a plain-language summary
  plus flagged anomalies for the user
- The user reviews and approves before the automation runs
- The Generator LLM's input is scoped (user prompt + schema + registry
  only — no arbitrary document content), minimizing prompt-injection paths

The sandbox + runtime limits + curated filter list protect against the
malformed-template attack. Human review protects against the
semantically-malicious-but-syntactically-valid attack. These are
complementary layers, not redundant.

Known residual risks, each genuinely small:

- **Future Jinja CVEs.** Historical sandbox bypasses have existed and
  been patched. This is a generic third-party-dependency risk, comparable
  to bugs in any other library we rely on. Mitigation: subscribe to
  security advisories, ship updates within a week of disclosure.
- **Side channels via prompts to LLMs.** A template that renders into a
  prompt can attempt prompt injection of the agent at run time. This is
  not a sandbox concern but a separate concern in `agent_task`'s design.
- **Operator deployments with long-lived secrets in worker env vars.**
  Mitigation: credentials fetched per-handler-per-call via
  `ActionContext.resolve_credentials`, never pre-loaded into worker
  env vars accessible to templates.

The sandbox-with-allowlist architecture means **the attack surface
equals the set of things we registered.** With zero globals registered
and 15 audited filters, the surface is small, bounded, and reviewable.
This is the structural property that makes the architecture sound, and
it doesn't depend on hypothetical assumptions about who authors templates.

#### Pre-Phase-5 gate

One trust-model change is documented in the roadmap: **Phase 5 introduces
template sharing across SearchSpaces** (automation templates as
exportable, importable artifacts). At that point, the *approver* of a
template (the original author) is no longer the *runner* (the importer).
The "human reviews before save" mitigation breaks down because the
reviewer doesn't bear the risk.

Before Phase 5 ships, this needs an explicit re-approval flow: importing
a template triggers a fresh review pass by the importing user, with the
flagged-anomalies output prominently displayed, and the import cannot
complete without explicit per-template approval.

This is a UX/flow decision, not a template-language migration. Jinja
itself stays; what changes is the approval workflow at the import boundary.

#### The `run.*` namespace exposed in every template

```
run.id, run.started_at, run.automation_id, run.automation_name,
run.automation_version, run.trigger_type, run.trigger_id,
run.search_space_id, run.creator_id, run.attempt,
run.failed_step_id, run.error.*   (only in on_failure context)
```

#### Default value rendering

Non-string template values render as JSON by default (via the `finalize`
hook): lists become `["a", "b"]`, dicts become `{"k": "v"}`, datetimes
become ISO 8601. The `| join`, `| length`, `| tojson` filters give explicit
control. Strings render as themselves with no quoting. `None` renders as
empty string in templates, as `null` in JSON contexts.

### 7.5 Event bus

`domain_events` table, polled by Celery Beat alongside the existing
scheduler. Both connector events and internal SurfSense events publish to
it. Both are consumed by the dispatcher's event-trigger subscriber.

**Automations themselves publish events.** Successful and failed runs emit
`automation.run.succeeded` / `automation.run.failed` events with the run
metadata. This makes automations composable through events — chain them by
subscribing one automation's event trigger to another's run event. No new
mechanism; the trigger filter and event publishing already exist.

Upgrade path documented: when throughput or latency demands it, replace
PostgreSQL polling with Redis Streams. The `events.publish()` and
`events.subscribe()` interfaces stay the same. Nothing else changes.

---

## 8. Cross-cutting concerns

### Concurrency policy

Per-automation `concurrency` field controls what happens when a new fire
occurs while a previous run is still running:

- `drop_if_running` — silently skip the new fire
- `queue` — execute serially, in arrival order
- `allow_parallel` — start a new run independently

The dispatcher enforces this before enqueueing.

### Retry policy

Three fields, per-automation defaults with optional per-step overrides:
- `max_retries`: integer, 0–10
- `retry_backoff`: `none` | `linear` | `exponential`
- `timeout_seconds`: integer

Retries on:
- Capability handler exceptions
- Output schema validation failures (for dynamic-output actions, the
  validation error is fed back to the LLM in the retry)

Not retries:
- `when:` evaluation failures (these are user errors, surface immediately)
- Input validation failures (caught at dispatch, never reach the executor)

### Budget enforcement

`budget_cap_usd` is per-run. The dispatcher refuses to enqueue if estimated
cost exceeds it. The executor kills the run if accumulated cost crosses it
mid-flight (the LLM ops handler reports tokens consumed back to the
executor between calls).

### On-failure handlers

`execution.on_failure` is a list of steps that run after the main plan has
failed and all retries are exhausted. Same step shape as the main plan.
Cannot have their own `on_failure`. See `run.error.*` in the run context.

### Artifacts

Actions that produce artifacts declare `produces_artifacts: list[ArtifactSpec]`:

```python
@dataclass
class ArtifactSpec:
    kind: str           # "audio", "document", "image", "data"
    retention: str      # "transient" | "default" | "permanent"
    visibility: str     # "private" | "search_space" | "shared"
```

The engine handles storage (writes to SurfSense's existing object storage),
URL generation (signed, scoped to the run's permissions), and cleanup (a
nightly Celery Beat task deletes expired artifacts).

### Duration classes and queue routing

Capabilities declare `expected_duration_seconds`. The dispatcher routes
runs to Celery queues based on the longest-duration step:
- < 10s → `automations_fast`
- 10s – 5min → `automations_medium`
- 5min – 1hr → `automations_long`

Operators scale each queue's worker pool independently. A future "very
long" queue is a config change, not a contract change.

---

## 9. Data model

Six tables. All scoped by `search_space_id` for RBAC.

The first four (`automations`, `automation_triggers`, `automation_runs`,
`domain_events`) are the engine's own state. The last two
(`mcp_connections`, `mcp_tools`) hold the durable knowledge that backs
MCP-derived capabilities — see §3 for the lifecycle rationale.

### `automations`

| field             | type                                | notes                                                                      |
| ----------------- | ----------------------------------- | -------------------------------------------------------------------------- |
| `id`              | int PK                              |                                                                            |
| `search_space_id` | FK → `search_spaces.id`             |                                                                            |
| `created_by`      | FK → `users.id`                     | runs execute as this identity                                              |
| `name`            | str                                 |                                                                            |
| `description`     | str                                 |                                                                            |
| `status`          | enum                                | `active`, `paused`, `archived`                                             |
| `definition`      | jsonb                               | the editable structured spec                                               |
| `version`         | int                                 | bumped on every edit                                                       |
| `created_at` / `updated_at` | timestamps                |                                                                            |

### `automation_triggers`

| field           | type                                                                          | notes                                       |
| --------------- | ----------------------------------------------------------------------------- | ------------------------------------------- |
| `id`            | int PK                                                                        |                                             |
| `automation_id` | FK                                                                            |                                             |
| `type`          | enum: `schedule`, `webhook`, `event`                                          |                                             |
| `config`        | jsonb                                                                         | validated against trigger's `config_schema` |
| `enabled`       | bool                                                                          |                                             |
| `secret_hash`   | str / null                                                                    | for webhook bearer tokens                   |
| `last_fired_at` | timestamp                                                                     |                                             |

### `automation_runs`

| field             | type                                                                         | notes                                              |
| ----------------- | ---------------------------------------------------------------------------- | -------------------------------------------------- |
| `id`              | int PK                                                                       |                                                    |
| `automation_id`   | FK                                                                           |                                                    |
| `trigger_id`      | FK / null                                                                    | null = manual via UI                               |
| `status`          | enum                                                                         | `pending`, `running`, `succeeded`, `failed`, `cancelled`, `timed_out` |
| `definition_snapshot` | jsonb                                                                    | the definition as it was when this run fired       |
| `trigger_payload` | jsonb                                                                        |                                                    |
| `resolved_inputs` | jsonb                                                                        |                                                    |
| `step_results`    | jsonb                                                                        | array of per-step results with timing              |
| `output`          | jsonb / null                                                                 |                                                    |
| `artifacts`       | jsonb                                                                        | references to created artifacts                    |
| `error`           | jsonb / null                                                                 |                                                    |
| `cost_usd`        | decimal                                                                      | accumulated cost                                   |
| `started_at` / `finished_at` | timestamps                                                        |                                                    |
| `agent_session_id`| str / null                                                                   | link to LangGraph trace if agent_task was used     |

### `domain_events`

| field             | type        | notes                                              |
| ----------------- | ----------- | -------------------------------------------------- |
| `id`              | UUID PK     |                                                    |
| `search_space_id` | FK          | scoping                                            |
| `event_type`      | varchar     | e.g. `drive.file_added`, `automation.run.succeeded` |
| `source_id`       | varchar     | which connector/automation/etc. produced it        |
| `payload`         | jsonb       | matches the event type's documented schema         |
| `created_at`      | timestamp   |                                                    |
| `consumed_by`     | jsonb       | array of consumer_ids, for tracking + replay       |
| `expires_at`     | timestamp   | auto-cleanup after 7 days                          |

### `mcp_connections`

Persistent record of MCP server connections per SearchSpace.

| field               | type        | notes                                              |
| ------------------- | ----------- | -------------------------------------------------- |
| `id`                | UUID PK     |                                                    |
| `search_space_id`   | FK          | scoping                                            |
| `server_url`        | text        | the MCP server's endpoint                          |
| `transport`         | text        | `"http"`, `"stdio"`, etc.                          |
| `name`              | text        | human-readable label (e.g., "Slack — Acme")        |
| `access_token`      | bytea       | encrypted at rest                                  |
| `refresh_token`     | bytea       | encrypted at rest                                  |
| `expires_at`        | timestamp   | for OAuth tokens                                   |
| `last_harvested_at` | timestamp   | when tool list was last refreshed                  |
| `created_at`        | timestamp   |                                                    |
| `created_by`        | FK → users  |                                                    |

### `mcp_tools`

The tool list each connected MCP server exposes. Acts as the durable
source for MCP capabilities — definitions reference `mcp_tools` rows by
qualified name, and worker processes lazily build handler closures from
this state.

| field           | type        | notes                                            |
| --------------- | ----------- | ------------------------------------------------ |
| `id`            | UUID PK     |                                                  |
| `connection_id` | FK → `mcp_connections.id` ON DELETE CASCADE | |
| `name`          | text        | the tool name reported by the MCP server         |
| `description`   | text        | description for the NL generator and form editor |
| `input_schema`  | jsonb       | JSON Schema for tool arguments                   |
| `output_schema` | jsonb       | JSON Schema for tool results                     |
| `side_effects`  | text[]      | inferred from MCP hints + naming + admin override |
| UNIQUE          |             | (connection_id, name)                            |

NL drafts are **not** a core table. They live in a generic short-TTL store
(Redis or a transient table) when the NL flow is built in Phase 3.

---

## 10. NL authoring flow

**This is how the system is intended to be used from day one, not just a
Phase 3 addition.** The product surface is: user describes intent in natural
language, LLM produces a structured proposal, user reviews and edits in an
auto-generated form, then saves. Hand-authoring JSON directly is supported
but is not the primary path.

This shapes the trust model. Templates are LLM-generated from day one, not
hand-written by power users. The mitigation is human-in-the-loop review,
not "trusted authors only."

### Pass 1: Proposal generation

User provides natural-language input. The Generator LLM is given:
- The full schema set (input schema for definition, registry of action
  types with their config_schemas, registry of trigger types, available
  capabilities for this SearchSpace, list of allowed Jinja filters)
- A tool to list available connectors, channels, and other SearchSpace
  resources, so it doesn't invent names that don't exist
- A few-shot set of examples

**Scoped input.** The Generator does *not* receive arbitrary SearchSpace
document content. Its context is the user's prompt plus the schema and
registry information. This minimizes the prompt-injection surface — there's
no document text in the context for an attacker to seed instructions into.

If a user wants document-aware generation later ("create an automation
that processes documents like this one"), that's a deliberate feature
extension with its own prompt-injection mitigations, not the default flow.

Output: a structured proposal matching the automation definition schema.

### Pass 2: Deterministic validation

Server-side, before the proposal reaches the user:
- Validate against JSON Schema (shape correctness)
- Verify every capability referenced exists in the registry (resource existence)
- Verify every connector/channel/resource referenced exists in this SearchSpace
- Validate every template against the sandbox's allowlist (no underscore
  attributes, no unregistered filter names, length under cap)

Failures here are deterministic errors, not warnings. A proposal that
references a non-existent capability or includes a template using
`{{x.__class__}}` is rejected before the user sees it; the Generator is
re-prompted with the validation error and asked to fix the proposal.

### Pass 2.5: Review pass

A second LLM call — the **Review LLM** — examines the validated proposal and
produces two outputs for the user:

1. **A plain-language summary** of what the automation will do, in business
   terms. "This automation will run every weekday at 9am. It reads documents
   in this SearchSpace tagged 'competitor' that were indexed since the last
   run, asks an agent to summarize them as 5 bullets, and posts the summary
   to your #engineering-standup Slack channel. Estimated cost: $0.40 per
   run."

2. **A "things worth checking" list** flagging anything unusual:
   - Templates with unusual attribute paths or filter usage
   - Prompts containing instructions that look more like commands than
     descriptions ("ignore previous instructions" style)
   - Action sequences that touch external systems without obvious benefit
     to the user
   - Cost estimates that seem high relative to the goal
   - References to capabilities the user hasn't used before
   - Schedules tighter than 15 minutes (likely should be event triggers)

The Review LLM is a **UX layer** that makes review actually useful. It is
**not a security boundary.** The deterministic controls (sandbox, runtime
limits, schema validator) are the security boundaries. The Review LLM
helps users catch their own intent mismatches and surfaces anomalies for
attention, but the sandbox would block dangerous templates even if the
Review LLM missed them.

This separation is important: two probabilistic controls compounding can
create a false sense of security. The Review LLM is explicitly framed in
the architecture as helper, not gatekeeper.

### Pass 3: Editable review

The user lands on a form pre-filled with the proposal. The page shows:
- The plain-language summary from the Review pass
- The flagged items, prominently displayed near the relevant fields
- The full editable form, auto-generated from the JSON Schemas
- Cost estimate and impact summary (which external systems get touched)

**Every field is editable.** Clarifications appear as required fields.
Templates are shown in code-styled fields with syntax highlighting and the
filter palette visible. The user can edit any field; saving re-runs Pass 2
(deterministic validation) before persisting.

Hitting **Save** promotes the proposal to an `automation` row.

### Editing existing automations

NL editing of an existing automation is a patch operation: the Generator
LLM receives the current definition plus the NL instruction and produces a
modified proposal. The same Pass 2 (validation) and Pass 2.5 (review) run
against the modified version, and the user reviews the diff before saving.
Existing run history is unaffected — only future runs use the new version.

### Why human-in-the-loop is non-negotiable

The Generator LLM, the Review LLM, and the sandbox are three layers of
defense against malformed or malicious proposals. The human approval step
is the fourth and most important layer. It exists because:

- LLMs can be prompt-injected; humans can spot text that asks them to
  ignore instructions
- LLMs can produce confident-but-wrong proposals; humans can catch
  semantic mismatches between intent and output
- The cost of a bad automation running unattended is high; the cost of a
  user clicking "approve" after reading is low

The architecture must never offer "auto-approve" or "skip review" options
for LLM-generated proposals. Save requires human action on the proposal,
always.

---

## 11. Repository layout

```
surfsense_backend/app/
├── automations/                       # NEW: the engine
│   ├── __init__.py
│   ├── models.py                      # SQLAlchemy models for 6 tables
│   ├── schemas.py                     # Pydantic schemas (definition envelope, etc.)
│   ├── routes.py                      # FastAPI router (/api/v1/automations)
│   ├── service.py                     # CRUD + business logic
│   ├── dispatcher.py                  # trigger matching, cost check, run creation
│   ├── executor.py                    # the Celery task that runs a plan
│   ├── templating.py                  # Jinja sandbox + filters
│   ├── events.py                      # publish/subscribe for domain_events
│   ├── filters.py                     # JSON filter grammar evaluator
│   ├── actions/
│   │   ├── registry.py
│   │   ├── agent_task.py
│   │   ├── transform_data.py
│   │   ├── slack_post.py
│   │   ├── send_email.py
│   │   ├── notification.py
│   │   └── (more in Phase 5: podcast_generation, report_generation, ...)
│   ├── triggers/
│   │   ├── registry.py
│   │   ├── schedule.py                # Celery Beat hookup
│   │   ├── webhook.py                 # /fire endpoint
│   │   └── event.py                   # subscribes to domain_events
│   ├── capabilities/
│   │   ├── registry.py
│   │   ├── native.py                  # native capability registrations
│   │   ├── mcp_harvester.py           # registers MCP tools as capabilities (Phase 4)
│   │   └── (LLM ops registered alongside)
│   └── nl/                            # Phase 1 — primary user path
│       ├── generator.py               # Generator LLM
│       ├── reviewer.py                # Review LLM (summary + flagged items)
│       ├── validator.py               # deterministic schema + resource checks
│       └── prompts.py                 # system prompts for both LLMs
│
├── utils/
│   └── periodic_scheduler.py          # EXTENDED to scan automation_triggers
│
└── alembic/versions/
    └── NN_add_automation_tables.py

surfsense_web/app/(routes)/
└── automations/                       # NEW: UI
    ├── page.tsx                       # list
    ├── new/page.tsx                   # NL input + draft preview (Phase 1)
    ├── [id]/page.tsx                  # editor (auto-generated forms)
    └── [id]/runs/page.tsx             # run history, streamed via Electric SQL
```

---

## 12. Phased delivery

Each phase delivers something usable. Each de-risks the next. **NL authoring
is the primary user path from Phase 1** — what evolves across phases is
which actions and triggers are available, not whether users can describe
automations in natural language.

### Phase 1 — Engine MVP with NL authoring
- 4 tables + Alembic migration
- Capability registry with native capabilities (`search_space.query`,
  `search_space.fetch_document`, `agent.run`)
- `agent_task` action only
- `schedule` trigger + manual "Run now" endpoint
- Executor with retries, timeouts, budget caps
- Template engine (Jinja sandbox + 15 filters + 4 runtime limits)
- **NL authoring flow**: Generator LLM, deterministic validator,
  Review LLM, editable form
- Run history UI with Electric SQL streaming

**After Phase 1**: a user can describe an automation in natural language,
review the proposal (with summary + flagged anomalies), edit any field,
save, and watch it run on a schedule. The Claude Routines value
proposition, on SurfSense's data, with NL-first authoring.

### Phase 2 — Webhooks and delivery
- `webhook` trigger with per-automation bearer tokens
- Tight actions: `slack_post`, `send_email`, `notification`
- `transform_data` action
- `on_failure` hooks
- Step-level retry/timeout overrides
- Concurrency policy enforcement

**After Phase 2**: external systems can drive automations, results go
somewhere humans see, complex pipelines have proper error handling.

### Phase 3 — NL authoring polish
- NL patch flow for editing existing automations (diff-based)
- Conversational refinement during proposal review ("change the schedule
  to weekdays only," "add a Slack notification on failure")
- Improved Review LLM coverage (more anomaly patterns, cost-relative-to-
  goal heuristics)
- Saved prompt templates and starter examples

**After Phase 3**: NL authoring is the polished primary surface; edit
flows are conversational rather than form-only.

### Phase 4 — Event triggers
- `domain_events` table and `events.py` module
- Indexing pipeline publishes `connector.*` events (smallest change — just
  add publish calls to the existing flow)
- Automations publish `automation.run.*` events on completion
- `event` trigger with filter grammar
- MCP capability harvester (so MCP-backed events and tools both work)

**After Phase 4**: "do X when Y happens" automations work, including
automation-chaining through events.

### Phase 5 — Wrapping existing features and sharing
- Wrap existing SurfSense capabilities as actions: `podcast_generation`,
  `report_generation`, `indexing_sweep`
- Artifact lifecycle implementation
- `expected_duration_seconds` based queue routing (split `automations_long`
  from `automations_default`)
- **Automation templates** (shareable, exportable, importable) — with
  the import re-approval flow that handles the approver-≠-runner trust
  shift documented in §7.4's pre-Phase-5 gate
- Cross-automation composition examples in the docs

**After Phase 5**: every existing SurfSense capability is automatable
without any per-feature code, and automations can be shared between
SearchSpaces and users.

---

## 13. Decisions locked

For reference — every decision made through the design process, in one
place.

### Foundations
1. ✅ JSON Schema 2020-12 is the single schema language for everything
2. ✅ Definition is the program; infrastructure is the interpreter
3. ✅ List of steps (not single action) in the plan, with `output_as` chaining
4. ✅ One capability registry serving native + MCP + LLM operations through the same interface
5. ✅ Capability IDs do not leak handler kind (`slack.post_message`, not `mcp.slack.post_message`)
6. ✅ Name-based resolution: definitions reference actions and capabilities by string ID. The registry is the runtime's vocabulary; lookup is a dict access. No code references in definitions.
7. ✅ The expressive spectrum runs from pure direct calls to broad agent_task; the NL generator proposes the cheapest shape that meets intent (Shape 6 from §4 by default)

### Trigger taxonomy
8. ✅ Three trigger types: `schedule`, `webhook`, `event`
9. ✅ Events absorb both connector events and internal SurfSense events
10. ✅ Filter grammar is JSON-structured operators (not Jinja)

### Templating cluster
11. ✅ Jinja2 `SandboxedEnvironment` for templates and `when:` predicates — but with the explicit understanding that the sandbox is an allowlist-by-default architecture, not a denylist
12. ✅ Zero globals registered. Curated 15 filters only, each audited for safe behavior with hostile input. List grows only by reviewed addition
13. ✅ Four runtime mitigations: `StrictUndefined`, 8 KB template source cap, 100 ms render time cap (watchdog-enforced), 1 MB output size cap
14. ✅ Non-string template values render as JSON by default
15. ✅ Fixed `run.*` namespace, documented
16. ⏸ **Pre-Phase-5 gate**: template sharing across SearchSpaces breaks the approver-equals-runner trust model. Mitigation is a re-approval flow at the import boundary (UX-level), not a template-language migration. Jinja itself stays.

### Execution
17. ✅ Executor is a Celery task wrapping a sequential loop — not an agent
18. ✅ `when:` is optional per step; false = skipped (not failed)
19. ✅ No DAGs, no parallelism, no loops — composition via agent_task or events
20. ✅ `on_failure` part of execution policy from v1
21. ✅ Step-level retry and timeout overrides
22. ✅ Budget cap enforced pre-enqueue and mid-flight

### Components
23. ✅ Dispatcher / executor / handlers / registry — distinct, each replaceable
24. ✅ Side effects are a set, including `USER_VISIBLE`
25. ✅ `expected_duration_seconds` integer drives queue routing
26. ✅ `produces_artifacts` is a list of `ArtifactSpec`, not a bool
27. ✅ Output schemas recommended on `agent_task`; editor warns when missing

### Event bus
28. ✅ `domain_events` table for v1, with upgrade path to Redis Streams
29. ✅ Automations publish run events for composability
30. ✅ Publish/subscribe behind interface — no direct table access elsewhere

### Capability storage (two-tier persistence)
31. ✅ Native capabilities registered in-memory at startup from the codebase. Identical across all workers.
32. ✅ MCP capability metadata persisted in `mcp_connections` and `mcp_tools` tables. Survives restarts.
33. ✅ MCP handler closures built lazily per worker from database state. Worker-local cache, rebuilt on demand.
34. ✅ MCP server tool list re-harvested on a schedule (default: daily) and on user request.
35. ✅ MCP tools harvested into the capability registry at connection time
36. ✅ Side effects inferred from MCP hints + naming + admin overrides
37. ✅ MCP tools callable directly (no agent required) when caller knows args

### Credentials
38. ✅ Credentials never appear in the automation definition — only connection IDs do
39. ✅ Credentials never appear in the LLM's context — the host holds them and uses them on the LLM's behalf
40. ✅ Credentials resolved per-call by `ActionContext`, not pre-loaded into worker environment
41. ✅ Tokens encrypted at rest in the database; refresh handled automatically by `ActionContext.resolve_*_client`

### NL authoring
42. ✅ LLM-authored templates is the primary path from day one — not a Phase 3 addition. Hand-authoring JSON is supported but secondary
43. ✅ Generator LLM produces JSON; deterministic schema + resource validation runs before user sees the proposal
44. ✅ Review LLM produces plain-language summary + flagged anomalies for the user — UX layer, not a security boundary
45. ✅ Generator LLM's input is scoped (user prompt + schema + registry only); arbitrary document content is not fed in
46. ✅ Human approval is required before save — no auto-approval option, ever
47. ✅ Every field editable in the proposal; unresolved questions surface as clarifications
48. ✅ NL drafts are transient storage, not a core table

### Data model
49. ✅ Six tables total — four for engine state, two for MCP persistence
50. ✅ Run rows snapshot the definition (immutable history)
51. ✅ All entities scoped by `search_space_id` for RBAC
52. ✅ Editing an automation bumps `version`; existing runs unaffected

---

## 14. Open questions deferred to implementation

None of these block design; they're decisions a developer will make in
context, with the principle from §1 as their guide.

- Exact retry backoff formulas (multipliers, jitter, ceilings)
- Webhook signature verification standards (HMAC scheme, header naming)
- Whether to support inline JSON Schema `$ref` to external schemas, or
  inline everything
- Specific CDN/storage backend choices for artifacts (probably
  whatever SurfSense already uses for podcasts)
- Rate limits per SearchSpace and per user
- Audit log retention policy

---

## 15. Why this is ready to build

This document satisfies five tests:

1. **The four worked examples** (digest, CI webhook, file-added-trigger,
   weekly podcast) all express cleanly in the contract without special
   cases. Each one was used to find gaps before the gaps reached code.

2. **The audit pass identified six refinements**, all incorporated. No
   pending audit items.

3. **Every decision points back to the principle from §1.** When a future
   feature request lands, "does it belong in the definition or in the
   engine?" gives a clear answer.

4. **The build is staged** so Phase 1 ships in weeks, not months, and
   each subsequent phase delivers user value while de-risking the next.

5. **Existing SurfSense infrastructure is reused**, not paralleled. Celery
   Beat, PostgreSQL/JSONB, Electric SQL, SQLAlchemy/Alembic, the existing
   `tools/registry.py` pattern, the existing Search Space scoping — all
   continue to do what they already do. The automation engine is a new
   directory, not a new system.

The next document a developer needs is the Pydantic models and JSON
Schemas spelled out concretely. Those follow mechanically from this plan.

---

*Sources consulted: Claude Code Routines documentation; NousResearch/hermes-
agent (cron and skills subsystems); n8n documentation on node types and
workflow data model; the SurfSense repository and DeepWiki architecture
notes (FastAPI + Celery Beat + Electric SQL + LangGraph Deep Agents +
Search Space RBAC); Model Context Protocol specification for capability
harvesting; AWS EventBridge for filter grammar; workflow-pattern
literature (van der Aalst et al.) for the trigger / action / concurrency
vocabulary.*
