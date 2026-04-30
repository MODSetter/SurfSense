# `multi_agent_chat` — layout & alignment with `new_chat`

## Mission

**Preserve** everything that makes SurfSense chat agents production-grade in `new_chat` (KB, middleware, tools, prompts, safety, observability). **Rework** how those pieces are composed: a clearer **multi-agent** layout (supervisor + domain slices + routing), less accidental coupling, and one explicit assembly path—so the agent stays **excellent** (correct tools, grounded KB, safe permissions, debuggable traces), not just “different folders.”

Implementation strategy: **reuse `new_chat` modules** (middleware classes, tool factories, KB helpers, prompts composer pieces) wherever possible; **`multi_agent_chat` owns structure and wiring**, not reimplemented business logic.

---

## What we must not lose from `new_chat` (capability inventory)

Use this as a checklist when porting middleware/KB into `multi_agent_chat`. Items map to `surfsense_backend/app/agents/new_chat/`.

| Area | Capabilities to preserve | Typical locations |
|------|-------------------------|-------------------|
| **KB & documents** | Hybrid search → priority docs → lazy XML load; workspace tree; anon-document path; KB persistence / commit staging | `middleware/knowledge_search.py`, `knowledge_tree.py`, `kb_persistence.py`, `anonymous_document.py`, `tools/knowledge_base.py`, `search_surfsense_docs.py` |
| **Filesystem** | Virtual FS, backends, path resolver, file intent | `middleware/filesystem.py`, `filesystem_backends.py`, `path_resolver.py`, `file_intent.py` |
| **Memory & context** | Memory injection, team/private protocols, context schema | `middleware/memory_injection.py`, `prompts/base/memory_protocol_*.md`, `context.py` |
| **Safety & quality** | Permissions, doom-loop detection, dedup HITL tool calls, tool-call repair, action logging | `middleware/permission.py`, `doom_loop.py`, `dedup_tool_calls.py`, `tool_call_repair.py`, `action_log.py` |
| **Model / context limits** | Compaction, context editing / spill, summarization, model & tool call limits, retries / fallback | `middleware/compaction.py`, `context_editing.py`, `chat_deepagent.py` stack |
| **Concurrency & ops** | Busy mutex (single-flight turns), OTel spans | `middleware/busy_mutex.py`, `otel_span.py` |
| **Skills & subagents** | Skills backends, subagent specs and wrapping patterns | `middleware/skills_backends.py`, `subagents/` |
| **Tools** | Async registry, connector gating, MCP loading, feature-flagged tools | `tools/registry.py`, `feature_flags.py`, `tools/mcp_tool.py` |
| **Prompts** | Composer, provider fragments, tool routing (KB vs live connectors), citations | `prompts/composer.py`, `prompts/base/tool_routing_*.md`, `system_prompt.py` |
| **Runtime** | Checkpointer, LLM config, `create_agent` + middleware ordering discipline | `checkpointer.py`, `llm_config.py`, `chat_deepagent.py` |

Not every row applies to the **first** multi-agent graph (e.g. you may start with a subset of middleware). The rule is: **if `new_chat` does it for correctness or safety, we either reuse it or consciously document why this graph differs.**

---

## Rework principles (better arrangement, same substance)

1. **Expert agents**: **`expert_agent/builtins/`** — broad registry **categories** (e.g. research, deliverables), not a single vendor. **`expert_agent/connectors/`** — **external integrations** (one package per product route: Discord, Notion, Gmail, …), each using the same pattern: ``slice_tools.py`` (registry subset or factories) + ``domain_prompt.md`` + ``agent.py``. Cross-cutting helpers live in `core/` or are imported from `new_chat`.
2. **Explicit graphs**: supervisor vs domain agents vs routing tools are **named** and testable; avoid one opaque megagraph where behavior is hard to reason about.
3. **Single composer**: integration eventually mirrors `create_surfsense_deep_agent` in spirit—**one factory** that attaches middleware, KB, and tools in documented order (see `chat_deepagent.py` comments on ordering).
4. **No duplicate KB pipelines**: align with `KnowledgePriorityMiddleware` / tree semantics; don’t invent a second hybrid-search path for the same turn.
5. **Parity tests**: when wiring completes, compare behavior against `new_chat` for the same user message + search space where scopes overlap (KB snippet quality, tool allow/deny).

---

## Supervisor vs domain agents — tools and context

**Supervisor (orchestrator)**

- Keeps a **small tool surface**: one **routing** tool per builtin category (`research`, `memory`, …) and per connector route (`notion`, `gmail`, …) — **not** the full flat `registry.py` tool list on the supervisor.
- **KB** should primarily benefit the model via **`new_chat`-style middleware** (e.g. hybrid priority docs → state / system adjunct), not by stacking redundant search tools, unless product explicitly requires them.
- **Single hybrid search per user turn** at this layer when possible: full retrieval is expensive; avoid running it again inside every sub-agent for the same message.
- Does **not** own **on-demand connector discovery** (e.g. `get_connected_accounts`): orchestration is route-by-intent, not ID resolution.

**Domain agents (every connector slice — same shape)**

