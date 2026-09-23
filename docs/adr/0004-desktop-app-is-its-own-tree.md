# ADR 0004: The desktop app is its own tree on FastAPI, SQLite and Huey, with no accounts

- **Status:** Accepted
- **Date:** 2026-09-03
- **Source:** [Umbrella plan L17](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/00-umbrella-plan.md#L17), [Umbrella plan L86–98](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/00-umbrella-plan.md#L86-L98), [Umbrella plan L104](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/00-umbrella-plan.md#L104), [Data model L6–13](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/00c-data-model.md#L6-L13), [Connections plan L83–87](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/api/05b-openai-compatible-connections.md#L83-L87)

## Context

Hosted SurfSense runs on Postgres with Zero, Celery with Redis, LangGraph for chat, and a Next.js app with accounts. The desktop app is airgapped and local-first: one user and one database file, `surfsense.db`. Its users and developers already know SurfSense's domain words from the hosted product. How the pieces fit today is in [the overview](../architecture/overview.md).

## Decision

- `surfsense_local/` is a new tree. It is not a feature flag on the Docker stack.
- The API is FastAPI on uvicorn: the same stack as the hosted backend, with native OpenAPI for the frontend and SSE for chat. Freezing it with PyInstaller was a known risk, handled by a spike rather than by choosing a smaller framework.
- Data lives in SQLite (`surfsense.db`) and jobs in Huey on SQLite (`huey.db`). Chat is retrieve-first RAG instead of LangGraph. The UI is a Vite SPA inside Electron.
- There is no auth: no users, memberships or tokens.
- The data model is a subset of the SurfSense domain and keeps its words: workspace, document, chunk, artifact, chat thread, chat message. Names are fixed when code is copied in, so `new_chat_threads` becomes `chat_threads`.
- Out of scope for this tree: Docker Compose, Postgres, Zero, Redis, Celery, LangGraph, the git knowledge base, scrapers, MCP, multi-seat LAN and Stripe.

## Consequences

- Electron spawns the API, one worker per job queue and `llama-server` as sidecars, and opens the window once the API answers `/health` ([`electron/src/main/index.ts`](../../surfsense_local/electron/src/main/index.ts)).
- Nothing authenticates a request, so the API binds `127.0.0.1` ([`api/config.py`](../../surfsense_local/backend/api/config.py)) and has to stay there. The connections plan records that binding it externally would make connection URLs an SSRF boundary, to be redesigned before any such release.
- Nothing can tell two users apart, and multi-seat use on a LAN is out of scope.
- Migrations, retrieval and the job queues have their own records: [ADR 0005](0005-hand-written-migrations.md), [ADR 0006](0006-hybrid-retrieval.md) and [ADR 0008](0008-two-job-queues.md).
