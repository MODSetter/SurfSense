# Multi-Agent Capability Parity Checklist

This checklist tracks whether `multi_agent_chat` has the required capability coverage
to be manually tested against `new_chat` in LangSmith.

Legend:
- `[x]` implemented
- `[~]` implemented with intentional difference
- `[ ]` pending

## 1) Prompting

- [x] Supervisor prompt has explicit delegation policy.
- [x] Supervisor prompt consumes structured expert outputs (`status`, `evidence`, `next_step`, `missing_fields`, `assumptions`).
- [x] Supervisor available specialist list is dynamically rendered from currently registered tools.
- [x] All expert prompts are normalized to a shared JSON output contract shape with invariant rules.
- [x] Memory wording adapts to thread visibility (user vs team).
- [~] `generic_mcp` specialist prompt exists but route is intentionally disabled.

## 2) Tooling and Routing

- [x] Built-in specialist routes are wired (`research`, `memory`, `deliverables` when eligible).
- [x] Connector specialist routes are gated by available connector inventory.
- [x] MCP tools are partitioned and merged into matching specialists.
- [x] MCP-only named specialists are routed when present (`linear`, `slack`, `jira`, `clickup`, `airtable`).
- [~] `generic_mcp` route is intentionally disabled by product decision.
- [x] Delegated child tasks include explicit structured context envelope tags.
- [x] Domain-agent outputs are parsed and validated as JSON with safe fallback envelope.

## 3) Middleware / Runtime

- [x] Supervisor middleware stack mirrors SurfSense shell used by `new_chat` for core protections.
- [~] `SubAgentMiddleware` intentionally omitted (multi-agent architecture uses explicit specialists).
- [~] `PermissionMiddleware` intentionally omitted by decision (route gating used instead).
- [x] Action-log / compaction / retry / fallback / filesystem / KB middleware are wired for supervisor path.
- [x] Agent graph compile path uses `asyncio.to_thread` for heavy build operations.

## 4) Entry-Point Wiring

- [x] Authenticated streaming path can route to `create_multi_agent_chat` via feature flag (`MULTI_AGENT_CHAT_ENABLED`).
- [x] Resume streaming path can route to `create_multi_agent_chat` via feature flag.
- [~] Authenticated stream falls back to `new_chat` when `disabled_tools` is provided (multi-agent does not yet implement disabled-tool filtering parity).
- [ ] Anonymous stream path wired to multi-agent (left unchanged for now due anonymous tool allow-list differences).

## 5) Observability and Validation Readiness

- [x] Ready for manual LangSmith trace inspection once `MULTI_AGENT_CHAT_ENABLED=true`.
- [ ] Formal routing eval harness and benchmark dataset.
- [ ] Automated regression checks in CI for routing quality.

## 6) Manual Benchmark Readiness Decision

Status: **Ready for manual benchmarking in authenticated flows**.

Before declaring "better than `new_chat`", still required:
- Build and run formal eval/benchmark harness.
- Close anonymous-path and disabled-tools parity gaps if they are in benchmark scope.
