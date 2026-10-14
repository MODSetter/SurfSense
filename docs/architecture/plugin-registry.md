# Plugin registry

The registry is the list of third-party plugins, verified and community, the app offers once third-party plugins are allowed. Publishers add an entry by pull request to `plugins/registry/plugins.json`; CI checks it, a maintainer connects it on `dev` and reviews it, and CI signs the list on `dev`; the release pull request carries the signed list to `main`. A small container serves the signed list, its icons and SurfSense's OAuth files at `plugins.surfsense.com`, and the app fetches it, verifies the signature against keys it compiles in, and keeps the last good copy. What the app does with an entry, connecting and signing in, is in [plugins](plugins.md#third-party-plugins).

**Code:** [`plugins/registry/`](../../plugins/registry/), [`surfsense_local/backend/modules/plugins/lists/registry/`](../../surfsense_local/backend/modules/plugins/lists/registry/), [`.github/workflows/`](../../.github/workflows/) (`plugins-registry-*.yml`)
**Decisions:** [ADR 0053](../adr/0053-plugins-are-listed-in-a-registry-and-third-party-ones-start-off.md)

## The repository side

| Path | Holds |
|---|---|
| [`plugins.json`](../../plugins/registry/plugins.json) | The source list as authors write it: `schema_version`, `plugins` and `removed`. It lists DeepWiki |
| [`icons/`](../../plugins/registry/icons/) | One icon per entry that names one |
| [`published/`](../../plugins/registry/published/) | Written by the sign job only: `plugins.json`, stamped, and `plugins.json.sig`. Empty until the first signing |
| [`check/`](../../plugins/registry/check/) | A uv project: `python -m registry_check static`, `sign` or `verify` |
| [`oauth/`](../../plugins/registry/oauth/) | `client.json` and `callback.html`, SurfSense's OAuth client ([below](#oauth-files)) |
| [`Caddyfile`](../../plugins/registry/Caddyfile), [`Dockerfile`](../../plugins/registry/Dockerfile) | The registry container |

`.github/CODEOWNERS` names maintainers for `/plugins/registry/`, so no change merges without one. The publisher's guide is [`plugins/README.md`](../../plugins/README.md).

## The entry rules

`static` checks every entry offline and prints one line per problem, naming the entry and the field ([`entry_rules.py`](../../plugins/registry/check/registry_check/static/entry_rules.py), [`list_rules.py`](../../plugins/registry/check/registry_check/static/list_rules.py)):

- **Identity.** An `id` of lowercase letters, digits and hyphens, `kind: remote`, `verification` `verified` or `community`. The license belongs to the first-party list alone, and being in that list is what makes a plugin SurfSense's.
- **Verified.** A `verified` entry names the `domain` whose ownership was proven: a registered domain, never a bare shared suffix such as `vercel.app`, decided offline by the Public Suffix List the check ships with (`publicsuffixlist`). The URL's host is on it, and so is every other host unless the entry signs in with OAuth, whose sign-in hosts may be elsewhere.
- **Display.** `name` and `author` up to 80 characters, `description` up to 200. `author` is the company or project that runs the server, never a person's name; review checks it.
- **Server.** An `https` `url` with no credentials. `hosts` lists exact lowercase hostnames, none loopback, none twice, the URL's host among them.
- **Sign-in.** `auth.type` is `none`, `token` (with a `title` and `description` saying what to paste) or `oauth` (with an optional `client_id` and `scopes`). No `auth` field may carry a secret.
- **Access.** `free`, or `external` with an `access_note`.
- **Pages.** `privacy_policy` is required, and it and `homepage` are `https`. `min_app_version`, when given, is a version like `2.3.0`.
- **The plugin's page.** `about`, when given, is up to 600 characters; `tools`, when given, is a list of MCP tool names, each once; `added`, when given, is a month like `2026-10`. Review, not the check, makes sure every entry has an `about`, lists its tools and says the month it was added.
- **Ids.** Unique in the registry and across the first-party list, which the check reads too; an id in `removed` is never listed again, and each removed entry gives a `reason`. Unknown fields are allowed, so a newer app can add them.
- **Icons** ([`icon_rules.py`](../../plugins/registry/check/registry_check/static/icon_rules.py)). A plain file name in `icons/`, `.svg` or `.png`, at most 32 KB, square; a PNG at least 64×64; an SVG read with `defusedxml`, with no script, `foreignObject`, frame or embed, no event attribute and no reference outside itself. An icon no entry uses fails.

## Proving ownership

