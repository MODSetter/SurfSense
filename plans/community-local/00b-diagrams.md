# Community Local — Companion Diagrams

> Workstreams: [`frontend/`](frontend/), [`api/`](api/), [`worker/`](worker/).

> Updated for [`api/07-llamacpp-runtime.md`](api/07-llamacpp-runtime.md):
> **Phase 7** replaces the Ollama sidecar with `llama-server` and removes the
> bundled llmfit binary.

## Process layout at runtime

```text
┌─────────────────────────────────────────────────────────────┐
│ Electron main                                               │
│  • BrowserWindow → frontend/dist (workspace UI)             │
│  • spawn surfsense-api                                      │
│  • spawn surfsense-worker                                   │
│  • packaged llama-server sidecar (router mode)              │
│  • on quit: SIGTERM workers, wait, exit                     │
└─────────────────────────────────────────────────────────────┘
         │                              │
         ▼                              ▼
┌─────────────────┐          ┌─────────────────┐
│ surfsense-api   │          │ surfsense-worker │
│ FastAPI :8xxx   │          │ huey_consumer -w1│
│ LLM catalog     │          │ Docling + embed  │
│ runtime adapters│          │                 │
│ GGUF header +   │          │                 │
│ ggml budget     │          │                 │
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
   │ full pack │      │ on-demand   │     │ endpoint  │
   └───────────┘      └─────────────┘     └───────────┘
                             ▼
              ggml device query (~180 ms, no scan)
                             ▼
              Curated (offline)  +  HF search (network)
            every row badged FITS / PARTIAL / TOO_BIG
                             ▼
                 one-click Download & Use
                             ▼
                    runtime install plan
                    └─ pinned GGUF (repo + file + quant)
                             ▼
              Create workspace → upload document
```

## Generation model boundaries

```text
LOCAL                                      REMOTE
curated manifest + HF search              provider_connections
        │                                           │
        ▼                                           ▼
fit estimator (ggml budget +              live GET /models per endpoint
 GGUF header), rank from manifest                   │
        │                                           ▼
        ▼                                 SelectedModel(connection_id, name)
GgufArtifact resolver                        ├── generation
  └── llama.cpp ── fetch file ── chat        │   └── core vLLM/gateway
                                              │       └── /chat/completions
                                              └── image_generation
                                                  ├── vLLM-Omni/gateway
                                                  │   └── /images/generations
                                                  └── OpenRouter
                                                      └── /images on 404/405
```

llmfit is not in the app at all: it runs on a maintainer's machine a few times a
year and its numbers ship as data in the manifest. The fit badge comes from the
runtime's own allocator plus the model's GGUF header, so it works offline and
covers every GGUF, not a curated subset. Remote model lists
are fetched live and never copied into SQLite. Two endpoints with the same model
id remain distinct because selection identity includes the connection id.

## Chat vs Studio

```text
CHAT
  question → hybrid search (app) → trim chunks → LLM → answer + citations

STUDIO (button)
  pick artifact type → pick documents → optional prompt
    → retrieve (app) → LLM → builder → artifacts row + file

  infographic → generation model writes a brief
                → image_generation selection paints it → artifact file
  image       → generation model writes a prompt
                → image_generation selection
                → /images/generations (or /images on 404/405) → artifact file

  both formats take the one image_generation selection, which resolves to
  either a remote connection or the bundled local sd-server (sdcpp);
  sd-server is loopback, so that path needs no key and takes no egress
  decision
```

Infographic is drawn here as an image path, which is what shipped. Earlier
versions of this diagram and of [`api/05b`](api/05b-openai-compatible-connections.md)
showed it as a deterministic SVG/HTML builder needing only the generation role;
no such builder was written, and `formats.py` gives `infographic` the same
`requires_roles` as `image`.
