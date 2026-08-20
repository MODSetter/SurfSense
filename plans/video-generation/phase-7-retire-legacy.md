# Phase 7 — Retire the legacy generation path

**Status:** DESIGN.
**Parent spec:** [`00-umbrella-plan.md`](00-umbrella-plan.md).
**Depends on:** Phases 1–6 green end-to-end (the skill path fully replaces the graph).

## 1. Goal

One way to make a video: the skill loop. Delete the monolithic graph/tool/Celery surface it replaces.

## 2. Removals

- **Tool:** drop `create_generate_video_presentation_tool` from `deliverables/tools/index.py`; delete `deliverables/tools/video_presentation.py`.
- **Task:** delete `app/tasks/celery_tasks/video_presentation_tasks.py`.
- **Graph:** delete `app/agents/video_presentation/` (`graph.py`, `nodes.py`, `state.py`, `prompts.py`).
- **Frontend renderer:** removed in Phase 6.
- **DB:** `VideoPresentationRun` / `VideoPresentationStatus` — keep only if Phase 8 backfill needs them; otherwise schedule a drop migration after backfill.

## 3. Risks / grep before deleting

- **Receipt/activity consumers:** anything keyed on receipt `type="video_presentation"` or the `generate_video_presentation` activity descriptor (frontend activity rendering, analytics).
- **`wait_for_deliverable` / `deliverable_wait`:** confirm no other deliverable depends on the video row polling before removing its usage.
- **Legacy artifact reads:** `_legacy_ref` / `legacy.kind == "video"` handling in `artifacts_routes.py` — retained until Phase 8 decides legacy fate.

## 4. Checks

- Deliverables agent test: a video request drives the skill loop only; no Celery task is enqueued and no `generate_video_presentation` symbol is importable.
- Grep gate: no remaining references to the deleted modules/symbols.

## 5. Exit criteria

1. The video graph, Celery task, and tool are deleted.
2. No code path dispatches the old pipeline.
3. Tests referencing the old path are removed or ported to the skill path.
