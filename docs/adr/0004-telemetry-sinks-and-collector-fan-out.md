# ADR 0004: One OTLP export to self-hosted LGTM; split agent/infra *views* by semconv, not by a second app-side SDK

- **Status:** Accepted (implemented in the observability module reorg)
- **Date:** 2026-08-26
- **Origin:** Review of `app/observability/` for maintainability/scale. Question raised: "we push agent stuff and API stuff into one sink — should agent traces go to a LangSmith-like sink instead?" This ADR decides *where each signal lands*, *how many times the app instruments*, and *what we defer*.
- **Relates to:** [ADR 0002](0002-knowledge-core-ports-and-adapters.md) (one core, many adapters — the same "one seam, many backends" instinct applies to telemetry). Does **not** touch the KB.

---

## Context

### Current state

The backend instruments **once** with OpenTelemetry and exports **traces,
metrics, and logs** over OTLP to a **self-hosted Grafana LGTM** stack
(`grafana/otel-lgtm` all-in-one: Tempo + Prometheus + Loki + Grafana, which
embeds a collector). Dev runs it via `docker-compose.dev.yml`; prod points
`OTEL_EXPORTER_OTLP_ENDPOINT` at its own LGTM. **There is no separate
app-managed collector config in the repo** — the previously-written
`otel-collector/config.yaml` (a Grafana Cloud fan-out that was never wired) has
been deleted. Telemetry is a no-op unless an OTLP endpoint is set.

### The problem this fixed

An LLM call used to be observed **three** times, none the OTel-standard way:

| Sink | How it saw an agent call | How it saw API/infra |
|---|---|---|
| **OTel → self-hosted LGTM** | bespoke `model.call` / `tool.call` / `kb.search` spans under tracers named `surfsense.new_chat` / `surfsense.platform` | FastAPI/SQLAlchemy/Redis/httpx/Celery auto-instrumentation |
| **PostHog** | `$ai_generation` / `$ai_span` via the LangChain `CallbackHandler` | product/outcome events only |
| **LangSmith** | full LangChain trace, opt-in via `LANGSMITH_TRACING` | nothing |

Three app-side integrations meant three failure modes, three flush/shutdown
paths, three credential sets, and a **bespoke span vocabulary** no backend reads
natively — while the one place infra and agent *should* correlate (a single
trace) used invented names instead of `gen_ai.*`.

### The insight

Splitting the agent *view* is correct; doing it with a *second app-side SDK* —
or standing up a new backend before we need one — is the anti-pattern. We
already self-host an OTLP-native backend. So: **instrument once with `gen_ai.*`
semconv, export OTLP to the self-hosted LGTM, and defer fan-out** until a
dedicated LLM backend earns its place. Because spans are `gen_ai.*` over OTLP,
adding Langfuse/Phoenix later is a collector/exporter change, not
re-instrumentation.

---

## Decision

**One app export path: OTLP directly to the self-hosted LGTM all-in-one.
Instrument agent calls with `gen_ai.*` semconv so they nest in the same trace as
their HTTP/DB context. PostHog stays product-only; the `$ai_generation` callback
is removed. LangSmith is dev-only. A dedicated LLM-observability backend and the
collector fan-out are deferred — introduced when evals/prompt-management become
real needs.**

### Target topology

```
App (FastAPI + Celery)
  └─ OTLP (traces + metrics + logs) ─► self-hosted LGTM all-in-one
                                         ├─ Tempo       (infra + agent, one trace)
                                         ├─ Prometheus  (incl. gen_ai cost/latency)
                                         └─ Loki        (logs, trace-correlated)
                                         … (future) ─► Langfuse / Phoenix
                                              ← added via a collector/exporter when evals need it

Product analytics: PostHog SDK  (separate on purpose — different signal, audience, shape)
```

### The two clean seams

1. **Ops telemetry (how the system behaves)** — OTel. One app export to LGTM.
   Tomorrow a collector copies `gen_ai.*` spans to an LLM backend without the app
   changing.
2. **Product analytics (what users/business do)** — PostHog. Event-shaped, keyed
   to persons, captures non-browser surfaces (MCP, PAT, Celery). Folding it into
   a trace backend is a category error.