- Carry tools built from **`new_chat`** (`registry` subsets via ``build_registry_tools_for_category`` per ``TOOL_NAMES_BY_CATEGORY``, plus MCP merge where applicable).
- **Curated context belongs in the task message**: when the supervisor calls **any** routing tool, the handler composes the child’s task string so it includes **only** what that domain needs (KB snippets, constraints, distilled facts) — folded into how the task is written — not the full parent transcript. The sub-agent `invoke` stays a tight payload (`messages` + task content); domain middleware can still add connector-local hints. Still **no second full hybrid search** for the same turn unless the subdomain explicitly needs a new query.
- **Middleware here** still fits **domain-only** grounding (connector availability, search-space hints, metadata) shared across tools in that subgraph. Reuse or thin-wrap `new_chat.middleware` where it applies to a subgraph.
- **Reactive discovery** (resolve a service id mid-task) stays a **tool** on that domain (or shared factory), e.g. `get_connected_accounts` when the model needs it — not something the supervisor must call.

**Tool grouping by category**

- Group “horizontal” registry tools by **job** (research, deliverables, creative, …) into **separate compiled subgraphs**; supervisor gets **one routing tool per category** (subagents-as-tools), matching LangChain multi-agent guidance. See prior discussion: not all 10 non–connector-gated tools on the supervisor.

### KB + virtual filesystem — where it belongs

In `new_chat`, KB + **virtual FS** (`KnowledgePriorityMiddleware`, tree, **`SurfSenseFilesystemMiddleware`** / **`KBPostgresBackend`**) serves the **orchestrator** that may **read and traverse** the workspace.

**Connector domain agents** are **not** mini-parents: the **supervisor** should already decide *what* to do and pass a **clear task** (plus any curated KB snippet folded into **`compose_child_task`**). The specialist runs **connector APIs**, not a second document crawl — duplicating full KB+VFS on every domain subgraph **shifts the parent’s exploration work onto the wrong agent** and adds noise.

So **no child-side filesystem stack by default** for narrow connector subgraphs unless product demands it. Reserve **KB + VFS on a subgraph** for roles that **actually** need heavy document work (research, coding/explore-style agents, deliverables that grep the KB), matching how `new_chat` uses specialists.

---

## Inspiration map (`new_chat` → `multi_agent_chat`)

| Concern in `new_chat` | Primary references | Role in `multi_agent_chat` |
|----------------------|-------------------|---------------------------|
| **Main factory** | `chat_deepagent.py` (`create_surfsense_deep_agent`) | `integration/create_multi_agent_chat.py` — eventual single composer after KB + middleware land |
| **Tool lists** | `tools/registry.py`, `build_tools_async` | **`expert_agent/builtins/`** — category bundles (research, deliverables). **`expert_agent/connectors/`** — per-integration graphs (may use hand-written factories or registry subsets). |
| **Middleware stack** | `chat_deepagent.py` → `_build_compiled_agent_blocking`, `middleware/*.py` | **Planned:** `middleware/` — compose `create_agent(..., middleware=[...])` on supervisor and/or domain graphs; reuse or thin-wrap `new_chat.middleware` (ordering matters: see `new_chat` comments, e.g. BusyMutex → OTel → KB priority → filesystem → …) |
| **KB / hybrid search** | `middleware/knowledge_search.py` (`KnowledgePriorityMiddleware`), `middleware/knowledge_tree.py`, `tools/knowledge_base.py` | **Planned:** hybrid priority **once per user turn** at orchestrator; **curated KB/context folded into the routing task message** to children (no second full search for the same message unless explicitly scoped otherwise). |
| **Prompts** | `prompts/composer.py`, `prompts/base/*`, provider fragments | Vertical **`domain_prompt.md`** per slice + **`supervisor/supervisor_prompt.md`**; optional later: thin composer that injects KB/tool-routing fragments like `tool_routing_*.md` |
| **Context / checkpointer** | `context.py`, `checkpointer.py` | Pass **`Checkpointer`** into `create_multi_agent_chat` / `build_supervisor_agent`; align thread IDs with route layer when wired |
| **Subagent middleware** | `subagents/config.py` (`_wrap_with_subagent_essentials`) | Domain agents may eventually take **`middleware=`** on `create_agent` mirroring “inherit parent essentials + local rules” |

---

## Current package tree

```
multi_agent_chat/
  __init__.py

  core/                      # one concern per subfolder (SRP)
    prompts/                 # read_prompt_md — markdown next to packages
    agents/                  # build_domain_agent — compile subgraph + prompt
    delegation/              # compose_child_task — supervisor → child message
    invocation/              # extract_last_assistant_text — invoke result parsing
    bindings/                # ``connector_binding`` — DB/search-space kwargs (not ``expert_agent.connectors`` vendors)
    registry/                # TOOL_NAMES_BY_CATEGORY, build_registry_tools_for_category, build_registry_dependencies

  expert_agent/
    builtins/                # broad categories: research, deliverables
    connectors/              # one subgraph per vendor route (see TOOL_NAMES_BY_CATEGORY keys)

  routing/
    domain_routing_spec.py
    from_domain_agents.py
    supervisor_routing.py

  supervisor/
    supervisor_prompt.md
    graph.py

  integration/
    create_multi_agent_chat.py
```

---

## References

- LangChain: [Multi-agent](https://docs.langchain.com/oss/python/langchain/multi-agent), [Subagents](https://docs.langchain.com/oss/python/langchain/multi-agent/subagents).
- Internal: `surfsense_backend/app/agents/new_chat/chat_deepagent.py`, `middleware/`, `tools/registry.py`.
