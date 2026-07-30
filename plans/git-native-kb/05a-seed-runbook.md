# Phase 5a — Production seed & flip runbook

> Operational companion to [`05-migration.md`](05-migration.md). That subplan says *what* the migration
> is and why; this one is the ordered list of commands and checks for doing it on production.
> Umbrella: [`00-umbrella-plan.md`](00-umbrella-plan.md).

**Read the safety property first.** Merging and deploying this work changes nothing at runtime,
because git-native behaviour needs **both** flags on: the process-wide `KNOWLEDGE_STORE_ENABLED`
(defaults `FALSE`, `app/config/__init__.py:543`) and the per-workspace
`workspaces.knowledge_store_enabled` (defaults false, migration 175). Seeding writes only to git and
to one metadata field; it never inserts or deletes a document row. So stages 0–6 are reversible by
doing nothing, and stage 7 is the first one that changes how a workspace behaves.

Stage numbering is the execution order. Each stage lists **checks** (verify before moving on) and
**stop conditions** (abort, do not continue).

---

## Stage 0 — Merge

The branch is `kb_git_mvp` on the fork (`origin` = `CREDO23/SurfSense`); upstream is
`MODSetter/SurfSense`.

**One PR: `kb_git_mvp → upstream/main`.** The merge is conflict-free, so there is nothing to gain from
routing through `dev` first. `main` already takes feature branches directly — `#1623`, `#1619`,
`#1617` from this fork all landed that way — so this is the repo's normal path, not a shortcut.

Why not promote `dev → main` instead: that ships everything sitting in `dev`, and the two are not
level. At the time of writing `dev` is **46 commits ahead** of `main` (searxng fallback,
model-connection fixes, an automations fix). Promoting would put all of it into the same production
deploy as this migration, giving two unrelated changes one blast radius.

The merge was **conflict-free** when last checked: this branch and `main` share the base `06c7e27c7`
(2026-07-24), `main` has moved 33 commits since, and none of them touch our files. Re-verify before
opening the PR — exit 0 means clean:

```bash
git fetch upstream
git merge-tree --write-tree upstream/main kb_git_mvp >/dev/null; echo "main: $?"
```

### Two rules

**Merge, never squash or rebase.** The repo allows all three, but its practice is merge commits, and
here it is load-bearing: our 127 commits must keep their SHAs on `main`, so that when someone later
syncs `main` into `dev` git recognises them as common history. A squash rewrites them into one new
SHA, and that sync becomes a re-application of the whole migration onto a branch that already has the
same content — conflicts across every file we touched.

**Merge only `upstream/main` into the branch, never `upstream/dev`.** Merging `dev` in would drag its
46 unreleased commits into the PR, which is the coupling this route exists to avoid.

### The PR

1. Merge `main` into the branch — and only `main`:
   ```bash
   git fetch upstream && git merge upstream/main
   ```
2. Run what CI runs, and note the baseline:
   ```bash
   cd surfsense_backend
   uv run pytest tests/unit tests/integration -q -p no:randomly --maxfail=100
   uv run ruff check . && uv run ruff format --check .
   ```
3. Open the PR against `upstream/main` and wait for `backend-tests`, `code-quality`, and `e2e-tests`.

**Checks**

- [ ] Alembic has a **single head** (`uv run alembic heads` → one revision, ours is `176`). Neither
      `main` nor `dev` has added a migration since our base, so this passes today; re-check after the
      merge anyway, because two heads makes the `migrations` container fail and halts the whole stack.
- [ ] Migrations 175 and 176 are **additive only** (new nullable columns) — no row rewrite, no long
      lock.
- [ ] `KNOWLEDGE_STORE_ENABLED` is **not** set true anywhere in the diff (compose, `.env.example`).
- [ ] `VERSION` resolves to `main`'s value (`0.0.35`, not this branch's stale `0.0.34`) — it decides
      the image tag in stage 1.

**Follow-up this creates:** `dev` won't have these 127 commits, and `main` won't have dev's 46, so
`dev` stops being a strict ancestor of `main`. Someone should merge `main` back into `dev` — the repo
already does this after a release (`Merge commit 'a89b3aa2...' into dev`). Content-wise it is clean
today: `git merge-tree --write-tree upstream/dev kb_git_mvp` also exits 0, so the two sets of changes
don't overlap. Tell whoever owns `dev`, and do it before they open the next `dev → main` promotion.

