# Phase 3 — Commit-per-turn write path

> Build after Phase 2 (needs the working-copy backend) and Phase 1's `transaction`. Umbrella: [`00-umbrella-plan.md`](00-umbrella-plan.md).
>
> **Status: SHIPPED (2026-07-29).** All six work items landed; see per-item notes for the small deviations from the locked model (receipt derivation, message model seam, connector sync still pending).

## Objective

Turn the agent turn's working copy — plus editor saves and upload-extracted markdown — into **one atomic revision** per turn/save. This is where the single write path for all indexed content lands.

## Locked model

- **One revision per agent turn.** A new, small persistence middleware (alongside `kb_persistence`, same package area): `aafter_agent` → `diff_working_copy(thread-{id})` → one `KnowledgeStore.transaction` scope replaying the net writes/removes → `discard_working_copy`. Empty diff records nothing. The commit body is a **free function** so the stream-task disconnect fallback (`event_loop.py`) can run the identical routine when `aafter_agent` is skipped — same shape as today's `commit_staged_filesystem_state`.
- **`kb_persistence` is not touched.** Both middlewares coexist behind `KNOWLEDGE_STORE_ENABLED`; the old path keeps serving unflagged workspaces. Deletion of `kb_persistence`, `KBPostgresBackend`, `revert_service`, and the revision models happens at cut time (Phase 5), once every workspace is migrated and verified.
- **Aider-style commit messages.** A model generates a one-line Conventional Commits subject from the turn's diff; `Thread: {id}` trailer carries provenance. *As built:* no weak/fast model role exists yet (`LLMRole` has only `AGENT`), so the generator takes any chat model as its seam and is wired with the workspace agent LLM — a dedicated weak model is a one-argument swap. Generation failure (or the LLM-less disconnect path) falls back to a deterministic subject; a commit is never lost to message generation.
- **Honest attribution (Aider split).** Author = the acting user; committer = the agent identity. Autonomous writes (no user) author as the agent. `record`/`transaction` gained a `committer` parameter (defaults to author); conventions live in `knowledge_store/identities.py`.
- **Receipts survive, derived from the recorded diff.** *As built:* the middleware **creates** receipts post-commit from `list_changes(revision)` (same ground-truth discipline as the old commit body — no provisional flip needed on this path), revision id as `external_id`. On commit failure it returns `failed` receipts and **keeps the copy** so the thread's next turn recovers the work. Receipts are file-only: history tracks content, so a directory's existence is proven by the receipt of the first file written into it.
- **No Zero events here.** `document_created/updated/deleted` dispatches move with the derived rows (Phase 4) and projection (Phase 6); flag-on workspaces are dev/test until then.
- **Janitor.** Celery beat task (daily, 4:45) sweeps every workspace via `knowledge_store/janitor.py` → `prune_working_copies(older_than_seconds=24h)`. 24h far exceeds any turn; crashed-turn copies are reused (and committed) by the thread's next turn well before that.
- **Editor saves & upload-extracted markdown use the same commit path** (one write path): `services/document_revision_recorder.py` resolves the document's canonical path with the existing `doc_to_virtual_path` resolver (the same `/documents/...` namespace agents see), converts it to the repo path with `to_store_path` (C1 — the tree has no `documents/` root), and records one `transaction` per save, behind the flag. Editor messages are deterministic (`docs: save <filename>`) — there is no chat context to summarize. During coexistence a recording failure logs instead of failing the already-committed Postgres save; that flips at the Phase 5 cut. *Still pending:* connector-indexable content (Notion/Drive) routing through the same recorder on sync.
- **No Postgres content writes here** — chunk/embedding refresh is Phase 4 (triggered off the revision).

## Work items

1. ✅ New persistence middleware `main_agent/middleware/knowledge_store_persistence/` (`commit_turn.py` free-function body, `commit_message.py`, `middleware.py`, `builder.py`); wired into `stack.py` alongside `kb_persistence`, gated by cloud mode + `KNOWLEDGE_STORE_ENABLED`.
2. ✅ `committer` parameter on `record`/`transaction`; `Revision` carries both identities.
3. ✅ `event_loop.py` gained a second safety-net block calling the same free function — no state markers needed (the working copy on disk *is* the pending state; no copy = no-op, naturally idempotent).
4. ✅ Revision id surfaced as every success receipt's `external_id` (reaches state via the existing receipts channel). A dedicated event for the indexer/projector lands with Phase 4's trigger wiring.
5. ✅ Editor save (`editor_routes.save_document`) and upload markdown (`UploadDocumentAdapter.index`) call `record_saved_document`. ⏳ Connector-indexable sync not yet routed.
6. ✅ Celery beat janitor (`prune_knowledge_store_working_copies`, daily).

## Tests (shipped)

- ✅ One revision per turn with the turn's **net** changes; message carries subject + `Thread:` trailer; author = user, committer = agent. (`tests/integration/knowledge_store/test_commit_turn.py`, real git + real Redis)
- ✅ A turn that never touches the KB records nothing; an untouched copy records nothing.
- ✅ Lock contention yields `failed` receipts, keeps the copy, and the next commit recovers the work.
- ✅ Message generation: model subject used; deterministic fallback on model failure and on the LLM-less path. (`tests/unit/middleware/test_commit_message.py`)
- ✅ Builder gating: flag on + cloud only. Editor-save recording: one revision, author identity, filename in message. (`test_document_recorder.py`)
- ✅ Janitor prunes only copies older than the TTL, across workspaces. (`tests/unit/knowledge_store/test_janitor.py`)

## Out of scope

- Building the chunk/embedding index from the revision → Phase 4.
- Zero row projection → Phase 6.
- Deleting the legacy write path → Phase 5 (cut time).

## Resolved

- Commit message format → Aider-style, weak-model generated, `Thread:` trailer (was open question 1).
- Squash policy → one revision per turn is the model; the working copy nets intra-turn noise by construction (was open question 2).
- Author identity → Aider split (author = user, committer = agent).
