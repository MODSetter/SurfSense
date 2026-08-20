# Phase 8 — Retire the legacy generation path

**Status:** DESIGN.
**Parent spec:** [`00-umbrella-plan.md`](00-umbrella-plan.md).
**Depends on:** **Phase 7 complete** — every legacy video artifact backfilled to MP4 or explicitly frozen — **and** `VIDEO_SANDBOX_RENDERING_ENABLED=TRUE` stable in production. This is the **last** phase: nothing here runs until backfill has drained.

## 1. Goal

Collapse to one video implementation. Until now the legacy LangGraph path and the new skill path have **coexisted** behind `VIDEO_SANDBOX_RENDERING_ENABLED` (flag off ⇒ legacy still authoritative; Phases 5–6 were additive and deleted nothing). This phase removes the flag and deletes the entire legacy subtree in one cut — safe now because backfill left no legacy-shaped artifact that still needs it.

**Why deletions were deferred to here.** The legacy `scene_codes` + per-slide audio + the browser renderer are the **inputs and viewer** for un-migrated artifacts. Deleting them before Phase 7 finishes would strand exactly the videos we promised never to force users to regenerate. So every removal — backend and frontend — lands together, gated on backfill.

## 2. Remove the flag (make the new path the only path)

- **`app/config`:** delete `VIDEO_SANDBOX_RENDERING_ENABLED` and its `.env.example` line.
- **`deliverables/tools/index.py::load_tools`:** drop the `if config.VIDEO_SANDBOX_RENDERING_ENABLED` branch — always register the skill path (`synthesize_narration`), never the legacy tool.
- **`deliverables/agent.py`:** stop conditionally composing the prompt — the video-skill routing block becomes unconditional.

The legacy pipeline has a **wide consumer surface** beyond the graph — tool catalog, streaming activity, receipts, public-chat sharing, Zero publication, billing, config, and a dozen frontend registrations. The inventory below is grouped by subsystem; the §7 grep gate is the backstop for anything missed. Where the new path **reuses** a symbol, it is called out under "retain".

## 3. Backend — legacy authoring & orchestration

- **Tool:** delete `deliverables/tools/video_presentation.py` and its import/registration in `deliverables/tools/index.py` + `tools/__init__.py`.
- **Task:** delete `app/tasks/celery_tasks/video_presentation_tasks.py` **and** drop its registration line in `app/celery_app.py` (`"app.tasks.celery_tasks.video_presentation_tasks"`).
- **Graph:** delete `app/agents/video_presentation/` (`graph.py`, `nodes.py`, `state.py`, `prompts.py`, `utils.py`) — **after** confirming Phase 3 lifted the TTS (`create_slide_audio`) and language handling into `synthesize_narration`, so nothing still imports it.
- **Deliverables integration surface (grep each, remove the video entry):**
  - `shared/tools/catalog.py` — the `name="generate_video_presentation"` catalog entry.
  - `main_agent/context_prune/prune_tool_names.py` — the `"generate_video_presentation"` name.
  - `shared/receipts/receipt.py` — the legacy `video_presentation` receipt descriptor (the receipt *framework* is Tier A — retain; only the video-specific type/value goes).
  - `streaming/handlers/tools/deliverables/generate_video_presentation/` (the `emission.py` tool-card/terminal handler) + its wiring in `.../deliverables/tool_names.py`.
  - `deliverables/deliverable_wait.py` — remove the `generate_video_presentation` mention/branch (podcast still uses row-polling; leave that).
  - `deliverables/system_prompt.md` — drop the `generate_video_presentation` bullets and the `"video_presentation"` `artifact_type` enum value (the base prompt now unconditionally routes video → skill, per §2).

## 4. Backend — persistence, serving & public chat

- **Writers:** delete `app/artifacts/media/video/record.py` (audio-as-primary + `scene_codes` in metadata) and `app/artifacts/media/video/storage.py` (per-slide audio offload).
- **Routes:** delete `/artifacts/{id}/video` and `/artifacts/{id}/slides/{n}/audio` in `artifacts_routes.py`; remove `_legacy_ref` / `legacy.kind == "video"` handling there.
- **Public chat (shared snapshots):** `public_chat_service.py` (`get_snapshot_video_presentation`, the `"generate_video_presentation"` tool allowlist entry, `snapshot_data["video_presentations"]` handling) and `public_chat_routes.py` (`/{share_token}/video-presentations/{id}` + `.../slides/{n}/audio`). **Decision required (§6):** already-shared public snapshots embed the legacy shape; either repoint public playback at the migrated MP4 artifact or accept that pre-migration shared links degrade.
- **Blobs:** delete the per-slide audio objects (backfill inputs) — safe now that Phase 7 consumed them; snapshot/verify counts first.

## 5. Backend — DB, Zero, billing, config

