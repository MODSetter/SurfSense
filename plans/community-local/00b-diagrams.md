# Community Local — Companion Diagrams

> Workstreams: [`frontend/`](frontend/), [`api/`](api/), [`worker/`](worker/).

## Process layout at runtime

```text
┌─────────────────────────────────────────────────────────────┐
│ Electron main                                               │
│  • BrowserWindow → frontend/dist (workspace UI)             │
│  • spawn surfsense-api                                      │
│  • spawn surfsense-worker                                   │
│  • on quit: SIGTERM workers, wait, exit                     │
└─────────────────────────────────────────────────────────────┘
         │                              │
         ▼                              ▼
┌─────────────────┐          ┌─────────────────┐
│ surfsense-api   │          │ surfsense-worker │
│ FastAPI :8xxx   │          │ huey_consumer -w1│
│ SQLite R/W      │          │ Docling + embed  │
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
                    RAM tier → model suggestion
                             ▼
              Create workspace → upload document
```

## Chat vs Studio

```text
CHAT
  question → hybrid search (app) → trim chunks → LLM → answer + citations

STUDIO (button)
  pick artifact type → pick documents → optional prompt
    → retrieve (app) → LLM → builder → artifacts row + file
```
