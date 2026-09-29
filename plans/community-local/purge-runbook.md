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

## The flags the script checks

The script refuses to run unless `is_sunset_mode()` is true. That function is two variables, not
one: `SUNSET_MODE` must be truthy **and** `DEPLOYMENT_MODE` must be `cloud`. Production already
sets `DEPLOYMENT_MODE=cloud` (see `.env.example` beside `SUNSET_MODE`, and ADR 0023). The half that
is easy to lose is `DEPLOYMENT_MODE` when you are in a different shell, container or checkout that
never loaded the backend `.env`.

It reads the **backend** variables — the ones in `surfsense_backend/.env`, set at T-0 in
[`sunset-runbook.md`](sunset-runbook.md) stage 1 — because `app.config` loads that file at import.
The web app's copy of `SUNSET_MODE` in `surfsense_web/.env` is irrelevant here.

So if you run the script from `surfsense_backend/` on a host whose `.env` still has both values
from T-0, it just works. If you run it somewhere else — a different checkout, a container shell, a
machine that never had the file — it will refuse even though production is very much wound down.
That refusal is the guard doing its job, not a bug. Setting only `SUNSET_MODE` in that shell is not
enough; set both and re-run:

```bash
DEPLOYMENT_MODE=cloud SUNSET_MODE=1 python -m scripts.purge_hosted_accounts
```