### Concrete rules

- **The app exports OTLP directly to the self-hosted LGTM.** No agent-trace SDK
  ships spans directly to a vendor in prod.
- **Agent spans carry `gen_ai.*` semconv and nest under the FastAPI server
  span** — agent + HTTP + DB in **one** trace.
- **Do not split the trace; keep the option to split the *backends*.** A
  collector/second exporter is added the day a dedicated LLM backend earns it.
- **PostHog keeps product/outcome analytics; the `$ai_generation` callback is
  removed** — it was the redundant fourth view.
- **LangSmith is dev-only** (`LANGSMITH_TRACING=false` in prod).

---

## We are borrowing, not inventing

| Element | Borrowed from |
|---|---|
| `gen_ai.*` as the one agent vocabulary | **OpenTelemetry GenAI semantic conventions.** https://github.com/open-telemetry/semantic-conventions/tree/main/docs/gen-ai |
| Instrument once, point at any backend, swap by config | **"Trace your agent with OTel GenAI, then point it anywhere."** https://dreaming.press/posts/instrument-agent-opentelemetry-genai-traces-send-anywhere.html |
| Agent spans parent under the FastAPI server span (one trace, two lenses) | **LiteLLM OTel v2.** https://github.com/BerriAI/litellm/pull/28909 |
| Fan-out / routing added when a second backend exists | **OTel Collector routing connector.** https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/main/connector/routingconnector/README.md |
| The deferred LLM backend is OTLP-native, so it drops in without re-instrumentation | **Langfuse native OpenTelemetry** https://langfuse.com/integrations/native/opentelemetry · **Arize Phoenix** https://arize.com/docs/phoenix/tracing/concepts-tracing/otel-openinference/otel-collector |
| Product analytics is a *separate* signal from ops telemetry | Existing SurfSense split (`analytics/` vs OTel), reaffirmed. |

### Counter-examples we reject

- **A second app-side agent SDK** exporting straight to a vendor. Re-creates the
  three-pipe mess, makes the app own vendor credentials + flush lifecycle, and
  orphans agent spans from the infra trace.
- **Standing up Langfuse (self-host or cloud) now.** Buys prompt-management +
  evals we do not yet do, at real cost. YAGNI until the need is concrete.

---

## Scope (implemented in the reorg)

1. **Agent spans reshaped to `gen_ai.*` semconv** (`model.call` → semconv attrs +
   `SpanKind.CLIENT`; neutral `surfsense` tracer/meter scope). Ergonomic
   `*_span()` helpers kept; only names/attributes changed. → `domains/agent.py`.
2. **Traces, metrics, and logs all exported over OTLP** — logs previously had no
   exporter; `setup/providers.install_logging()` now installs a
   `LoggerProvider` + `OTLPLogExporter` + root `LoggingHandler`.
3. **`build_llm_callback_handler` and the `$ai_generation` wiring removed**;
   `capture_chat_turn_completed` and all product/outcome captures kept in
   `analytics/posthog.py`. The anonymous tier gained `OtelSpanMiddleware` so its
   LLM calls still emit `gen_ai.*` to LGTM.
4. **LangSmith defaulted off** (`LANGSMITH_TRACING=false`; dev-only).
5. **`POSTHOG_AI_PRIVACY_MODE` removed** — it only guarded the deleted callback.
6. **Module reorg** into `core/` (policy/identity), `signals/` (tracing/metrics),
   `setup/` (providers/instrumentation/privacy/lifecycle), `domains/*` (one file
   per concept), `analytics/` (PostHog). The old `bootstrap.py` / `otel.py` /
   `metrics.py` god-files were deleted.

### Deferred (keep the door open, build when needed)

- **Langfuse / Phoenix as a fan-out target** — added via a collector exporter +
  pipeline when evals or prompt management become real. Cloud-vs-self-host
  decided *then*, driven by whether traces must carry prompt/completion content.
- **Evals and prompt versioning/management.**
- **Production-grade, durable trace/metric storage** — the all-in-one is
  single-node/ephemeral; durable prod storage is a separate decision.

---

## Consequences

### Positive

- **No new system, no new vendor now.** Agent traces land in the LGTM we already
  self-host.
