# SurfSense Integration Architecture

## System Topography
SurfSense operates via a multi-part integration model separating state syncing, background processing, and web presentation.

### 1. Data Sync Layer (Zero + Next.js + PostgreSQL)
- **Zero Cache (`zero-cache`)**: Acts as the real-time CVR (Client View Record) layer synchronizing mutations.
- **Flow**:
  - The Next.js frontend uses `@rocicorp/zero` to mutate or query data locally.
  - Zero Cache connects directly to the PostgreSQL upstream DB (`ZERO_UPSTREAM_DB` & `ZERO_CVR_DB`) polling for replication changes.
  - Conflicts and syncing are orchestrated between Zero Cache (`port 4848`) and Frontend API endpoints (`/api/zero/query` and `/api/zero/mutate`).

### 2. General API / Action Layer (FastAPI + Next.js)
- **FastAPI Layer**: When synchronous REST operations, authentication, or triggers are needed (like initiating a scrape), Next.js performs HTTP REST calls to the FastAPI backend at `BACKEND_PORT`: `8929/8000`.
- The FastAPI layer accesses the Postgres DB directly utilizing `asyncpg` and `SQLAlchemy`.

### 3. AI / RAG Processing Layer (SearXNG + Celery + FastAPI)
- **Search**: FastAPI contacts `SearXNG` at `http://searxng:8080` (Internal Docker network) for anonymized agent searches.
- **Offloaded Processing**:
  - Web scraping/Agent LLM processes are handed off from FastAPI to **Celery**.
  - `Celery` uses `Redis` at `redis:6379/0` as its Broker and Result Backend.
  - A detached **Celery Worker** process natively handles LangGraph workflows, processing large web contexts and storing vector outputs back into PostgreSQL via `pgvector`.
  - **Celery Beat** provides ongoing scheduled tasks, waking up the worker for cron jobs.

## Component Integrations Summary

| Origin | Target | Protocol | Description |
| :--- | :--- | :--- | :--- |
| **Next.js (Web)** | Zero Cache | WebSocket / HTTP | Local-first State Sync API. |
| **Next.js (Web)** | FastAPI | HTTP/REST | Triggering synchronous jobs, user logic. |
| **Zero Cache** | PostgreSQL | TCP (PG Protocol) | Standard relational sync and conflict resolution via CVR. |
| **FastAPI** | PostgreSQL | TCP (PG Protocol) | AsyncPG DB Reads/Writes. |
| **FastAPI** | Redis | TCP | Celery queue pipelining / PubSub. |
| **FastAPI** | SearXNG | HTTP | Metasearch queries. |
| **Celery Worker** | Redis | TCP | Consuming asynchronous processing queues. |
| **Celery Worker** | PostgreSQL | TCP | Saving LangGraph context and PgVector embeddings. |