**Stop if** the test baseline has failures beyond the known pre-existing ones (currently 6, in
`google_maps`, `automations`, and a PAT static check — confirm by stashing your work and re-running).

---

## Stage 1 — Deploy (still inert)

The backend image serves four roles from one build, dispatched by `SERVICE_ROLE`
(`scripts/docker/entrypoint.sh:146-160`): `migrate` (one-shot, runs `alembic upgrade head` then
exits 0), `api`, `worker`, `beat`.

### What the merge to `main` publishes

`main` is the default branch, so that push runs the full build chain
(`.github/workflows/docker-build.yml`): it reads the `VERSION` file, finds the newest existing
`X.Y.Z.N` tag, and increments the build number. The images are pushed as
`ghcr.io/modsetter/surfsense-backend:X.Y.Z.<N+1>` **and** `:latest` (the `latest` alias is applied
only for the default branch or a `v*` tag, line 341), then `finalize_release` pushes the git tag.
With `VERSION` at `0.0.35` and build tags running to `0.0.35.2`, expect `0.0.35.3`.

This is also why the PR has to target `main` to be deployable at all: version computation is gated on
the default branch, so a merge into `dev` builds images but nothing gets a version tag or the `latest`
alias.

- [ ] Note the exact version tag the build produced, and deploy **that** rather than trusting
      `latest` to have settled.
- [ ] All four backend services must move to the same tag together — a worker on an older image than
      the API is the same failure mode as a split volume. Note that the compose services carry
      `com.centurylinklabs.watchtower.enable=true` labels: if anything Watchtower-like is watching
      `latest` in your deployment, services can update unattended and at different moments. Pin the
      version tag for this deploy so the fleet moves as one.

Then five checks on the deployed stack. The first is the one that can corrupt data; the rest are the
ones that fail quietly.

### Check 1.1 — the object-store volume is the *same* volume on api and worker

Git repositories live under `{FILE_STORAGE_LOCAL_PATH}/knowledge_store/{workspace_id}`
(`app/config/__init__.py:546-549`), i.e. on the `object_store` volume mounted at
`/app/.local_object_store` (`docker/docker-compose.yml:119`, `184`). The API writes editor saves and
the worker runs indexing, so if these two mount **different** volumes, each sees its own repository:
editor saves land in one, the index is built from the other, and the drift monitor will fight itself
forever. Prove they share one:

```bash
# in the api container
echo "$(date -u +%FT%TZ) api" > /app/.local_object_store/_volume_probe
# in the worker container
cat /app/.local_object_store/_volume_probe   # must print what api wrote
rm /app/.local_object_store/_volume_probe
```

- [ ] The worker reads what the API wrote.
- [ ] `/shared_tmp` is likewise the same volume on both (already required for uploads,
      `Dockerfile:129-131`).
- [ ] `beat` does **not** need either volume — it only schedules.

### Check 1.2 — the worker consumes the connectors queue

`reindex_knowledge_store` (the full-tree repair, and what the drift monitor auto-enqueues) is routed
to `{default}.connectors` (`app/celery_app.py:268`). With `CELERY_QUEUES` unset, the entrypoint
subscribes to default + `.connectors` + `.gateway` (`entrypoint.sh:95-104`). If someone has pinned
`CELERY_QUEUES` to just `surfsense`, every repair silently queues forever.

```bash
# in the worker container
echo "CELERY_QUEUES=${CELERY_QUEUES:-<unset, good>}"
celery -A app.celery_app inspect active_queues 2>/dev/null | grep -E "surfsense"
```

- [ ] `CELERY_QUEUES` unset, or includes `surfsense.connectors`.

### Check 1.3 — beat is actually running

The hourly sweep, the janitor, and the drift monitor are beat entries
(`app/celery_app.py:345-366`). Without beat there is no automatic recovery for a lost index task.

- [ ] A `SERVICE_ROLE=beat` service exists and its log shows the scheduler starting.

