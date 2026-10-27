# ADR 0074: The Docker image's sign-in is a SurfSense page, issued by the headless entry and enforced by Caddy's `forward_auth`

- **Status:** Accepted
- **Date:** 2026-10-28
- **Source:** [Docker proposal, Caddy and access](../proposals/docker/README.md#caddy-and-access)

## Context

Step 10 of the Docker proposal opened an instance beyond `localhost` behind Caddy's `basic_auth`, so that no authentication would be application code. That leaves the browser's own dialog as the only sign-in: no page, no sign-out, a poor fit for phones and password managers, and a password that exists only in `.env`. The image is for servers reached from other devices, where those limits are what users meet first.

Caddy itself offers two ways to put a page in front of an app: `forward_auth`, which asks a service whether each request may continue, and the third-party `caddy-security` plugin, which needs a custom Caddy build.

## Decision

- **Caddy stays the one door.** Every request goes through `forward_auth` to an access service on loopback, except the app's static files, which carry no data, `/api/health`, which the healthcheck reads, and the service's own `/access/*` routes.
- **A sign-in's callback needs no session,** `/callback` for ChatGPT and `/plugins/oauth/callback` for plugins. The browser can return on another name than its cookie's, as on `127.0.0.1` after signing in on `localhost`, and each is guarded by its own `state` and PKCE, as RFC 9700 has an OAuth redirect endpoint guarded; the host checks still apply.
- **The access service lives in `headless/access/`,** the Docker entry, in Node. The desktop never runs it, and the shared backend and frontend core do not depend on it.
- **One password per instance,** hashed with scrypt and a random salt on `/data`. It is created in the app, from the host itself, or set at start by `SURFSENSE_PASSWORD`, which also replaces a forgotten one.
- **Sessions are signed cookies**, HMAC-SHA256 under a key derived from the instance's secret, and are `HttpOnly`, `SameSite=Strict`, `Secure` over HTTPS, and kept 30 days. Changing the password ends every session. Strict holds because nothing reached from another site needs it: a sign-in's callback needs no session, and the app's own requests are same-site.
- **Guessing is slowed:** five failed sign-ins from one client within a minute, then `429` with `Retry-After`. Sign-in and sign-out also refuse a cross-site `Origin`.
- **Without a password, nothing changes:** only the host's own requests are answered, by `Host` and by the client address Caddy sees, and no sign-in is asked for, as on the desktop.
- Rejected: `basic_auth`, for the limits above; `caddy-security`, a custom Caddy build and a third-party security plugin on every release, with its own page; Authelia and its kind, a second service in a one-container image; sign-in in the Python API, which would put code only Docker uses into the core the desktop shares.

## Consequences

- SurfSense owns a small authentication module, `headless/access/`, tested with Node's runner in Docker Tests, and the image tests cover a refused request, a slowed guess, sign-in and sign-out.
- The frontend gains a sign-in screen and a Settings section to create or change the password, both shown only in the Docker build and tested with the `docker` tag.
- The healthcheck and the image tests read `/api/health` without a session; of the API's routes, nothing else does.

## Where the code stands

Built, as step 10 of the [Docker proposal](../proposals/docker/README.md#steps): [`headless/access/`](../../surfsense_local/headless/access/), `forward_auth` in [`routes.caddy`](../../docker/surfsense/caddy/routes.caddy), and the frontend's [`features/access/`](../../surfsense_local/frontend/src/features/access/).