`verified` is set by a maintainer in review, once the publisher has proven it runs the server: the URL's host is on `domain`, `domain` belongs to `author`, and the publisher controls it, by one of a file at `https://{domain}/.well-known/surfsense-plugins.json` holding `{"plugins": ["<id>"]}`, a DNS TXT record `surfsense-plugin=<id>` on `domain`, or the same server URL in the [MCP Registry](https://modelcontextprotocol.io/registry/about) under that domain's namespace. The proof is checked again whenever a pull request changes the entry's URL, hosts or domain; the app never fetches it. Every other entry is `community`.

## Signing

`sign` reads the source list and writes `published/plugins.json` with `generated_at`, the UTC time with a `Z`, and each icon's `icon_sha256`, then `plugins.json.sig`: the bare base64 Ed25519 signature over that file's exact bytes ([`sign.py`](../../plugins/registry/check/registry_check/signing/sign.py)). One formatting, two-space JSON with a final newline, makes a re-sign of the same list byte-identical ([`signed_bytes.py`](../../plugins/registry/check/registry_check/signing/signed_bytes.py)). The key is the raw 32-byte private key in base64, read from `REGISTRY_SIGNING_KEY`; the source list is never rewritten. `verify` checks a list against a hex public key as the app does.

## CI

| Workflow | Runs | Does |
|---|---|---|
| [`plugins-registry.yml`](../../.github/workflows/plugins-registry.yml), on a pull request | Pull requests into `main` or `dev` that touch `plugins/registry/` or the first-party list | Fails a hand edit to `published/`, except from the bot or the release pull request from `dev` into `main`; runs the check's lint, format and tests, `static`, and the callback page's Node tests. A manual run checks any branch. A maintainer then connects the listing on `dev` and reviews its tools, since most servers need a key or a sign-in CI does not hold |
| [`plugins-registry.yml`](../../.github/workflows/plugins-registry.yml), on `dev` | Pushes to `dev` that change `plugins.json` or `icons/`, or a manual run on `dev` | Its sign job, the only one with write access to the code: runs `static`, signs with the `REGISTRY_SIGNING_KEY` secret, verifies with the public key the app compiles in, and commits `published/` to `dev` itself. Nothing pushes to `main`: the release pull request carries it there, and the registry container is built from `main` |

## The container

The registry is served by a container of its own beside the [plugin host](plugin-host.md), on the same hostname, so updating the list never restarts the plugins. It is pinned Caddy 2.11.4 serving files copied into the image, read-only, as an unprivileged user, with a health check ([`Caddyfile`](../../plugins/registry/Caddyfile)):

| Path | Serves | Cache |
|---|---|---|
| `/plugins.json`, `/plugins.json.sig` | The signed copies from `published/`; the source list is never served | 5 minutes |
| `/icons/<name>.svg` or `.png` | An icon, with a CSP that sandboxes it and runs nothing | 5 minutes |
| `/oauth/client.json` | SurfSense's client ID metadata document | 5 minutes |
| `/oauth/callback` | `callback.html`, never framed | none |
| `/health` | `ok` | none |

Any other path is `404`, and any method but `GET` or `HEAD` is `405`. `docker build -t surfsense-registry plugins/registry` builds it.

## OAuth files

