# Hosted sunset

The hosted service went export-only on 18 Sep 2026 (T-0), and its user data is purged once the export window closes on 18 Oct 2026 (T+30). Every sunset behaviour sits behind flags read at runtime, because the same `surfsense_backend` and `surfsense_web` code is also the self-host stack, the scraper API and the license portal: with the flags unset nothing changes, and on the backend the flag takes effect only on a `DEPLOYMENT_MODE=cloud` deployment. Writes are refused and app routes redirect to `/sunset`, while reads, sign-in, export, the license business, PATs and the scraper API keep working.

**Code:** [`surfsense_backend/app/sunset.py`](../../surfsense_backend/app/sunset.py), [`surfsense_web/proxy.ts`](../../surfsense_web/proxy.ts), [`surfsense_web/lib/sunset.ts`](../../surfsense_web/lib/sunset.ts), [`surfsense_backend/scripts/purge_hosted_accounts.py`](../../surfsense_backend/scripts/purge_hosted_accounts.py)
**Decisions:** [ADR 0023](../adr/0023-sunset-behind-flags.md)

The operational steps are in the [sunset runbook](../../plans/community-local/sunset-runbook.md) for T-0 and the [purge runbook](../../plans/community-local/purge-runbook.md) for T+30.

## The flag

`is_sunset_mode()` reads `SUNSET_MODE` from the environment on every call, so throwing it takes a restart, never a rebuild or a deploy. It accepts `1`, `true`, `yes` and `on` in any case, because the switch is thrown once under time pressure, and a spelling that silently read as false would leave the service running with nothing to show it had failed. It returns false unless `DEPLOYMENT_MODE=cloud` ([PR #1815](https://github.com/MODSetter/SurfSense/pull/1815)), so a stray `SUNSET_MODE=1` copied into a self-hosted `.env` is a no-op rather than an outage. Production sets `DEPLOYMENT_MODE=cloud`.

The web app reads its own `SUNSET_MODE`, with the same spellings, in `proxy.ts` on every request. It is deliberately not `NEXT_PUBLIC_SUNSET_MODE`: `NEXT_PUBLIC_*` values are inlined at build time, and nothing reads that name. So one variable is set in two places, the backend's `.env` and the web app's, and setting only one gives a half-sunset: a backend refusing writes behind an app that still looks open, or the reverse.

## Refusing writes

`SunsetWriteBlockMiddleware` answers `410 Gone` to `POST`, `PUT`, `PATCH` and `DELETE` while the flag is on, except on an allowlist:

| Allowed | Why |
|---|---|
| `/auth/*`, except `/auth/register` | export needs a session, and the legacy desktop signs in through `/auth/desktop/*`; nobody new needs to sign up |
| `/api/v1/license/*` | the license portal keeps selling |
| `/api/v1/stripe/webhook` | license fulfilment and refunds |
| `/api/v1/pats*` | PATs keep working until the T+30 purge, for MCP clients among others |
| `/api/v1/workspaces/<id>/scrapers/` | the scraper API outlives the wind-down |

Reads are never refused. That is why the middleware checks the method rather than listing every route that mutates something: export is a `GET`. The refusal's body is `{"detail": "SurfSense is export-only while the hosted service winds down. Your data is still available to export."}`.

## Telling clients

`GET /health` in `app/app.py` returns `status`, `sunset`, which is `is_sunset_mode()`, and `sunset_url`, from `SUNSET_URL` with a default of `https://surfsense.com/sunset`. It needs no credentials and is exempt from rate limiting, because the legacy desktop v0.0.40 asks it once at startup, with a 3-second timeout and no retry, and reads any failure as "not sunset" ([contract 4](../contracts/04-sunset-flag.md)). When `sunset` is true, v0.0.40 loads the live `/sunset` page in place of its bundled frontend.

On the web, `proxy.ts` sends every non-public route to `/sunset` with a 307. The public routes in `lib/public-routes.ts` include `/`, `/sunset`, `/license`, `/pricing`, `/downloads`, `/login` and the marketing pages, so the portal everyone is being sent to stays reachable. `ZeroProvider` needs no change: a redirected route never renders, and on a public route it already passes its children through without connecting.

## Export

`GET /api/v1/export` (`app/routes/export_routes.py`, `app/services/export_service.py`) builds the whole account, every workspace the user can access, into the contract-3 bundle inside the request: a temporary ZIP with `manifest.json` as its first entry, streamed back and then deleted. An `X-Skipped-Documents` header counts the documents it could not include. The Export account button on `/sunset` calls it with the user's session and says what does not travel: original uploads, generated artifacts, tool calls, agent steps and live citation links ([contract 3](../contracts/03-export-bundle.md), [import](import.md)).

## Purge

`scripts/purge_hosted_accounts.py` carries out the deletion at T+30. It loops `erase_account()`, the function self-service deletion (`DELETE /users/me`) already runs for one account, rather than issuing a bulk `DELETE`, because a cascade drops the rows but leaves blobs and knowledge stores on disk. PATs have an `ON DELETE CASCADE` foreign key to the user, so they go with it.

- It is a dry run by default: it counts the accounts, or lists them with `--verbose`, and changes nothing without `--execute`.
- `--execute` asks for the typed phrase `erase every hosted account`; `--yes` skips it on a re-run.
- It refuses to run unless `is_sunset_mode()` is true, so it cannot be pointed at a live service by mistake.
- `erase_account()` is idempotent and failures are recorded rather than raised, so an interrupted or partly failed run is finished by running it again.

## Known gaps

- The web redirect is not gated on `DEPLOYMENT_MODE`: a self-hosted web app with `SUNSET_MODE` set redirects to `/sunset`.
- The 410 body carries no `sunset_url`.
- The purge selects every user, so once license mode creates synthetic license users it would erase them too.
- The purge script has no test.
- Celery beat keeps scheduling its periodic tasks, connector indexing checks and automation triggers among them, and none checks `is_sunset_mode()`; the middleware covers HTTP only.
- The synchronous export has no size warning and no timeout.
- The web app's unit tests, `tests/unit/sunset-redirect.test.ts` among them, are not run in CI.
- The runbooks do not mention `DEPLOYMENT_MODE`, which the flag and therefore the purge script both depend on.
- `/sunset` has the export button, download links and import steps, but not the deletion date (18 Oct 2026), the refund-or-discount offer or the change for MCP users, which the launch plan put on it.
