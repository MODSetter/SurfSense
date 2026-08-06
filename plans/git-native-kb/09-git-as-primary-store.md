# Phase 9 — Git as the primary store (body)

> **DESIGN (2026-08-06).** The turn that renamed the model out loud: for a
> flagged workspace git stops being a *log the row also writes to* and becomes
> the **primary store for the body**. Git owns the body; Postgres owns metadata
> (`document_type`, `document_metadata`, identity) and the derived index.
> Depends on Phases 3/4/6/7/8. Umbrella: [`00-umbrella-plan.md`](00-umbrella-plan.md).
> **Amends** the shared contract: C1 states git is primary for the body and
> Postgres keeps metadata; C5's projection preserves the row's metadata and
> defaults `NOTE` only for a git file that has no row.
>
> **Scope decision (2026-08-06).** Only the *ownership model* below is settled
> now — it is already the running behavior (C1/C5). The clean switch and the
> `record_*` rename are **the Phase 5 cut's re-org**, not a separate phase: they
> delete the legacy arm and are churn if done mid-transition, while the dual-run
> behind flags is correct meanwhile. This doc records the target shape they land in.

## Objective

One honest sentence per side of the boundary:

- **Git owns the body** — one file per document, the raw source markdown, read
  and written verbatim. The agent reads/edits/greps it natively; the commit is a
  plain diff. Nothing has to strip or wrap on the way through.
- **Postgres owns the metadata** — `document_type`, `document_metadata`,
  identity (`unique_identifier_hash`), folder — and the derived index (chunks,
  embeddings, `source_markdown` cache). It stays the source of truth for
  everything git doesn't hold.

The projection's `document_type = NOTE` default stops being a wrinkle: the only
case it fires is a git file with no row, which is an **agent-authored new file
— and that really is a note**. Typed documents (uploads, connectors) always get
their row from their creator, never from a bare git file, so the default is
correct rather than a guess we paper over.

## The switch, stated plainly

There is **one** decision, read once per write, and it lives in **one place** —
the facade create verb, not scattered across callers:

```
async def save_documents(session, ingredients):
    if knowledge_store_enabled_for(workspace):        # git-first
        row = build_row(session, ingredients)         # Postgres owns metadata
        revision = write_body_to_git(row)             # git owns the body
        return await project_revision(...)            # refresh body-derived fields
    else:                                             # postgres-only
        return build_row(session, ingredients)
```

Two disjoint arms, **no confused middle**. A flagged workspace writes the body
to git for *every* verb; an unflagged one never touches git. The row build is
honest, not a log: Postgres is the metadata owner, so authoring the row *is* the
metadata write; git gets the body when flagged.

The git-first arm needs no new row-building code — Phase 6's `project_revision`
already materializes/refreshes the row synchronously at commit. Deletes and
moves are already single facade calls
(`record_deleted_documents`/`record_moved_documents`), so they become
switch-shaped the moment the verb branches internally.

## Verbs: say what they do

The `record_*` names are the "log" vocabulary that started this. Rename at the
facade and the module verb to the intent (git-first for the body, so these *are*
the write):

| today | becomes |
|---|---|
| `record_prepared_documents` | `save_documents` |
| `record_markdown_files` | `write_files` |
| `record_moved_documents` | `move_documents` |
| `record_deleted_documents` | `remove_documents` |

Mechanical rename + call-site update; no behavior change in this item.

## Deferred: on-disk front-matter (OKF-as-stored-truth)

An earlier draft of this phase stored each document as a lossless OKF concept —
front-matter (its metadata + a `surfsense:` machine block) plus body — so a
clone was whole and the row rebuilt from the file. **Deferred**, because inline
front-matter fought every operation:

- The agent worktree serves bytes verbatim and line-numbers them for C2
  citations. Front-matter lines shift the body's line numbers, so every
  `aread` had to strip and every `aedit`/`awrite` had to re-wrap — and doing
  that at the working-copy boundary meant re-baselining git's index so the
  end-of-turn diff didn't see the header churn. That is the "patchy" machinery
  we stopped at.
- The projection and indexer would each have to split the concept before
  reading the body.

Not worth it for v1: Postgres is the durable metadata store (backed up), and a
rebuild recovers body + chunks. This is **reversible** — front-matter can be its
own later phase when a real need appears (repo portability, connect-your-own
remote git). **Cost of deferring:** git alone is not self-describing — a bare
clone is bodies without types/metadata, and a rebuild from an *empty* Postgres
recovers body + chunks but not type/metadata/identity. Disaster-recovery-from-
git-alone is not a v1 goal, so this is an accepted trade, not a gap.

`app/services/okf/` stays exactly what it is today: a **read projection** for
export and MCP, rendered from the row. Untouched.

## Projection: preserve the row's metadata

`index/rows.py::upsert_row` and `index/project.py` keep today's behavior — read
the raw body from git, index/cache it, and preserve the row's Postgres-owned
`document_type`/`document_metadata`. The only synthesis is for a git file with
no row: `document_type = NOTE`, title from the path. As above, that case is an
agent-authored note, so it is correct.

## Seed writes bodies

Phase 5's per-workspace seed ([`05-migration.md`](05-migration.md),
[`05a-seed-runbook.md`](05a-seed-runbook.md)) copies the raw body out of
Postgres, unchanged by this phase. Metadata stays in the row; byte-parity
verification compares the body.

## Scope: the switch is the Phase 5 cut, not a now-task

The clean switch is the **end of the transition**, so it lands with the Phase 5
cut, not before. Doing it mid-transition is churn: the cut deletes the legacy
arm per workspace after byte-parity, so a partial reshape now gets partly redone.
Until then the dual-run behind flags is correct — a flagged workspace already
takes the git path, an unflagged one never touches git, and the flag makes which
is which explicit. When the cut runs, the write paths take the target shape:

- **Creates that build a row then record it** — notes-with-body, extension
  pages, circleback, the editor save path, the indexing pipeline — call the
  branching verb; the git-first arm writes the body and projects, and the
  legacy arm is deleted so the verb is unconditional git-first.
- **Deletes / moves** — already one facade verb each; the cut drops their
  legacy no-op arm.

## Cost to existing data

- **No prod rewrite outside a flip.** Unflagged workspaces are untouched;
  rollback stays a flag flip.
- **No on-disk format change.** Git files stay raw bodies, byte-identical to
  what Phases 3–7 already write, so nothing already flipped needs rewriting.

## Work items (all deferred to the Phase 5 cut)

1. [ ] Make the create verb the single branch point and delete the legacy arm;
       repoint the ~5 create sites. Deletes/moves drop their legacy no-op arm.
2. [ ] Rename `record_*` → intent verbs (table above); update call sites.
3. [ ] Suites green: KB, projection, migration.

## Open questions

1. ~~Store metadata as on-disk front-matter so git is self-describing?~~
   **Deferred 2026-08-06** (see "Deferred" above): fought too many operations
   for the robustness it bought; Postgres keeps metadata. Revisit for a real
   portability/remote-git need.
