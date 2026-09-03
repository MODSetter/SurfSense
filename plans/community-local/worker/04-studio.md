# Worker — Phase 4: Studio pipeline

> Copy one builder from cloud Studio. Schema: [`../00c-data-model.md`](../00c-data-model.md) (`artifacts`).

## Goal

One artifact type via fixed pipeline.

## Work

- `@task studio_job(artifact_id)` on same worker (`-w 1`).
- retrieve (`search.py`) → LLM → one builder (summary **or** podcast — pick at start).
- Artifact file on disk; `ARTIFACT` document; `artifacts.status=ready`.

## Acceptance

- API enqueues → file on disk + DB `ready`.

## Interface from API

[`../api/04-studio.md`](../api/04-studio.md).