SurfSense signs in to OAuth plugins as one public client ([plugins](plugins.md#signing-in-with-oauth)). [`client.json`](../../plugins/registry/oauth/client.json) is its client ID metadata document: `client_id` is its own URL, its one redirect is `https://plugins.surfsense.com/oauth/callback`, its grants `authorization_code` and `refresh_token`, and it authenticates with none.

[`callback.html`](../../plugins/registry/oauth/callback.html) forwards the browser to the app. The `state` the app sends is `<port>.<nonce>`; the page reads exactly one `state`, checks its shape and that the port is 1024 to 65535, and replaces the location with `http://127.0.0.1:<port>/plugins/oauth/callback` and the whole query, the provider's `error` included. Anything else shows "This sign-in link isn't valid". Its CSP allows only its own inline script and style, by hash, and it sends no referrer.

## In the app

[`current_registry.py`](../../surfsense_local/backend/modules/plugins/lists/registry/current_registry.py) holds the one answer to which list the app offers.

- **When it fetches.** Only through `GET /plugins/registry` or connecting from it, only while third-party plugins are allowed and `plugins.surfsense.com` is allowed, and at most every five minutes; a failed or refused fetch also waits five minutes. Readers that must not reach the network, readiness, a plugin's row, icons and custom ids, read the copy held ([`delisted.py`](../../surfsense_local/backend/modules/plugins/lists/registry/delisted.py), [`listed_ids.py`](../../surfsense_local/backend/modules/plugins/lists/registry/listed_ids.py)).
- **Consent.** `host:plugins.surfsense.com` is built in, off by default ([egress](egress.md)). A refusal carries `purpose: "plugin_registry"`, so the prompt asks about fetching the list ([`registry_consent.py`](../../surfsense_local/backend/modules/plugins/lists/registry/registry_consent.py)).
- **Verifying.** The list and its `.sig` are fetched from `plugins.surfsense.com` ([`registry_fetch.py`](../../surfsense_local/backend/modules/plugins/lists/registry/registry_fetch.py)) and kept only if the signature verifies with one of the public keys compiled into [`registry_keys.py`](../../surfsense_local/backend/modules/plugins/lists/registry/registry_keys.py), a tuple so a release can trust an old and a new key while CI's is rotated. A list with another `schema_version`, or a `generated_at` older than the copy held, is ignored and the copy kept, so an old list cannot bring back a removed plugin.
- **Entries dropped** ([`registry_document.py`](../../surfsense_local/backend/modules/plugins/lists/registry/registry_document.py), [`offered_entry.py`](../../surfsense_local/backend/modules/plugins/lists/registry/offered_entry.py)): one that does not parse; one claiming SurfSense's license (`auth: license` or `access: license`), so no fetched file reaches the license key; one taking a first-party id; one whose `min_app_version` is above this build's, read from the package's metadata ([`app_version.py`](../../surfsense_local/backend/shared/app_version.py), copied into the frozen API by `bundling/api.spec`); one listed twice or also in `removed`. Each is logged and the rest are kept.
- **The cache.** `{data_dir}/plugin-registry/` holds the list, its signature and when it was fetched, written last so a copy cut short reads as none ([`registry_cache.py`](../../surfsense_local/backend/modules/plugins/lists/registry/registry_cache.py)). Offline the copy is listed with its date; with no verified copy, listing is `502 registry_unavailable`.
- **Icons.** After a new list, each icon is fetched into the cache's `icons/` and kept only if its SHA-256 matches the entry's `icon_sha256` ([`registry_icons.py`](../../surfsense_local/backend/modules/plugins/lists/registry/registry_icons.py)). `GET /plugins/registry/icons/{id}` serves only a matching copy, never fetching, with a CSP that sandboxes it; anything else is `404` and the screen shows the name's first letter.
- **Development.** An unfrozen API reads the checkout's `plugins/registry/plugins.json` and icons, unsigned and with no consent ([`registry_origin.py`](../../surfsense_local/backend/modules/plugins/lists/registry/registry_origin.py)). `SURFSENSE_LOCAL_PLUGIN_HOST_URL` moves entries on `plugins.surfsense.com` to the local plugin host, as it does the first-party list ([`served_entry.py`](../../surfsense_local/backend/modules/plugins/lists/registry/served_entry.py)).

## Tests

- **Check:** from `plugins/registry/check`, `uv run pytest`. [`tests/`](../../plugins/registry/check/tests/) hold each entry rule and icon rule, unique ids across both lists, removed entries, and signing: a list verifies, one changed byte or another key fails, the stamps, stable formatting, and the source never rewritten. The sign job alone also checks the committed list against the production key. [`oauth/tests/callback.test.mjs`](../../plugins/registry/oauth/tests/callback.test.mjs) runs the callback page: a valid state forwarded, a provider's error forwarded, each malformed state going nowhere, and a CSP that loads nothing.
- **App:** [`test_registry.py`](../../surfsense_local/backend/tests/integration/plugins/routes/test_registry.py) runs the routes against a stand-in plugin host signing with a test key ([`tests/registry_stand_in.py`](../../surfsense_local/backend/tests/registry_stand_in.py)): nothing fetched while third-party plugins are off, the five-minute refresh, a bad signature, an older list and an unknown schema each ignored, the cached copy offline, no copy, entries only the first-party list may hold dropped, the host's consent, icons, the checkout read unsigned, connecting, removed plugins, and custom ids. [`test_registry_compiled.py`](../../surfsense_local/backend/tests/unit/plugins/lists/test_registry_compiled.py) checks the production key is compiled in and the host is built in.

## Known gaps

- Nothing builds or deploys the registry image, so `plugins.surfsense.com` serves no list, and a packaged app's fetch fails.
- A delisting reaches the app only when Settings → Plugins lists the registry; nothing fetches it before an agent turn.
- `min_app_version` has not been tried in a frozen build; only a test that `bundling/api.spec` copies the package's metadata guards it.
