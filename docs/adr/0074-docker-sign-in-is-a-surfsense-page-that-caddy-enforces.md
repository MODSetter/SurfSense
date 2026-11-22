# ADR 0074: The Docker image's sign-in is a SurfSense page, issued by the headless entry and enforced by Caddy's `forward_auth`

- **Status:** Accepted
- **Date:** 2026-10-28
- **Source:** the Docker proposal, now [Docker, Caddy and access](../architecture/docker.md#caddy-and-access)

## Context

Step 10 of the Docker proposal opened an instance beyond `localhost` behind Caddy's `basic_auth`, so that no authentication would be application code. That leaves the browser's own dialog as the only sign-in: no page, no sign-out, a poor fit for phones and password managers, and a password that exists only in `.env`. The image is for servers reached from other devices, where those limits are what users meet first.

Caddy itself offers two ways to put a page in front of an app: `forward_auth`, which asks a service whether each request may continue, and the third-party `caddy-security` plugin, which needs a custom Caddy build.

## Decision

- **Caddy stays the one door.** Every request goes through `forward_auth` to an access service on loopback, except the app's static files, which carry no data, `/api/health`, which the healthcheck reads, and the service's own `/access/*` routes.
- **A sign-in's callback needs no session,** `/callback` for ChatGPT and `/plugins/oauth/callback` for plugins. The browser can return on another name than its cookie's, as on `127.0.0.1` after signing in on `localhost`, and each is guarded by its own `state` and PKCE, as RFC 9700 has an OAuth redirect endpoint guarded; the host checks still apply.
- **The access service lives in `headless/access/`,** the Docker entry, in Node. The desktop never runs it, and the shared backend and frontend core do not depend on it.
- **One password per instance, always,** hashed with scrypt and a random salt on `/data`. It is created the first time the app is opened, as Open WebUI and Immich create their first account, or set at start by `SURFSENSE_PASSWORD`, which also replaces a forgotten one. A password from `SURFSENSE_PASSWORD` is the setup's: the app shows it locked and refuses to change it, since the next start would set it back; without the variable it becomes the app's.
- **Whoever opens a new instance first creates its password,** as Immich and Open WebUI have their first account. Anything reachable from the internet should preset `SURFSENSE_PASSWORD`, so no one else gets there first.
- **`SURFSENSE_AUTH=none` turns sign-in off,** for a server whose own proxy or VPN signs people in, as Open WebUI's `WEBUI_AUTH=False` does. It is a line in the server's setup, never a setting in the app, and the log warns at every start.
- **Sessions are signed cookies**, HMAC-SHA256 under a key derived from the instance's secret, and are `HttpOnly`, `SameSite=Strict`, `Secure` over HTTPS, and kept 30 days. Changing the password ends every session. Strict holds because nothing reached from another site needs it: a sign-in's callback needs no session, and the app's own requests are same-site.
- **Guessing is slowed:** five failed sign-ins from one client within a minute, then `429` with `Retry-After`. Sign-in and sign-out also refuse a cross-site `Origin`.
- **`SURFSENSE_ALLOWED_HOSTS` refuses any other name, with sign-in on or off,** which stops a page rebinding its own name to this address.
- Rejected: no password meaning this machine only, which on a server locks out every device the user owns; no password meaning open to named addresses, with a one-time setup code from the log for a public domain, which no comparable app asks of its users; a Portainer-style window, the first password open to other devices only for minutes after a start, which made a server left running need a restart for little gain; removing the password from the app, since sign-in is always on; `basic_auth`, for the limits above; `caddy-security`, a custom Caddy build and a third-party security plugin on every release, with its own page; Authelia and its kind, a second service in a one-container image; sign-in in the Python API, which would put code only Docker uses into the core the desktop shares.

## Consequences

- SurfSense owns a small authentication module, `headless/access/`, tested with Node's runner in Docker Tests, and the image tests cover a refused request, a slowed guess, sign-in and sign-out.
- The frontend gains a setup screen, a sign-in screen and a Settings section to change the password, all shown only in the Docker build and tested with the `docker` tag.
- A Docker Desktop user alone on their PC creates a password on first visit too.
- Every case, from a home PC to a public domain, is in [Docker access](../architecture/docker-access.md).
- The healthcheck and the image tests read `/api/health` without a session; of the API's routes, nothing else does.

## Where the code stands

Built ([Docker](../architecture/docker.md), [Docker access](../architecture/docker-access.md)): [`headless/access/`](../../surfsense_local/headless/access/), `forward_auth` in [`routes.caddy`](../../docker/surfsense/caddy/routes.caddy), and the frontend's [`features/access/`](../../surfsense_local/frontend/src/features/access/).
