# T-0 — sunset and scale-down runbook

> Operational companion to [`00d-pivot-plan.md`](00d-pivot-plan.md). That plan says *what* the
> wind-down is and why; this is the ordered list of commands and checks for doing it on production.
> The purge that follows a month later is [`purge-runbook.md`](purge-runbook.md).

**Read the safety property first.** Every sunset behaviour is behind `SUNSET_MODE`, which defaults
off in the backend (`app/sunset.py`) and in the web app (`lib/sunset.ts`). Both treat unset and
empty as off, so the self-host stack and the pre-sunset hosted service take the same branch. Stages
1 to 4 are therefore reversible by unsetting a variable and restarting a process; stage 5 is the
first one that stops something, and stage 6 is the first that users cannot un-see.

Stage numbering is the execution order. Each stage lists **checks** (verify before moving on) and
**stop conditions** (abort, do not continue).

Substitute your own host for `$API` and `$WEB` throughout.

## Two variables, two places

The flag is two variables in each of two files. `SUNSET_MODE` is the one you set today.
`DEPLOYMENT_MODE=cloud` is the one it depends on: both processes ignore `SUNSET_MODE` unless the
deployment mode is `cloud`, so that a self-hosted install with a copied `.env` cannot sunset itself.
Production has had `DEPLOYMENT_MODE=cloud` all along, which is why it is easy to forget and easy to
lose in a different shell, container or checkout.

| Set in | Reaches | Needs | Turns on |
|---|---|---|---|
| `surfsense_backend/.env` | the API process | `DEPLOYMENT_MODE=cloud` and `SUNSET_MODE` | `sunset: true` on `/health`, writes return 410 |
| `surfsense_web/.env` | the Next process | cloud mode, from `DEPLOYMENT_MODE=cloud` or a build made with `NEXT_PUBLIC_DEPLOYMENT_MODE=cloud`, and `SUNSET_MODE` | app routes redirect to `/sunset` |

Setting `SUNSET_MODE` in only one file is the likeliest way to get a half-sunset: a backend refusing
writes behind an app that still looks open, or an app redirecting to `/sunset` while the backend
happily accepts writes.

`SUNSET_MODE` is read at **runtime**, per request — the backend through `os.getenv`, the web app in
`proxy.ts`. It is not baked into a build, which is why the web one is not a `NEXT_PUBLIC_*`
variable: sunsetting is a restart, never a rebuild. The backend reads `DEPLOYMENT_MODE` the same
way, defaulting to `self-hosted`. The web app takes the runtime `DEPLOYMENT_MODE` and falls back to
the build-time `NEXT_PUBLIC_DEPLOYMENT_MODE`.

`SUNSET_MODE` accepts `1`, `true`, `yes` or `on`; anything else, including empty, means off.
`DEPLOYMENT_MODE` must be exactly `cloud`. Stages 1 and 3 set `SUNSET_MODE` one file at a time on
purpose, so that if something breaks you know which half did it.

> The Docker Compose stack — dev and self-host, not production — passes the web flag from
> `docker/.env` into the frontend container instead. Production sets both files directly.

---

## Stage 0 — Before you touch anything

Confirm the launch gates are green, then capture the "before" state so you can tell later whether
something you did caused a change.

```bash
curl -s $API/health                                   # sunset: false
curl -s -o /dev/null -w '%{http_code}\n' $WEB/dashboard   # 200
# and whatever lists your running services, e.g. on the compose stack:
#   docker compose ps --format '{{.Service}}\t{{.Status}}'
```

Take a Postgres snapshot now, not at T+30. The purge has its own snapshot, but this one covers
stages 5 and 6 — and it is the only thing that makes a stopped service a recoverable mistake.

Confirm both processes are in cloud mode before going on: `DEPLOYMENT_MODE=cloud` in
`surfsense_backend/.env`, and for the web app either `DEPLOYMENT_MODE=cloud` in `surfsense_web/.env`
or a build made with `NEXT_PUBLIC_DEPLOYMENT_MODE=cloud`. Without it the stages below change
nothing, and nothing will say why.

**Stop condition:** `/health` already reports `sunset: true`. Something is set that you did not set;
find out what before continuing.

**Stop condition:** either process is not in cloud mode. That is not this runbook's to set: a
production that is not in cloud mode has a different problem, so find out why first.

---

## Stage 1 — Backend flag

```bash
# surfsense_backend/.env
SUNSET_MODE=1
```

Restart the API process so it picks up the file. The flag is read per request, so no rebuild.

**Checks**

```bash
curl -s $API/health                                            # sunset: true
curl -s -o /dev/null -w '%{http_code}\n' -X POST $API/api/v1/documents      # 410
curl -s -o /dev/null -w '%{http_code}\n' -X POST $API/auth/jwt/login        # NOT 410
curl -s -o /dev/null -w '%{http_code}\n' -X POST $API/api/v1/license/resend # NOT 410
curl -s -o /dev/null -w '%{http_code}\n' $API/api/v1/export                 # 401, NOT 410
```

Export must answer 401 rather than 410: it is a `GET`, and it is the only thing users have left.

