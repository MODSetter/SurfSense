# SurfSense website

The site at `www.surfsense.com`: the homepage, docs, blog, changelog, announcements, pricing, the license pages, and the routes the desktop app calls, `/api/updates` (behind `updates.surfsense.com`) and `/api/usage` (behind `usage.surfsense.com`). Next.js App Router, deployed on Vercel from this folder.

The desktop UI lives in [`surfsense_local/frontend/`](../surfsense_local/frontend/). The hosted web app and the self-hosted stack are on the [`legacy` branch](https://github.com/MODSetter/SurfSense/tree/legacy).

## You need

- Node.js 24 and [pnpm](https://pnpm.io/installation)

## Run it

```bash
cp .env.example .env
pnpm install
pnpm dev
```

Site: http://localhost:3000

The license pages call the license portal in [`backend/`](../backend/) at `NEXT_PUBLIC_FASTAPI_BACKEND_URL`. Every other page runs without it.

## Tests

```bash
pnpm test:unit
pnpm format
```
