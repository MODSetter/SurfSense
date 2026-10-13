# Plugin lists

> Owns: the first-party list (`surfsense_local/backend/modules/plugins/lists/first_party/`), the registry (`plugins/registry/`: `plugins.json`, the entry schema both lists follow, its check, the signing job, later the bundle scanner), the app's cached copy of the registry and its refresh (`modules/plugins/lists/registry/`), the `CODEOWNERS` line for `plugins/registry/`.
> Decision: [ADR 0053](../../../adr/0053-plugins-are-listed-in-a-registry-and-third-party-ones-start-off.md).

## Two lists

The app knows plugins from two lists that share one entry schema. Only custom plugins added by URL live outside them, in the user's app.

| | The first-party list | The registry |
|---|---|---|
| Lists | First-party plugins: SurfSense's | Third-party plugins, verified and community ones, plus removed ones |
| Lives in | `surfsense_local/backend/modules/plugins/lists/first_party/plugins.json` | `plugins/registry/plugins.json` |
| Reaches the app | Packaged into the API binary, as the model catalogs are | Fetched, signed, from `plugins.surfsense.com` once the user allows third-party plugins, then cached |
| Changes with | An app release | A merged pull request, with no app update |
| Shown | Always, with no network and no consent | Once the user allows third-party plugins |

- **Lists point at plugins and never hold them.** A plugin's code, and later its bundle files, stay with its publisher. A first-party entry is a few hundred bytes, so the app does not grow with plugins, and a third-party plugin never changes the app.
- **The first-party list changes only when SurfSense adds or retires a plugin.** What changes more often, a server's tools or a bundle's versions, is read from where the plugin is hosted.
- **Only the first-party list speaks for SurfSense.** Being in it is what makes a plugin SurfSense's: its entries carry no `verification`, and `auth: license` and `access: license` appear in it alone. The registry check refuses them, and the app drops them from a fetched registry, so no fetched file can claim to be SurfSense or receive the license key ([`05-paid.md`](05-paid.md)).

An illustrative registry entry, not a real listing:

```json
{
  "schema_version": 1,
  "plugins": [
    {
      "id": "notion",
      "kind": "remote",
      "verification": "verified",
      "domain": "notion.com",
      "name": "Notion",
      "description": "Search and read your Notion pages and databases.",
      "about": "Find pages and databases across your workspace, read them whole, and answer from them. Notion signs you in; SurfSense keeps only the sign-in.",
      "tools": ["search", "fetch"],
      "added": "2026-10",
      "author": "Notion Labs",
      "url": "https://mcp.notion.com/mcp",
      "auth": { "type": "oauth" },
      "hosts": ["mcp.notion.com"],
      "access": "external",
      "access_note": "Requires a Notion account.",
      "privacy_policy": "https://www.notion.so/privacy",
      "homepage": "https://www.notion.so",
      "icon": "notion.svg",
      "min_app_version": "2.3.0"
    }
  ],
  "removed": [
    { "id": "old-plugin", "reason": "The service shut down." }
  ]
}
```