### Check 1.4 — schema is at head

```bash
# in the api container
alembic current    # expect: 176 (head)
```

- [ ] `176 (head)`, single head.

### Check 1.5 — disk

Git will hold a second copy of every document's markdown (working tree plus compressed objects).
Estimate before you commit to it:

```sql
SELECT pg_size_pretty(sum(length(coalesce(source_markdown, content)))::bigint) AS corpus,
       count(*) AS docs
FROM documents
WHERE coalesce(source_markdown, content) IS NOT NULL
  AND coalesce(source_markdown, content) <> 'Pending...';
```

Budget roughly **2.5×** that figure on the `object_store` volume (working tree + objects + head-room
for future revisions), on top of what the blob store already uses.

- [ ] Free space on the volume ≥ 2.5 × corpus, with margin.

**Stop if** any of 1.1–1.4 fails. None of them are recoverable by continuing.

---

## Stage 2 — Pre-flight state (nothing written yet)

Run against the production database (psql inside the `db` container, or your usual client):

```sql
-- 2.1 the columns exist
SELECT column_name FROM information_schema.columns
WHERE table_name = 'workspaces'
  AND column_name IN ('knowledge_store_enabled', 'last_indexed_revision');

SELECT column_name FROM information_schema.columns
WHERE table_name = 'chunks' AND column_name IN ('start_line', 'end_line');

-- 2.2 nothing is flipped yet
SELECT count(*) FILTER (WHERE knowledge_store_enabled) AS flipped,
       count(*)                                        AS total
FROM workspaces;

-- 2.3 no stamps yet
SELECT count(*) FROM workspaces WHERE last_indexed_revision IS NOT NULL;

-- 2.4 the shape of the job: documents per workspace
SELECT workspace_id, count(*) AS docs,
       pg_size_pretty(sum(length(coalesce(source_markdown, content)))::bigint) AS bytes
FROM documents
WHERE coalesce(source_markdown, content) IS NOT NULL
  AND coalesce(source_markdown, content) <> 'Pending...'
GROUP BY workspace_id ORDER BY 2 DESC;
```

**Checks**

- [ ] 2.1 returns both workspace columns and both chunk columns.
- [ ] 2.2 shows `flipped = 0`.
- [ ] 2.3 shows `0`.
- [ ] 2.4 gives you the batch plan: note the biggest workspaces and pick 2–3 **small, internal** ones
      as the canary set.
- [ ] `KNOWLEDGE_STORE_ENABLED` is still off in the api/worker environment (`env | grep KNOWLEDGE`).

---

## Stage 3 — Seed dry run (writes nothing)

Run **inside a container that mounts the object store** — the api or worker, not a fresh one-off
container, or the seeder will inspect an empty volume and report the whole fleet as missing.

```bash
mkdir -p /app/.local_object_store/ks-migration
cd /app && python scripts/migrate_knowledge_store.py \
  --out /app/.local_object_store/ks-migration/dry-$(date -u +%Y%m%dT%H%M%SZ).jsonl
```

Writing the report onto the volume matters: the container filesystem is ephemeral, and this file is
your audit trail and your resume point.

**Expected output.** Every unseeded workspace reads
`drift: missing=N extra=0 mismatched=0, N file(s)`, and the command **exits 1**. That is normal
pre-seed — a workspace that has not been seeded is not "ok". What matters is the prefix.

**Checks**

- [ ] No line begins `error:` — that is a real failure (unreadable store, mapping bug), not "not
      seeded yet". Triage before seeding.
- [ ] `extra=0` and `mismatched=0` everywhere. Non-zero here on a *fresh* store means something
      already wrote into these repositories and needs explaining.
- [ ] Workspaces reporting `0 file(s)` are genuinely empty (cross-check against 2.4).

**Stop if** any workspace errors, or `extra`/`mismatched` is non-zero.

---

## Stage 4 — Seed for real (still inert)

Seeding is safe to run while the site is live and taking writes, because with the flags off no other
writer touches git: the recorder and the turn-commit path both no-op for unflipped workspaces. There
is no lock contention to fear yet.

**4a. Canary set first** — the small internal workspaces from 2.4:

