# Docker access

Who can open the Docker image's SurfSense, and how. Every instance asks for one password, created the first time it is opened. The server's setup can turn sign-in off, and then anyone who can reach SurfSense can use it. None of this exists on the desktop: Electron never runs the access service, and the frontend shows its screens only in the Docker build (`IN_CONTAINER`).

**Code:** [`headless/access/`](../../surfsense_local/headless/access/), [`headless/sign-in-mode.ts`](../../surfsense_local/headless/sign-in-mode.ts), [`headless/main.ts`](../../surfsense_local/headless/main.ts), [`frontend/src/features/access/`](../../surfsense_local/frontend/src/features/access/), `forward_auth` in [`routes.caddy`](../../docker/surfsense/caddy/routes.caddy)
**Decisions:** [ADR 0074](../adr/0074-docker-sign-in-is-a-surfsense-page-that-caddy-enforces.md)
**Also:** [Docker](docker.md), the container this guards

## The rules

- **Caddy asks the access service about every request** (`forward_auth`), which answers 200, 401 (sign in or set up) or 403 (refused).
- **`/api/internal/*` is refused to every browser,** signed in or not and with sign-in off: the workers reach it on loopback only.
- **A name not in `SURFSENSE_ALLOWED_HOSTS` is refused,** when the list is set, whether or not sign-in is on: a page rebinding its own name to this address never names one of ours. Empty, any name passes this check.
- **Without a session, only the app's files, `/api/health`, `/access/*` and the sign-in callbacks pass.** The app's files load, carry no data, and show the setup or the sign-in. The callbacks are guarded by their own `state` and PKCE.
- **No password yet is the same as signed out:** the API answers 401, and the app shows its setup.
- **`SURFSENSE_AUTH=none` turns all of that off:** every allowed name gets everything, and the log warns at every start. Who can reach it is then up to `SURFSENSE_BIND`, `SURFSENSE_ALLOWED_HOSTS` and anything in front: this machine alone, a VPN, or a proxy with its own login. Any other value stops the container at start, saying why.

## Where the password lives

`/data/access.json` on the data volume, mode 600, written whole then renamed ([`password-store.ts`](../../surfsense_local/headless/access/password-store.ts)):

```json
{ "salt": "…", "hash": "…", "version": 4, "source": "app" }
```

- `hash`: scrypt (N=2^17, r=8, p=1) of the password with a random 16-byte salt. The password itself is never stored.
- `version`: bumped on every change; each session cookie carries it, so a change signs every other device out.
- `source`: who owns it. `app` was created or changed in SurfSense; `setup` was set by `SURFSENSE_PASSWORD`, and only the server's setup may change it. A record from before owners were kept reads as `app`.

## Who owns the password

| Set by | Settings › Access | `POST /access/password` to change it |
|---|---|---|
| The app (setup page, or a change in Settings) | change form: current and new password | 204 with the right current password |
| The server's setup, `SURFSENSE_PASSWORD` | a locked note: "This password is set where SurfSense is installed. To change it, update SurfSense's setup on that computer, then restart it." | 409 |

At every start, [`main.ts`](../../surfsense_local/headless/main.ts) sets `SURFSENSE_PASSWORD`, when given, as `setup`, and deletes it from the environment so no sidecar sees it. Without it, a `setup` password stays and becomes `app` ([`handOverToApp`](../../surfsense_local/headless/access/password-store.ts)): removing the variable never exposes the instance nor locks anyone out. The interface never names the variable.

## The first password

Whoever opens a new SurfSense first creates its password, from any browser, as Immich and Open WebUI have their first account. While no password exists, the log says to open SurfSense and create one. Compose publishes on every network the server is on (`SURFSENSE_BIND=0.0.0.0`), so phones and laptops reach a fresh install at once. A server reachable from the internet, such as a VPS, should preset `SURFSENSE_PASSWORD` before the first start: Docker's published ports pass the server's firewall, `ufw` included, so whoever reaches it first would set it.

## The cases

**1. A server at home, nothing set.**
```
server: docker compose up -d
start ──► log: "No password yet. Open SurfSense in a browser to create one…"
phone  ──► http://192.168.1.20:4929 ──► Set up SurfSense ──► password ──► the app
laptop ──► http://192.168.1.20:4929 ──► sign-in ──► the app (30 days per browser)
```
Plain HTTP: the password crosses the network unencrypted, and browsers allow the microphone only over HTTPS. Case 2 adds it.

**2. A server at home, over HTTPS.**
```
.env: SURFSENSE_ALLOWED_HOSTS=surfsense.lan  SURFSENSE_TLS=internal
laptop ──► https://surfsense.lan:4943 ──► Set up SurfSense, or sign in ──► the app
```
Each device trusts Caddy's root certificate once.