If `/health` still reports `sunset: false` after the restart, the API process is not seeing both
variables. Check, in the environment of the running process and not only in the file, that
`DEPLOYMENT_MODE` is exactly `cloud` and that `SUNSET_MODE` is one of the accepted spellings, and
that the process restarted was the one serving `$API`.

**Stop condition:** export or login returns 410. Unset the flag, restart, and work out why before
retrying — a sunset that blocks export is worse than no sunset at all.

**Reverse:** remove the line, restart the API process.

---

## Stage 2 — Legacy desktop clients follow automatically

Nothing to do. Stage 1 is what flips them: v0.0.40 reads `sunset` from `/health` once at startup
(contract 4) and loads the live `/sunset` instead of its bundled frontend.

**Know the failure mode.** The check is once, at startup, with a 3-second timeout and no retry, and
it fails open. A client whose check times out runs against a sunset backend and sees 410s on write
rather than the sunset page. It corrects itself on next launch. If support hears "the app just
errors", that is this, and the answer is "restart it" — not a bug.

---

## Stage 3 — Web flag

```bash
# surfsense_web/.env
SUNSET_MODE=1
```

Restart the Next process. Read per request by `proxy.ts`, so no rebuild here either — that is why the
variable is not `NEXT_PUBLIC_*`.

**Checks**

```bash
curl -s -o /dev/null -w '%{http_code} %{redirect_url}\n' $WEB/dashboard/1   # 307 -> /sunset
curl -s -o /dev/null -w '%{http_code}\n' $WEB/sunset                        # 200, no loop
curl -s -o /dev/null -w '%{http_code}\n' $WEB/license                       # 200
curl -s -o /dev/null -w '%{http_code}\n' $WEB/pricing                       # 200
```

The portal has to stay reachable: it is where everyone is being sent.

If `/dashboard/1` still answers 200, the Next process is not seeing both halves. Check that
`SUNSET_MODE` is one of the accepted spellings in the environment of the running process, and that
it is in cloud mode: `DEPLOYMENT_MODE=cloud` at runtime, or a build made with
`NEXT_PUBLIC_DEPLOYMENT_MODE=cloud` when the runtime variable is unset.

**Stop condition:** `/sunset` redirects to itself, or `/license` redirects. Unset and restart.

**Reverse:** remove the line, restart the Next process.

---

## Stage 4 — The other two flags

```bash
# surfsense_backend/.env
AUTO_RELOAD_ENABLED=FALSE     # stop charging saved cards for a service winding down
LICENSE_TRIAL_ENABLED=TRUE    # the trial route is dark until launch
```

Restart the API process.

**Checks**

```bash
curl -s -o /dev/null -w '%{http_code}\n' -X POST -H 'content-type: application/json' \
  -d '{"email":"you@example.com"}' $API/api/v1/license/trial    # not 404
```

A 404 means the trial route is still dark.

---

## Stage 5 — Stop what nothing needs

Only two services. Most of the stack is still serving the business you are keeping, so resist the
instinct to turn more off:

| Service | T-0 | Why |
|---|---|---|
| `db`, `redis`, `backend`, `frontend`, `proxy` | **stays** | licence routes, scraper API, export, the portal |
| `searxng` | **stays** | the Google Search scraper falls back to it |
| `celery_worker`, `celery_beat` | **stays** | beat runs `reconcile_pending_stripe_credit_purchases`; licences are still being bought |
| `zero-cache` | **stop** | only the app UI syncs through it |
| `opensandbox-server` | **stop** | artifacts and code execution go with the app |

Stop the `zero-cache` and `opensandbox-server` services however your deployment does it. On the
compose stack that is:

```bash
docker compose stop zero-cache opensandbox-server
```

**Order matters:** stop `zero-cache` *after* stage 3, never before. With the web flag on, app routes
redirect to `/sunset` and nothing reaches Zero. Reversed, users meet an app that cannot sync.

**Checks**

```bash
curl -s -o /dev/null -w '%{http_code}\n' $API/api/v1/export   # 401, still serving
curl -s $API/health                                           # still ok
curl -s -o /dev/null -w '%{http_code}\n' $WEB/sunset          # 200
```

**Reverse:** start both services again.

---

## Stage 6 — Announce

Publish 2.0.0 with **"Set as the latest release" unchecked** — the pin stays on the legacy release,
and that pin is what keeps 0.0.39 clients off the new app.

Send the launch email through the broadcast tool, not the app. Turn on the in-app banner.

This is the first stage that cannot be reversed: you can unset a flag, you cannot unsend 19,000
emails. Everything above should be green before you start it.

---

## The first hour

Watch for, in this order of likelihood:

1. **410s on something users need.** Grep the access log for 410 and check nothing unexpected is in
   it. The allowlist covers `/auth/*` except register, `/api/v1/license/*`, and the Stripe webhook.
2. **Export failures.** Large accounts export synchronously; a timeout looks like a hang.
3. **Stripe webhooks failing.** A licence purchase that 410s would be a miswired allowlist.
4. **Support saying "the app just errors"** — stage 2's fail-open clients. Tell them to restart.

## Reversing the whole thing

Unset `SUNSET_MODE` in both files, restart the API and Next processes, start `zero-cache` and
`opensandbox-server` again. `/health` returns to `sunset: false` and the app comes back. Stage 6 is the
exception — an announcement cannot be withdrawn, only followed by another one.