| Field | Rule |
|---|---|
| `id` | `^[a-z][a-z0-9-]{0,63}$`, unique across both lists, never reused once listed |
| `kind` | `remote`. `bundle` is reserved ([below](#bundle-entries-later)) |
| `verification` | Registry only: `verified` or `community`, set by a maintainer ([below](#publishers)). A first-party entry has none: it is SurfSense's by its list |
| `domain` | `verified` only. The registered domain whose ownership was proven, never a shared hosting suffix such as `vercel.app` (the Public Suffix List decides). The URL's host is on it; for an `oauth` entry, its sign-in hosts may be elsewhere |
| `name`, `description`, `author` | Display text, 1–80, 1–200 and 1–80 characters. `author` is the company or project that runs the server, never a person's name: a solo developer lists their project |
| `url` | `remote` only. `https`, no credentials in it; the server's MCP endpoint |
| `auth` | `{ "type": "oauth" }`, `{ "type": "token", "title", "description" }`, `{ "type": "none" }`, or `{ "type": "license" }` in the first-party list only. `oauth` may carry `client_id`, SurfSense's app as registered with a provider that registers clients only in advance, and `scopes`; never a client secret |
| `hosts` | Every host the app contacts for this plugin: for a remote one, the URL's host and the authorization server's hosts. Exact hostnames, no loopback |
| `access` | `free` or `external`, or `license` in the first-party list only ([`05-paid.md`](05-paid.md)) |
| `access_note` | Required when `access` is `external`: what the user must buy or have, in a sentence |
| `privacy_policy` | Required in the registry |
| `about` | Required in both lists. What the plugin does, in more detail than `description`, in 1–600 characters: `description` is the line on its card in Browse, `about` the text on its public page. Neither is ever given to a model |
| `tools` | Required in both lists, at least one: a plugin's tools are all SurfSense uses of it. The names of the tools the server offers, each an MCP tool name, listed once. Shown on the plugin's public page; never given to a model ([below](#a-plugins-page)) |
| `added` | Required in both lists. The month the plugin joined its list, as `YYYY-MM`: set by the publisher in its pull request and checked in review, or by SurfSense with its own plugin. Shown on the plugin's public page |
| `homepage`, `icon` | Optional. Icons live beside their list: `plugins/registry/icons/`, or `lists/first_party/icons/` in the app |
| `min_app_version` | Registry only, optional. Older apps do not list the entry |

Unknown fields are ignored, so a newer field does not break an older app. `schema_version` rises only when the structure breaks.

## Adding a plugin

A company or a project:

1. Opens a pull request into `dev` adding one entry to the registry, and its icon. A submission site can replace the pull request later.
2. CI checks the entry against the rules above, and its icon. It does not contact the server: most need a key or a sign-in CI does not hold.
3. A maintainer reviews the entry once, after connecting the plugin on `dev` and signing in if it needs it: who runs the server, what its tools do and whether `tools` lists every one of them, whether their descriptions carry instructions aimed at the model, whether the hosts are complete, whether the privacy policy is real, and that `author` names the company or project that runs the server. `verified` needs proof of the domain, below.
4. Once merged and on `main`, the entry reaches every app that allows third-party plugins at its next refresh, without an app update ([below](#how-the-app-gets-the-registry)).

A later change to an entry is the same pull request and the same review. A change to a remote server needs none: the publisher deploys when they like, which is why tools added later start off ([below](#tools-added-later)).

SurfSense adds a plugin by adding its entry to the first-party list in the same change as the plugin itself ([`../remote/02-surfsense-servers.md`](../remote/02-surfsense-servers.md)). The same check runs on the first-party list.

`CODEOWNERS` requires a maintainer's approval for every change under `plugins/registry/`.

## Who can publish what

| Publisher's situation | What they do |
|---|---|
| Already runs an MCP server, as many products do | One registry entry pointing at it. Nothing else to build |
| Has an API but no MCP server | Builds a remote MCP server over its API, with any MCP SDK, and hosts it: then it works in SurfSense and every other MCP client. Later, a bundle is the alternative for a publisher that will not host anything ([`bundles/`](../bundles/README.md)) |
| Wants the agent to use its tools well | Adds skills to its entry once plugins carry them ([`06-later.md`](06-later.md)) |
| A project wrapping someone else's public API | Hosts the server themselves and is listed as `community` unless it proves its own domain, never as the API's owner. The entry and the screen say who runs the server, and its privacy policy is the developer's, since the user's requests and credentials pass through it |
| SurfSense | Its own remote plugins in `plugins/remote/` and `plugins/remote/proprietary/`, run on its plugin host ([`../remote/02-surfsense-servers.md`](../remote/02-surfsense-servers.md#surfsenses-own-servers)); later its bundles, in `plugins/bundles/` ([`bundles/`](../bundles/README.md)). Both kinds are listed in the first-party list |

A publisher never touches SurfSense's code, and the user sees the same Connect button whatever the publisher.

## Publishers

| Kind | Listed in | Shown as | Offered |
|---|---|---|---|
| SurfSense's | The first-party list | "By SurfSense" | Always: first-party |
| `verification: verified` | The registry | "By" its author, **Verified** | Once third-party plugins are allowed |
| `verification: community` | The registry | "By" its author, **Community** | Once third-party plugins are allowed, after a reminder |
| custom | The user's app | "Custom", not reviewed by SurfSense | Once third-party plugins are allowed |

Verification is the list's, never the plugin's, and a plugin is SurfSense's only by being in the first-party list, so no registry entry, and no server, can claim to be SurfSense.

**Verified** means SurfSense has proven that the company or project named as `author` runs the server, which is who receives the user's requests and sign-in. It is the namespace check the [MCP Registry](https://modelcontextprotocol.io/registry/about) and OpenAI's app directory make, not a review of quality. A maintainer checks it in the pull request:

1. The URL's host is on `domain`, a registered domain that belongs to `author`. Its sign-in hosts, for an `oauth` entry, may be elsewhere: they see the sign-in, never a tool call.
2. The publisher proves it controls `domain`, by any one of:
   - `https://{domain}/.well-known/surfsense-plugins.json`, holding `{"plugins": ["<id>"]}` with the entry's id;
   - a DNS TXT record on `domain`, `surfsense-plugin=<id>`;
   - the same server's URL published in the [MCP Registry](https://modelcontextprotocol.io/registry/about) under that domain's namespace, such as `com.notion/…`, whose DNS or HTTP proof already holds.

The proof is checked at review and again when a pull request changes the entry's URL, hosts or domain; the app never fetches it. Every other listing is **community**: reviewed the same way, but not proven to be run by the service it connects to, so Connect first says who runs it and that the user's requests and sign-in pass through their server. Verified is not a security audit, and a publisher can change its tools after review ([below](#tools-added-later)).

## Third-party plugins

Every plugin not published by SurfSense is third-party and starts off: verified and community plugins, and custom ones added by URL. Settings → Plugins shows first-party plugins and, below them, a Third-party section with one button, **Allow third-party plugins**. Pressing it, once, says they are run by other people, that what a tool is sent goes to its publisher, and that SurfSense reviews the listing, not every change to the server; then it asks for `plugins.surfsense.com` if it is not yet allowed, fetches the registry, and lists its plugins. Turning it back off disconnects nothing, but the section collapses and every third-party tool stops being offered until they are allowed again. The switch plays the part of Obsidian's Restricted mode, named for what it allows.

## Tools added later

A remote server can change any day, so every listing is compared with what `plugin_tools` recorded. The rule, which the rest of these docs refer to:

- a new tool starts off;
- a tool whose description changes, or whose annotations become less safe (no longer read-only, newly destructive or open world), is switched off;
- a removed tool disappears.

The plugin's row says what changed, such as "Notion added 1 tool: delete page", with a switch.

## Removing a plugin

- **From the registry:** a maintainer moves the entry to `removed` with a reason. An app that refreshes such a list stops offering the plugin's tools, keeps the user's connection so nothing is lost if it comes back, and shows the reason on its row. No installer carries a third-party entry, so a removed plugin is never listed again from an old copy.
- **From the first-party list:** SurfSense stops the plugin at once, with no app release: a remote plugin's server refuses its calls, which the user reads as the tool's refusal, and a bundle's versions are blocked where they are listed. The next release drops the entry.

## How the app gets the registry

The registry grows without app updates. It is served at `plugins.surfsense.com`, the hostname of SurfSense's own plugins, by a small registry container of its own beside the plugin host, so updating the list never restarts the plugins ([`../remote/02-surfsense-servers.md`](../remote/02-surfsense-servers.md#the-plugin-host)).

- On every merge to `dev` that changes `plugins/registry/`, a CI job adds `generated_at` and each icon's SHA-256, signs the file with an Ed25519 key held in a CI secret, and commits the signed file and `plugins.json.sig` back to `dev`. The release pull request carries them to `main`, so nothing pushes to `main`, and the registry container is built from `main`, serving them at `/plugins.json` and `/plugins.json.sig`, so the private key never reaches the server. Nobody edits the copy on the server.
- The app compiles in the URL and the public key, as it compiles in the keys that verify licenses offline ([ADR 0019](../../../adr/0019-offline-licenses.md)). A copy whose signature does not verify is ignored and the cached copy kept, and so is one with an unknown `schema_version` or a `generated_at` older than the cached copy's, so an old list cannot bring back a removed plugin. An icon whose hash differs from its entry's is not shown.
- Fetching needs consent for `plugins.surfsense.com`, which [`egress/service.py`](../../../../surfsense_local/backend/modules/egress/service.py) adds to `BUILT_IN`, off by default. It is the same host as SurfSense's plugins, so one consent covers both.
- The app fetches the registry when the user allows third-party plugins, then whenever Settings → Plugins opens. The last verified copy is kept in the app's data folder, so the section stays listed offline, with the date it was fetched.
- In development the app reads `plugins/registry/plugins.json` from the repository.

The first-party list needs none of this: `bundling/api.spec` packages it into the API binary, and in development the API reads it from its own tree.

### On the screen

- **By SurfSense** comes first, from the first-party list, with no network and no consent: each plugin with its description, its access ("License required"), and the host it runs on.
- **Third-party** follows. Until third-party plugins are allowed, the section is one sentence and a button, **Allow third-party plugins**. Once allowed, it lists the registry's plugins, each by its author and marked Verified or Community, with the date of the list.
- **Add a plugin by URL** is last.
- **Connect** asks for every host the plugin needs in one prompt, then for its sign-in.
- **Each plugin opens its public page** ([below](#a-plugins-page)), from By SurfSense and Third-party only. A connected plugin's row in Yours opens its settings instead: its status, its controls and the server's live tools with their switches, nothing more.

### A plugin's page

Every listed plugin has a public page, as each of Claude's connectors does, opened only from its entry in Browse and shown in place of the list with **Back**. It is built from the list entry alone, so it is the same for every user and the same whether the plugin is connected or not; one page serves first-party and registry plugins alike. A custom plugin has no entry, so no public page.

- **Header:** its icon, name and publisher ("By SurfSense", or "By" its author marked Verified or Community), and **Connect**, or "Connected" once it is.
- **About:** `about`. The card's `description` is never shown in its place.
- **Tools:** the entry's `tools`, each name as a chip in two columns, as Claude's connectors show them, with no description, no switch and no approval. Those are settings of a connected plugin, in Yours.
- **Details:** its authentication (none, the SurfSense license, an API key, or the user's account on its service, named), the hosts it connects to, the month it was added, and its homepage and privacy policy.

The list's `tools` describe a plugin to the user and nothing else. A server's tools are known for certain only by listing it, which needs its sign-in and, for a third-party host, consent the page cannot ask for just to describe it, so the list carries them. They never reach a model: the agent is given only what the server lists, under the rules for [tools added later](#tools-added-later). A registry entry's tools are checked in its pull request's review, like the rest of the entry; a first-party entry's are checked against each server by SurfSense's plugin host's tests. A server that changes its tools after review shows the old list on its page until its entry is updated.

## Bundle entries (later)

When bundles arrive ([`bundles/`](../bundles/README.md)), a bundle is one more entry, `kind: bundle`, in the list of its publisher.

A third party's bundle is a registry entry carrying each approved version's files:

```json
{
  "id": "acme-local",
  "kind": "bundle",
  "verification": "community",
  "name": "Acme Local",
  "description": "Query your local Acme database.",
  "author": "Jane Doe",
  "repo": "janedoe/surfsense-acme-local",
  "path": ".",
  "hosts": [],
  "access": "free",
  "privacy_policy": "https://example.com/privacy",
  "versions": [
    {
      "version": "1.2.0",
      "min_app_version": "2.6.0",
      "files": {
        "macos-arm64": { "url": "https://github.com/janedoe/surfsense-acme-local/releases/download/1.2.0/acme-local-1.2.0-macos-arm64.tar.gz", "sha256": "<64 hex>", "size": 812345 },
        "linux-x64": { "url": "…", "sha256": "…", "size": 0 },
        "windows-x64": { "url": "…", "sha256": "…", "size": 0 }
      },
      "blocked": []
    }
  ]
}
```

A SurfSense bundle is a first-party entry that says who it is and where its versions are listed: SurfSense's plugin host for a free one, the license server for a paid one ([ADR 0047](../../../adr/0047-premium-plugins-are-source-available.md)). Its versions, files and sha256s are fetched when the user installs or updates it. A new version needs no app release, and no bundle's files are ever in the installer.

How versions are built, scanned, verified and blocked is in [`bundles/`](../bundles/README.md).

## Acceptance

- The check fails a registry entry with a bad id, an `http` URL, `auth: license` or `access: license`, an `external` entry with no `access_note`, or a host list missing the URL's host, each with a line naming the field. It runs on the first-party list too.
- A pull request changing `plugins/registry/` cannot merge without a maintainer's approval.
- With no network and no consent, Settings → Plugins lists SurfSense's plugins from the first-party list, and no request leaves the machine.
- Allowing third-party plugins asks for `plugins.surfsense.com` once, fetches the registry and lists its plugins; turning them off collapses the section and no third-party tool reaches a caller.
- A registry merged to `main` with a new entry reaches a running app at its next refresh; one with an entry moved to `removed` stops its tools and shows the reason.
- A fetched registry with a bad signature is ignored and the cached copy kept. With no network, the cached copy is listed with its date.
- An entry in a fetched registry with `auth: license` or `access: license` is dropped by the app, and no request carries the license key to it.
- A third-party plugin cannot be connected until third-party plugins are allowed, and its tools never reach a caller.
- A tool a fake server adds after connecting is listed off and never reaches a caller until switched on.
- The check fails an entry whose `about` is too long, a tool name MCP does not allow or one listed twice, or an `added` that is not a `YYYY-MM` month, and a first-party entry with no `about`, `tools` or `added`.
- A plugin's public page shows its `about`, its listed tools and its details with no request leaving the machine, the same before and after it is connected, and no switch; Yours shows a connected plugin's live tools with their switches and nothing from its entry.
- A first-party entry whose `tools` differ from its server's tools fails the plugin host's tests.
- The check fails a registry entry whose `verification` is anything but `verified` or `community`, a `verified` entry with no `domain`, a `domain` that is a shared hosting suffix, or a `verified` entry whose URL's host is off its domain or, unless it signs in with OAuth, any of whose hosts is.
- Connect on a community plugin asks first, naming who runs it; a verified or first-party plugin connects at once.
