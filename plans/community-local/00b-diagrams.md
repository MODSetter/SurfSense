# Community Local — Companion Diagrams

> Workstreams: [`frontend/`](frontend/), [`api/`](api/), [`worker/`](worker/).

## Process layout at runtime

```text
┌─────────────────────────────────────────────────────────────┐
│ Electron main                                               │
│  • BrowserWindow → frontend/dist (workspace UI)             │
│  • spawn surfsense-api                                      │
│  • spawn surfsense-worker                                   │
│  • packaged Ollama sidecar; bundled llmfit executable       │
│  • on quit: SIGTERM workers, wait, exit                     │
└─────────────────────────────────────────────────────────────┘
         │                              │
         ▼                              ▼
┌─────────────────┐          ┌─────────────────┐
│ surfsense-api   │          │ surfsense-worker │
│ FastAPI :8xxx   │          │ huey_consumer -w1│
│ LLM catalog     │          │ Docling + embed  │
│ runtime adapters│          │                 │
│ llmfit JSON CLI │          │                 │
│ SQLite R/W      │          │                 │
└────────┬────────┘          └────────┬─────────┘
         │                            │
         └────────────┬───────────────┘
                      ▼
              ~/.surfsense/surfsense.db
              ~/.surfsense/huey.db
              ~/.surfsense/models/
```

## Onboarding paths (one binary)

```text
                    ┌─────────────────┐
                    │  First launch   │
                    └────────┬────────┘
                             │
         ┌───────────────────┼───────────────────┐
         ▼                   ▼                   ▼
   ┌───────────┐      ┌─────────────┐     ┌───────────┐
   │ A Airgap  │      │ B Slim +    │     │ C BYO     │
   │ full pack │      │ on-demand   │     │ Ollama/   │
   └───────────┘      └─────────────┘     └───────────┘
                             ▼
                    llmfit hardware scan
                             ▼
                 Recommended + Explore
                             ▼
                 one-click Download & Use
                             ▼
                    runtime install plan
                    ├─ Ollama tag (v1)
                    └─ verified GGUF (later)
                             ▼
              Create workspace → upload document
```

## Generation model boundaries

```text
llmfit model catalog + fit estimates
                  │
                  ▼
          SurfSense adapter
                  │ canonical, normalized models
                  ▼
      Curated models JSON + support policy
                  │
                  ▼
       Runtime artifact resolver
          ├── Ollama adapter ── pull tag ── chat
          └── llama.cpp adapter (future) ── GGUF ── chat
```

llmfit never handles a SurfSense chat request. It can disappear and an already
installed model still answers through its runtime adapter.

## Chat vs Studio

```text
CHAT
  question → hybrid search (app) → trim chunks → LLM → answer + citations

STUDIO (button)
  pick artifact type → pick documents → optional prompt
    → retrieve (app) → LLM → builder → artifacts row + file
```
