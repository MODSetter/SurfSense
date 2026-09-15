# Keygen CE — self-hosted licensing

Standalone stack for the licensing server that issues SurfSense license files.
See the Licensing decision log in
[`plans/community-local/00d-pivot-plan.md`](../../plans/community-local/00d-pivot-plan.md)
for why this is self-hosted rather than Keygen Cloud.

This directory is for **standing it up and proving it works**. It brings its own
Postgres and Redis so you do not need the main stack running. Production runs
one `keygen` service against the existing `db` and `redis` in
[`docker-compose.yml`](../docker-compose.yml) — see [Production shape](#production-shape).

## Run it

```bash
cp .env.example .env
# then fill in the five generated secrets, see the comments in .env.example
docker compose --profile setup run --rm setup    # ~30s, no TTY needed
docker compose up -d web worker
python check.py                                  # issues and verifies a real file
```

`check.py` walks the full production path — admin token, product, the three
policies, a license carrying the `{plan, email, checkoutSessionId}` metadata the
portal writes, a `ttl: null` check-out — and then verifies the resulting file
with contract 1's consumer algorithm, including that a tampered payload is
rejected. It exits non-zero on any failure.

Read the account public key (it is **not** exposed over the API):

```bash
docker compose exec -T web bundle exec rails runner "puts Account.sole.ed25519_public_key"
```

That 32-byte hex string is what gets compiled into
`surfsense_local/backend/modules/license/verify.py`, replacing the test key.
**Back up the account keypair out of band before that happens** — see the risk
note in the pivot plan. Tear down with `docker compose down -v`.

## Three traps

Each of these breaks the first boot or the first call. All were hit in the
15 Sep dry run.

1. **Setup needs four secrets, not one.** `SECRET_KEY_BASE` plus
   `ENCRYPTION_DETERMINISTIC_KEY`, `ENCRYPTION_PRIMARY_KEY` and
   `ENCRYPTION_KEY_DERIVATION_SALT`. Supply those plus `KEYGEN_ACCOUNT_ID`,
   `KEYGEN_ADMIN_EMAIL`, `KEYGEN_ADMIN_PASSWORD`, `KEYGEN_EDITION` and
   `KEYGEN_MODE` and `setup` runs non-interactively.

2. **`KEYGEN_HOST` must be a dotted name with a parseable eTLD+1.** A single
   label — `localhost`, or a bare compose service name like `keygen` — crashes
   boot in `resolve_account_service.rb` with
   `Regexp.escape: no implicit conversion of nil into String`. Use
   `keygen.internal`, or set `KEYGEN_DOMAIN` and `KEYGEN_SUBDOMAIN` explicitly.

3. **Keygen forces TLS** and answers plain HTTP with a `308` to `https://`. It
   does not terminate TLS itself, but Rails accepts `X-Forwarded-Proto: https`
   from RFC1918 peers, so an internal caller needs **that header, not a TLS
   terminator**. Without it every call silently redirects. `check.py` sets it;
   so must the backend's Keygen client.

## Production shape

Internal-only: nothing outside the compose network calls this. The backend's
license routes and the scraper API's `validate-key` are the only clients, so it
needs no Caddy route, no public DNS and no published port.

```yaml
keygen:
  image: keygen/api:latest
  command: web          # plus a second service with `command: worker`
  environment:
    KEYGEN_HOST: keygen.internal
    DATABASE_URL: postgres://...@db:5432/keygen   # its own database
    REDIS_URL: redis://redis:6379
    # ...the four secrets, KEYGEN_ACCOUNT_ID, KEYGEN_EDITION=CE
  depends_on: [db, redis]
```

Budget about 535 MiB for `web` plus `worker`. The backend reaches it at
`http://keygen.internal:3000/v1/accounts/$KEYGEN_ACCOUNT_ID` via
`KEYGEN_API_URL`.
