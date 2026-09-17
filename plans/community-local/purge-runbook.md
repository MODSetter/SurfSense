# T+30 — purge runbook

> Operational companion to [`00d-pivot-plan.md`](00d-pivot-plan.md), run thirty days after
> [`sunset-runbook.md`](sunset-runbook.md). The date is the one users were given in the launch
> email, the T+23 reminder and on `/sunset`, so it is a promise with a deadline rather than a
> cleanup task.

**Read the safety property first.** There isn't one. Every earlier stage of the wind-down is
reversible by unsetting a variable; this is not. The snapshot in stage 1 is the only way back, and
it exists for exactly thirty days before stage 6 destroys it. Do not start without it.

The work is done by [`scripts/purge_hosted_accounts.py`](../../surfsense_backend/scripts/purge_hosted_accounts.py),
which loops over `erase_account` — the same function support already uses for one account. That is
deliberate: a bulk `DELETE` drops the rows and leaves blobs and knowledge stores on disk forever,
which is not what a deletion promise means.

Stage numbering is the execution order. Each stage lists **checks** and **stop conditions**.

## The flag the script checks

The script refuses to run unless `SUNSET_MODE` is on, so it cannot be pointed at a live deployment
by mistake. It reads the **backend** variable — the one in `surfsense_backend/.env`, set at T-0 in
[`sunset-runbook.md`](sunset-runbook.md) stage 1 — because `app.config` loads that file at import.
The web app's copy in `surfsense_web/.env` is irrelevant here.

So if you run the script from `surfsense_backend/` on a host whose `.env` still has the flag from
T-0, it just works. If you run it somewhere else — a different checkout, a container shell, a
machine that never had the file — it will refuse even though production is very much wound down.
That refusal is the guard doing its job, not a bug; set the variable in that shell and re-run:

```bash
SUNSET_MODE=1 python -m scripts.purge_hosted_accounts
```

---

## Stage 0 — Confirm the date and the state

```bash
curl -s $API/health     # sunset: true, and has been for 30 days
date -u                 # on or after the date users were told
```

**Stop condition:** the date users were given has not arrived. Deleting early breaks the promise in
the direction that cannot be apologised for.

**Stop condition:** `sunset` is false. The purge script refuses to run in this state anyway — it is
a guard against pointing it at a live deployment.

---

## Stage 1 — Snapshot, and prove it restores

```bash
pg_dump "$DATABASE_URL" --format=custom --file=surfsense-prepurge-$(date -u +%Y%m%d).dump
```

A snapshot you have not restored is a hope, not a backup. Restore it into a scratch database and
count the users:

```bash
createdb surfsense_restore_check
pg_restore --dbname=surfsense_restore_check surfsense-prepurge-*.dump
psql surfsense_restore_check -c 'select count(*) from "user";'
```

Record that number. It is the figure stage 3 is measured against.

**Stop condition:** the restore errors, or the count is zero. Fix the snapshot before deleting
anything.

---

## Stage 2 — Dry run

The script reports and changes nothing unless `--execute` is passed.

```bash
cd surfsense_backend
python -m scripts.purge_hosted_accounts --verbose
```

**Checks**

- the count matches stage 1
- the addresses look like real users, not test accounts you meant to keep

**Stop condition:** the count is wildly different from the snapshot, or the list is empty. Either
means the script is pointed at the wrong database.

---

## Stage 3 — Purge

```bash
python -m scripts.purge_hosted_accounts --execute
```

It asks you to type a confirmation phrase. Progress prints every 100 accounts.

`erase_account` is idempotent and the script records failures rather than stopping, so an
interrupted or partially failed run is resumed by running the same command again — with `--yes` to
skip retyping the phrase.

**Checks**

```bash
python -m scripts.purge_hosted_accounts     # "no accounts remain"
```

Personal access tokens are `ON DELETE CASCADE` against the user, so they go with it. Verify rather
than assume:

```bash
psql "$DATABASE_URL" -c 'select count(*) from personal_access_tokens;'   # 0
psql "$DATABASE_URL" -c 'select count(*) from documents;'                # 0
```

**Stop condition:** accounts remain after a second run. Read the failures on stderr; do not move to
stage 4, because stage 4 destroys the blobs those accounts still reference.

---

## Stage 4 — Blob storage

`erase_account` purges each account's blobs as it goes, so this stage is for what is left over:
orphans from interrupted uploads, and the container itself.

Which commands apply depends on `FILE_STORAGE_BACKEND`:

```bash
grep FILE_STORAGE_BACKEND surfsense_backend/.env    # local | azure
```

- **local** — the object store directory, `FILE_STORAGE_LOCAL_PATH` (the `object_store` volume in
  compose). Confirm it is empty, then destroy the volume.
- **azure** — delete the container named by `AZURE_STORAGE_CONTAINER`.

**Check:** the store is empty or gone, and `/api/v1/export` is irrelevant by now — there is nothing
left to export.

---

## Stage 5 — Prove what survives

The service keeps running for licences and the scraper API. Postgres stays up for the scraper's own
operational rows; the licence routes need nothing in it, because Keygen is the system of record.

```bash
curl -s $API/health                                                         # ok
curl -s -o /dev/null -w '%{http_code}\n' -X POST -H 'content-type: application/json' \
  -d '{"email":"a real licensee"}' $API/api/v1/license/resend               # 200
curl -s -o /dev/null -w '%{http_code}\n' $API/<a scraper endpoint>          # serving
```

**Stop condition:** licence resend or the scraper API broke. The snapshot is still valid; restore
before investigating, because the thirty-day window on it has started.

Then announce nothing. The purge was already announced three times.

---

## Stage 6 — T+120

Destroy the snapshot from stage 1. Note the date in the calendar when you take it, not when you
plan to delete it.

After this, the deletion is complete and unrecoverable, which is the point.