```bash
cd /app && python scripts/migrate_knowledge_store.py --yes \
  --workspace <A> --workspace <B> \
  --out /app/.local_object_store/ks-migration/seed-canary.jsonl
```

**4b. Then the fleet**, once the canary reports `ok`:

```bash
cd /app && python scripts/migrate_knowledge_store.py --yes \
  --out /app/.local_object_store/ks-migration/seed-fleet.jsonl
```

What one workspace's seed does: reads each document's `source_markdown` (falling back to `content`,
skipping blanks and `Pending...`), resolves a path per row (recorded marker first, title-derived
otherwise), writes them all as **one** revision authored by the migration identity, removes any
tracked path not in the desired set so a re-run converges, verifies parity by content address, then
stamps `virtual_path` back onto each row.

**Cost model.** No embeddings, no model calls, no re-chunking — the seed copies bytes, which is the
whole point of "adopt, don't rebuild". Runtime is dominated by writing git objects for the corpus
measured in 1.5, plus one metadata `UPDATE` per document.

**Checks**

- [ ] Every line reads `ok, N file(s)`; the summary reads `seeded: X ok, 0 failed of X`.
- [ ] No `Could not record seeded paths` in the logs (a marker failure leaves rows that cannot
      survive a retitle; re-running the seed repairs it).
- [ ] Marker coverage matches the seeded count:
      ```sql
      SELECT count(*) FROM documents
      WHERE document_metadata::jsonb ->> 'virtual_path' IS NOT NULL;
      ```
- [ ] Row counts unchanged from stage 2 (seeding must not create or delete documents):
      ```sql
      SELECT count(*) FROM documents;
      ```
- [ ] Disk grew by roughly the predicted amount, and free space is still comfortable.

**Stop if** any workspace fails. Re-running is idempotent and convergent, so a partial pass is safe
to resume — but understand *why* it failed first.

---

## Stage 5 — Verify parity

```bash
cd /app && python scripts/migrate_knowledge_store.py \
  --out /app/.local_object_store/ks-migration/verify-$(date -u +%Y%m%dT%H%M%SZ).jsonl
```

- [ ] Every workspace reads `ok`, and the command **exits 0**.
- [ ] Spot-check a handful of documents by hand: read the blob at head and diff it against
      `source_markdown` for the same row. Byte identity is the seed's whole claim.

**Stop if** anything is not `ok`. Do not flip a workspace whose parity fails — the drift monitor
would auto-enqueue a full re-embed for it (capped at 10 workspaces per nightly run), which is
exactly the cost this migration exists to avoid.

---

## Stage 6 — Turn on the global flag (still nothing flipped)

Set `KNOWLEDGE_STORE_ENABLED=TRUE` on **api** and **worker** (beat is harmless either way) and
redeploy those services. Nothing changes behaviour yet, because every workspace's column is still
false — this stage exists so that the flip in stage 7 is a single, reversible database write rather
than a deploy.

**Checks**

- [ ] `env | grep KNOWLEDGE_STORE_ENABLED` shows TRUE in api and worker.
- [ ] A chat turn on an unflipped workspace still behaves exactly as before (the compiled agent
      cache key includes the per-workspace flag, so no stale graph is served).
- [ ] Nothing new appeared under `/app/.local_object_store/knowledge_store/*/`.

---

## Stage 7 — Flip, in batches

```bash
cd /app && python scripts/migrate_knowledge_store.py --yes --flip \
  --workspace <A> \
  --out /app/.local_object_store/ks-migration/flip-A.jsonl
```

`--flip` refuses to run without `--yes`, only flips a workspace whose parity passed in the same
pass, and stamps `last_indexed_revision` to the store's head as it goes. That stamp is load-bearing:
leave it NULL and the hourly sweep reads the workspace as never-indexed and re-embeds the entire
tree.

**Immediately after the first flip, verify by hand**

- [ ] `SELECT id, knowledge_store_enabled, last_indexed_revision FROM workspaces WHERE id = <A>;`
      and the stamp equals the repository's head.
- [ ] One agent turn that writes a note: a new revision appears, and the document row appears in the
      UI with the right title and folder.