- **One export path.** The app speaks OTLP; the destination is one endpoint.
- **The door stays open cheaply.** `gen_ai.*` over OTLP means Langfuse/Phoenix
  later is a config change, not a re-instrumentation project.
- **Net deletion:** the `$ai_generation` callback, `POSTHOG_AI_PRIVACY_MODE`,
  prod LangSmith, three god-files, and the unwired collector config are gone;
  bespoke span names collapsed onto a standard.
- **One trace, correlated.** Agent + HTTP + DB in a single Tempo trace; logs in
  Loki carry the same trace/span IDs.

### Negative / cost

- **The LGTM all-in-one is not production-grade storage** (single-node,
  ephemeral). Fine for now; durable prod storage is deferred, not free.
- **Reshaping spans breaks any dashboard/query** built on `model.call` /
  `surfsense.new_chat`.
- **Tempo shows a raw trace, not an LLM UI** — no prompt/completion rendering,
  cost rollups, or evals until a dedicated backend is added. Accepted.
- **`gen_ai` semconv is still "Development" status** — expect occasional updates.
- **Privacy decision is deferred, not resolved** — it returns the day agent
  traces might carry prompt/completion bodies to a new backend.

---

## Alternatives considered

| Alternative | Why not (now) |
|---|---|
| Stand up **Langfuse self-hosted** now | 6-container/ClickHouse ops for eval/prompt features we don't yet use. Add via fan-out when needed. |
| **Langfuse / LangSmith Cloud** now | New SaaS + data egress + a privacy fork, inconsistent with our self-host posture, and premature. |
| **Second app-side agent SDK** to a vendor | Re-creates three pipes; app owns vendor creds + flush; agent spans orphan from the infra trace. |
| **Keep the three overlapping sinks** (status quo) | Triple cost and drift; no standard vocabulary. |
| **PostHog as the agent-trace sink** | Not OTLP/trace-shaped; wrong shape and privacy profile for prompts/completions. |

---

## Obligations

1. The app exports OTLP to the self-hosted LGTM only; no agent SDK ships spans
   directly to a vendor in prod.
2. Agent spans use `gen_ai.*` semconv and parent under the server span (verified
   for Celery + detached tasks).
3. `analytics/posthog.py` product/outcome captures remain; the `$ai_generation`
   callback stays removed, not relocated.
4. Adding a dedicated LLM backend is a collector-config change; the application
   code does not move.
5. When (4) happens, message-body privacy is decided first and enforced at the
   collector by default (scrub unless explicitly enabled).

---

## Open questions (for team discussion)

1. **Prod backend + durable storage:** self-hosted LGTM with real storage vs the
   Grafana Cloud path. The all-in-one is ephemeral.
2. **When Langfuse/Phoenix is introduced:** do agent traces carry
   prompt/completion content (evals need it; privacy resists it)? cloud vs
   self-host? who operates ClickHouse if self-host?
3. **Sampling:** keep 100% of `gen_ai` spans even when infra tail-sampling drops
   healthy traces?

---

## Appendix: key file index (current implementation)

| Topic | Path |
|---|---|
| Enablement/policy, resource identity, error tokens, semconv | `surfsense_backend/app/observability/core/` |
| Generic span + metric mechanisms | `surfsense_backend/app/observability/signals/` |
| Providers/exporters, instrumentors, privacy scrub, lifecycle | `surfsense_backend/app/observability/setup/` |
| Per-concept spans + metrics (agent, chat, kb, etl, indexing, gateway, celery, security, knowledge_store, runtime) | `surfsense_backend/app/observability/domains/` |
| PostHog product analytics (keep) | `surfsense_backend/app/observability/analytics/posthog.py` |
| `chat_turn_completed` product event (keep; `$ai_generation` removed) | `surfsense_backend/app/tasks/chat/streaming/flows/shared/analytics.py` |
| Dev self-hosted backend | `docker/docker-compose.dev.yml` (`otel-lgtm`) |
| LangSmith opt-in (dev-only) | `surfsense_backend/.env.example` (`LANGSMITH_TRACING`) |
| Docs | `surfsense_web/content/docs/observability.mdx` |