- **DB models + migration:** remove `VideoPresentationRun` / `VideoPresentationStatus` from `app/db.py` and add a **new** drop migration (do not edit `107_add_video_presentations_table` / `179_add_video_presentation_artifact_id` / `180_slim_video_presentation_runs` — history is immutable). The deferred queued render fleet (umbrella §4) does **not** revive this table — it would use a *lean, generic* render-job row (job id, status, artifact_id, error), not this video-specific record.
- **Zero publication:** `app/zero_publication.py` — remove `VIDEO_PRESENTATION_RUN_COLS` and the two `"video_presentation_runs"` registrations (this is what streamed run status to the browser; the new path has no run row).
- **Billing:** `services/billable_calls.py` + `celery_tasks` usage — the `usage_type="video_presentation_generation"` path and `QUOTA_DEFAULT_VIDEO_PRESENTATION_RESERVE_MICROS`. **Retain if reused:** Phase 3 narration billing may keep a usage-type; confirm whether to rename vs delete before removing the quota constant.
- **Config — `app/config` + `.env.example`, delete vs retain (do not blanket-remove):**
  - **Delete:** `VIDEO_PRESENTATION_MAX_SLIDES` (unless the skill still enforces a cap), `QUOTA_DEFAULT_VIDEO_PRESENTATION_RESERVE_MICROS` (per billing decision above).
  - **Retain (reused by the new path):** `VIDEO_PRESENTATION_FPS` and `VIDEO_PRESENTATION_DEFAULT_DURATION_IN_FRAMES` (Phase 1 `props.json` single source of truth) and `VIDEO_PRESENTATION_DEFAULT_LANGUAGE` (Phase 3 narration). Leave these; they are not legacy-only.

## 6. Frontend — legacy tool UI, player & registrations

Phase 6 added the `<video>` path and branched on PRIMARY mime, **keeping** the old player so un-migrated (audio + `scene_codes`) artifacts still rendered. With backfill done, every video artifact is `video/mp4`, so remove:

- **Player & compile path:** `lib/remotion/compile-check.ts` (the `new Function` path), `components/tool-ui/video-presentation/combined-player.tsx`, `lib/remotion/constants.ts` if unused, and the mime-branch fallback in the viewer (leaving only `Mp4VideoPlayer`).
- **Legacy tool-UI + its status poller:** `components/tool-ui/video-presentation/generate-video-presentation.tsx` (the polling `StatusPoller`/`VideoPresentationPlayer` that hit the deleted run endpoints) and the `tool-ui/video-presentation/index.ts` + `tool-ui/index.ts` re-exports.
- **Tool registrations/UI wiring:** `assistant-ui/assistant-message.tsx` (`GenerateVideoPresentationToolUI` dynamic import + `generate_video_presentation` map entry), `assistant-ui/thread.tsx` tool allowlist, `public-chat/public-thread.tsx` map, `contracts/enums/toolIcons.tsx` (icon + label), `features/chat-artifacts/model/artifact.ts` (`generate_video_presentation: "video"`), `features/chat-artifacts/lib/collect-artifacts.ts` (`video_presentation_id` legacy path), `components/settings/roles-manager.tsx` (`video_presentations` permission block — confirm it is video-generation, not an unrelated capability).
- **Zero client:** `zero/schema/video-presentation-runs.ts` + its `zero/schema/index.ts` registration, and `zero/queries/video-presentation-runs.ts` + its `zero/queries/index.ts` (`videoRuns`) registration.
- **Deps** from `surfsense_web/package.json`: `@remotion/player`, `@remotion/web-renderer`, `@remotion/media`, `@babel/standalone` (and `remotion` if nothing else imports it).

## 7. Tests to remove or port

- Delete/port: `tests/unit/agents/video_presentation/*`, `tests/unit/agents/test_video_presentation_graph.py`, `tests/unit/tasks/test_video_presentation_billing.py`, and the video assertions in `tests/unit/tasks/chat/test_activity_contract.py`, `tests/unit/observability/test_helpers.py`, `tests/unit/routes/test_artifacts_routes.py`.
- `scripts/backfill_video_artifacts.py` + `tests/unit/scripts/test_backfill_video_artifacts.py`: the *older* runs→artifact migrator, unrelated to Phase 7's `backfill_video_mp4.py`. Optional cleanup once its one-time migration is historical — leave unless confirmed obsolete.

## 8. Risks / grep before deleting

- **Backfill ledger:** confirm Phase 7 reports zero un-handled legacy artifacts (all Backfilled or Frozen) before deleting audio blobs and legacy reads.
- **Public-chat snapshots:** resolve the shared-link decision (§4) before deleting the public endpoints.
- **Receipt/activity consumers:** anything keyed on receipt `type="video_presentation"` or the `generate_video_presentation` activity descriptor (analytics, activity rendering).
- **Billing/config reuse:** verify the retained-vs-deleted split (§5) against actual new-path usage before removing any constant.
- **Shared frontend imports:** grep other consumers of the dropped web libs (`@remotion/*`, `@babel/standalone`) before removal.

## 9. Checks

- Deliverables agent test: a video request drives the skill loop only; no Celery task enqueued and no `generate_video_presentation` symbol importable.
- **Grep gate (backstop):** no remaining references to `video_presentation` / `VideoPresentation` / `generate_video_presentation` / `VIDEO_SANDBOX_RENDERING_ENABLED` outside history (alembic) — backend and frontend.
- Legacy routes `/video`, `/slides/{n}/audio`, and public `/video-presentations/*` return 404.
- Frontend bundle no longer contains `remotion`/`@babel/standalone`; Zero schema has no `video_presentation_runs` table; typecheck + lint clean.

## 10. Exit criteria

1. The flag and **every** legacy subsystem — authoring (graph/task/tool/catalog/receipt/activity), persistence/serving (writers/routes/blobs/public-chat), DB + Zero + billing, and the full frontend tool-UI/player/Zero surface — are deleted; retained-and-reused config is explicitly kept.
2. No code path dispatches the old pipeline; the skill loop is the single way to make a video.
3. `VideoPresentationRun` tables are dropped via a new migration; Zero no longer publishes the run.
4. Tests referencing the old path are removed or ported; the grep gate is clean.