- [ ] One editor save on that note: it records, and the title is not silently renamed.
- [ ] Search returns seeded content for that workspace.

**Then watch the clock** (all UTC, `app/celery_app.py:345-366`):

- **:20 every hour** — the sweep. For a correctly stamped workspace it should be a **no-op**. If it
  re-indexes the whole tree, the stamp was wrong; stop flipping.
- **04:45 daily** — the working-copy janitor.
- **05:15 daily** — the drift monitor. Expect `status=ok`. This is the strongest single signal that a
  flip is healthy.

**Batch size.** Flip in groups of **≤ 10**, and let one nightly drift check pass between groups. Ten
matches the monitor's per-run repair cap, so if a whole batch goes wrong, one night's auto-repair can
cover it.

---

## Stage 8 — Watching, and rolling back

### What to watch

Metrics exist but only when an OTLP endpoint is configured; otherwise they no-op silently
(`app/observability/otel.py:62-84`), so **logs are the primary signal** unless you wire a collector:

| Signal | Where |
|---|---|
| `surfsense.knowledge_store.drift.check` counter, labels `workspace.id`, `status` | metrics, if OTLP configured |
| `surfsense.knowledge_store.record.outcome` counter, labels `flow` (`editor_save`/`sync_batch`/`turn_commit`), `status` (`recorded`/`noop`/`failed`) | metrics, if OTLP configured |
| `Knowledge store drift check for workspace %s: %s (missing=… extra=… mismatched=…)` | worker log, nightly |
| `Knowledge store index for workspace %s: revision=… indexed=… skipped=… failed=… deleted=… stamped=…` | worker log, per index run |
| `Could not acquire index_lock/write_lock for workspace …` | worker log — contention or a leaked lock |
| `Knowledge store recording failed for document %s in workspace %s` | api log — an editor save that did not reach git |
| `End-of-turn commit failed for workspace %s thread %s` | worker log — a turn whose writes were kept for next-turn recovery |

Alarm-worthy: any `failed=` other than zero in an index outcome, any `status=drift` after the first
night, and any lock error that repeats.

### Rolling back

- **One workspace:**
  ```bash
  cd /app && python scripts/migrate_knowledge_store.py --unflip --workspace <A>
  ```
  Clears the column and the stamp — deliberately, so a later re-flip does a full reconcile, since
  the legacy pipeline owns the chunks in between.
- **The whole fleet, immediately:** set `KNOWLEDGE_STORE_ENABLED=FALSE` and redeploy api + worker. No
  database write, no per-workspace bookkeeping.
- **What rollback does not undo:** revisions committed to git while the workspace was flipped stay in
  git, and the rows the indexer wrote stay in Postgres. That is harmless — the content is the same
  content — but re-flipping later should be treated as a fresh seed-and-verify.

---

## Known gaps to accept (or close) before flipping a UI-live workspace

These are tracked in the phase plans, not defects introduced by the migration:

1. **Phase 6 — the SSE channel.** Only the legacy middleware emits `document_created`/`updated`/
   `deleted`/`folder_deleted`; nothing on the git-native path does, so the in-chat document cards
   stop appearing for a flipped workspace. Zero replication of the rows still works, so the document
   list itself stays live, with a lag equal to the index queue.
2. **`DELETE /documents/{id}`** removes the row but not the git file, so the drift monitor resurrects
   the document.
3. **`PUT /documents/{id}`** retitles the row but leaves its marker and identity hash on the old
   path.
4. **Cosmetic:** storage paths still carry `.xml` for anything named from a title. Harmless, and
   retiring it is deferred.

Items 2 and 3 are the two that a normal user can trigger from the UI, so close them before flipping
a workspace with real users, or accept the behaviour knowingly.

---

## Appendix — one-line summary of each command

| Purpose | Command |
|---|---|
| Dry run, whole fleet | `python scripts/migrate_knowledge_store.py --out <report>` |
| Dry run, one workspace | `… --workspace <id>` |
| Seed for real | `… --yes` |
| Seed + flip | `… --yes --flip --workspace <id>` |
| Roll one workspace back | `… --unflip --workspace <id>` |
| Force a full reindex of one workspace | enqueue `reindex_knowledge_store` for that id |