**3. Your own PC only.**
```
.env: SURFSENSE_BIND=127.0.0.1
http://localhost:4929 ──► Set up SurfSense ──► the app; no other device can connect
```

**4. From work or anywhere, through a VPN.**
```
.env: SURFSENSE_ALLOWED_HOSTS=surfsense.tail1234.ts.net
work laptop on the VPN ──► sign-in ──► the app
```

**5. A public domain.**
```
.env: SURFSENSE_DOMAIN=surfsense.example.com  SURFSENSE_PASSWORD=…   (preset: recommended)
any browser ──► https://surfsense.example.com ──► sign-in ──► the app
Settings › Access: the locked note
```
Without a preset password, whoever opens the domain first sets the password, which is why it is preset.

**6. Sign-in turned off.**
```
.env: SURFSENSE_AUTH=none  SURFSENSE_ALLOWED_HOSTS=surfsense.lan
start ──► log: "Sign-in is off (SURFSENSE_AUTH=none): anyone who reaches SurfSense can use it…"
any browser that reaches it ──► SurfSense opens, no setup, no sign-in
Settings › Access: "Sign-in is turned off where SurfSense is installed. Anyone who can reach it can use it."
```
Safe where something else decides who reaches it: this machine alone (`SURFSENSE_BIND=127.0.0.1`, since the default publishes on every network), a VPN such as Tailscale, or a proxy with its own login such as Cloudflare Access or Authelia. Published straight to a network or the internet, anyone there gets the documents, chats, plugins and API keys.

**7. Changing a password the app owns.**
```
Settings › Access ──► current + new password ──► version +1
──► every other device signed out; this browser stays signed in
```

**8. Moving the password from the setup to the app.**
```
remove SURFSENSE_PASSWORD ──► restart ──► the password stays, source: app
──► Settings › Access can change it
```

**9. A forgotten password.**
```
set SURFSENSE_PASSWORD=<new> ──► restart ──► sign in with it (source: setup)
```

**10. A page you visit tries DNS rebinding.**
```
evil.example ──► your browser ──► SurfSense's address, Host: evil.example
──► not a name you allowed ──► 403, with sign-in on or off
```
With `SURFSENSE_ALLOWED_HOSTS` empty, the password is what stands in its way.

**11. Someone guesses passwords.**
```
five wrong tries from one client within a minute ──► 429 with Retry-After
```

## Routes

| Route | Does |
|---|---|
| `GET /verify` | Caddy's `forward_auth` question: 200, 401 or 403 |
| `GET /access/state` | `password`, `signedIn`, `host`, `source` (`app`, `setup` or null), `signInOff` |
| `POST /access/password` | `{password}` creates the first one; `{current, password}` changes it; 409 when the setup owns it; 422 under 8 characters |
| `POST /access/sign-in`, `/access/sign-out` | sets or clears the session cookie; both refuse a cross-site `Origin` |

## The screens

[`access-gate.tsx`](../../surfsense_local/frontend/src/features/access/access-gate.tsx) reads the state before the app: sign-in off or signed in opens the app; a password shows the sign-in; no password shows Set up SurfSense. Each password field is typed once, with an eye that shows it ([`password-field.tsx`](../../surfsense_local/frontend/src/features/access/password-field.tsx)), and asks the browser to generate and save a new one (`autocomplete="new-password"`). Settings › Access shows the change form, the locked note, or the sign-in-off note, with Sign out unless sign-in is off.

## Tests

- [`access.test.ts`](../../surfsense_local/headless/access/access.test.ts): the rules, the first password, ownership and the handover, sign-in off, rebinding, guessing, sessions.
- [`main.test.ts`](../../surfsense_local/headless/main.test.ts): `SURFSENSE_PASSWORD` as `setup`, the log while no password exists, `SURFSENSE_AUTH`.
- [`image.test.ts`](../../surfsense_local/headless/image.test.ts): through Caddy, a fresh image asks to be set up; one with `SURFSENSE_PASSWORD` signs in, refuses another host and refuses a change from the app.
- `access-gate.test.tsx`, `access-settings.test.tsx`: each screen, tagged `docker`.

## Known gaps

- A new instance reachable by others before its password exists can be set up by them first; `SURFSENSE_PASSWORD` is the guard, and nothing else is.
- `SURFSENSE_AUTH=none` with `SURFSENSE_ALLOWED_HOSTS` empty answers any name, so a rebinding page reaches an instance with no sign-in; the docs say to name the hosts.
