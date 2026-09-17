# SurfSense web

Next.js UI for the self-host stack (App Router, `pnpm`).

This is not the desktop UI. Desktop frontend lives in [`surfsense_local/frontend/`](../surfsense_local/frontend/).

## You need

- Node.js 20+ and [pnpm](https://pnpm.io/installation) (not npm)
- The API in [`surfsense_backend/`](../surfsense_backend/README.md) on http://localhost:8000

## Run it

```bash
cp .env.example .env
```

In `.env`, point at a backend on your machine (the example file uses Docker hostnames):

```bash
NEXT_PUBLIC_FASTAPI_BACKEND_URL=http://localhost:8000
SURFSENSE_BACKEND_INTERNAL_URL=http://localhost:8000
AUTH_TYPE=LOCAL
ETL_SERVICE=DOCLING
DEPLOYMENT_MODE=self-hosted
```

Then:

```bash
pnpm install
pnpm dev
```

App: http://localhost:3000

Match `AUTH_TYPE` with the backend. Leave `SUNSET_MODE` unset.

Live document/chat updates need [zero-cache](content/docs/manual-installation.mdx). Most UI PRs can run without it; the page just will not refresh itself.

## Tests

```bash
pnpm test:unit
pnpm format
```

Playwright needs Postgres, Redis, the API, and a worker. See [tests/README.md](tests/README.md).
