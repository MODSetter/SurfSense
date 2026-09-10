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
LOCAL                                      REMOTE
llmfit catalogue + fit                    provider_connections
        │                                           │
        ▼                                           ▼
SurfSense adapter + policy                live GET /models per endpoint
        │                                           │
        ▼                                           ▼
runtime artifact resolver                 SelectedModel(connection_id, name)
  ├── Ollama ── pull tag ── chat             ├── generation
  └── llama.cpp (future) ── chat             │   └── core vLLM/gateway
                                              │       └── /chat/completions
                                              └── image_generation
                                                  ├── vLLM-Omni/gateway
                                                  │   └── /images/generations
                                                  └── OpenRouter
                                                      └── /images on 404/405
```

llmfit never handles a SurfSense chat request. It can disappear and an already
installed model still answers through its runtime adapter. Remote model lists
are fetched live and never copied into SQLite. Two endpoints with the same model
id remain distinct because selection identity includes the connection id.

## Chat vs Studio

```text
CHAT
  question → hybrid search (app) → trim chunks → LLM → answer + citations

STUDIO (button)
  pick artifact type → pick documents → optional prompt
    → retrieve (app) → LLM → builder → artifacts row + file

  infographic → generation model → strict spec → deterministic SVG/HTML builder
  image       → image_generation selection
                → /images/generations (or /images on 404/405) → artifact file
```
