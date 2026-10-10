# Registry

> Owns: `plugins/registry/` (`plugins.json`, its schema, its check, the signing and publishing job, later the bundle scanner), the app's copy of the registry and its refresh (`modules/plugins/registry/`), the `CODEOWNERS` line for `plugins/registry/`.
> Decision: [ADR 0053](../../../adr/0053-plugins-are-listed-in-a-registry-and-third-party-ones-start-off.md).

## One list

`plugins/registry/plugins.json`, the registry, lists every plugin the app shows, SurfSense's included, plus removed ones. Nothing is maintained beside it. Only custom plugins added by URL live outside it, in the user's app.

The registry points at plugins and never holds them: a plugin's code, and later its bundle files, stay with its publisher. SurfSense's own plugin servers live in [`plugins/remote/`](../remote/02-surfsense-servers.md#layout) only because SurfSense publishes them. The registry sits beside it, in `plugins/registry/`, because it lists every kind of plugin, bundles later included.

An illustrative entry, not a real listing:

```json
{
  "schema_version": 1,
  "plugins": [
    {
      "id": "notion",
      "kind": "remote",
      "publisher": "partner",
      "name": "Notion",
      "description": "Search and read your Notion pages and databases.",
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
| `id` | `^[a-z][a-z0-9-]{0,63}$`, unique, never reused once listed |
| `kind` | `remote`. `bundle` is reserved ([below](#bundle-entries-later)) |
| `publisher` | `surfsense`, `partner` or `community` |
| `name`, `description`, `author` | Display text, 1–80, 1–200 and 1–80 characters |
| `url` | `remote` only. `https`, no credentials in it; the server's MCP endpoint |
| `auth` | `{ "type": "oauth" }`, `{ "type": "token", "title", "description" }`, `{ "type": "license" }` (SurfSense only) or `{ "type": "none" }` |
| `hosts` | Every host the app contacts for this plugin: for a remote one, the URL's host and the authorization server's hosts. Exact hostnames, no loopback |
| `access` | `free`, `license` (SurfSense only, [`05-paid.md`](05-paid.md)) or `external` |
| `access_note` | Required when `access` is `external`: what the user must buy or have, in a sentence |
| `privacy_policy` | Required for every publisher other than `surfsense` |
| `homepage`, `icon` | Optional. Icons live in `plugins/registry/icons/` |
| `min_app_version` | Optional. Older apps do not list the entry |

Unknown fields are ignored, so a newer field does not break an older app. `schema_version` rises only when the structure breaks.

## Adding a plugin

1. The publisher opens a pull request into `dev` adding one entry, and its icon. A submission site can replace the pull request later.
2. CI runs the registry check:
   - the entry matches the rules above;
   - a remote server answers `initialize` and `tools/list` at `url`, or, for one that needs sign-in, its protected resource metadata names an authorization server on a declared host;
   - every tool has a description of at most 2,000 characters, and the tool list, with names, descriptions and annotations, is posted on the pull request.
3. A maintainer reviews the entry once: who runs the server, what its tools do, whether their descriptions carry instructions aimed at the model, whether the hosts are complete, whether the privacy policy is real. `partner` needs evidence the author speaks for the company.
4. Once merged and on `main`, the entry reaches every app at its next refresh, without an app update ([below](#how-the-app-gets-the-registry)).

A later change to an entry is the same pull request and the same review. A change to a remote server needs none: the publisher deploys when they like, which is why tools added later start off ([below](#tools-added-later)).

`CODEOWNERS` requires a maintainer's approval for every change under `plugins/registry/`.

## Who can publish what

| Publisher's situation | What they do |
|---|---|
| Already runs an MCP server, as many products do | One registry entry pointing at it. Nothing else to build |
| Has an API but no MCP server | Builds a remote MCP server over its API, with any MCP SDK, and hosts it: then it works in SurfSense and every other MCP client. Later, a bundle is the alternative for a publisher that will not host anything ([`bundles/`](../bundles/README.md)) |
| Wants the agent to use its tools well | Adds skills to its entry once plugins carry them ([`06-later.md`](06-later.md)) |
| A community developer wrapping someone else's public API | Hosts the server themselves and lists it as `community`, never `partner`. The entry and the screen say who runs the server, and its privacy policy is the developer's, since the user's requests and credentials pass through it |
| SurfSense | Its own servers in `plugins/remote/` and `plugins/remote/proprietary/`, run on its plugin host ([`../remote/02-surfsense-servers.md`](../remote/02-surfsense-servers.md#surfsenses-own-servers)), listed as `surfsense` |

A publisher never touches SurfSense's code, and the user sees the same Connect button whatever the publisher.

## Publishers

| Publisher | Shown as | Restricted mode |
|---|---|---|
| `surfsense` | "By SurfSense" | Not affected |
| `partner` | The company's name, "Verified" | Off until turned on |
| `community` | The author's name | Off until turned on |
| custom (not in the registry) | "Not reviewed by SurfSense" | Off until turned on |

The publisher is the registry's, never the plugin's, so no server can claim to be SurfSense.

## Restricted mode

Every plugin not published by SurfSense starts off. Settings → Plugins shows them greyed until the user turns third-party plugins on once, with a sentence saying they are run by other people, that what a tool is sent goes to its publisher, and that SurfSense reviews the listing, not every change to the server. Turning it back off disconnects nothing, but every third-party tool stops being offered until it is on again.

## Tools added later

A remote server can change any day, so every listing is compared with what `plugin_tools` recorded. The rule, which the rest of these docs refer to:

- a new tool starts off;
- a tool whose description changes, or whose annotations become less safe (no longer read-only, newly destructive or open world), is switched off;
- a removed tool disappears.

The plugin's row says what changed, such as "Notion added 1 tool: delete page", with a switch.

## Removing a plugin

A maintainer moves an entry to `removed` with a reason. An app that refreshes such a list stops offering the plugin's tools, keeps the user's connection so nothing is lost if it comes back, and shows the reason on its row.

## How the app gets the registry

The registry grows without app updates. It is served by SurfSense's plugin host, `plugins.surfsense.com`, which also serves SurfSense's own plugins and is the only host the license key is ever sent to ([`../remote/02-surfsense-servers.md`](../remote/02-surfsense-servers.md#the-plugin-host), [`05-paid.md`](05-paid.md)).

| Copy | Where | Written by |
|---|---|---|
| Source | `plugins/registry/plugins.json` in this repository | Pull requests, reviewed by a maintainer |
| Live | `https://plugins.surfsense.com/plugins.json` and `/plugins.json.sig` | CI, on merge to `main` |
| Shipped | Inside the app, packaged into the API binary as the model manifests are | The release build |

- On every merge to `main` that changes `plugins/registry/`, a CI job adds `generated_at`, signs the file with an Ed25519 key held in a CI secret, and deploys the plugin host with the signed file in its image. Nobody edits the copy on the server.
- The app compiles in the URL and the public key, as it compiles in the keys that verify licenses offline ([ADR 0019](../../../adr/0019-offline-licenses.md)). A copy whose signature does not verify is ignored.
- The release build packages the registry signed at that commit. In development the app reads `plugins/registry/plugins.json` directly.
- Fetching the live copy needs consent for `plugins.surfsense.com`, which [`egress/service.py`](../../../../surfsense_local/backend/modules/egress/service.py) adds to `BUILT_IN`, off by default. Until the user allows it, the shipped copy is the one used; after that, the newer of the two by `generated_at`. A copy with an unknown `schema_version` is ignored.
- Connecting a SurfSense plugin needs consent for the same host, so one consent covers both.
- The first Connect of any plugin also offers the registry host, ticked: "Keep the plugin list up to date (plugins.surfsense.com)". A removal reaches only apps that refresh, and every app update; this is how it reaches users who connect only third-party plugins.

### On the screen

Settings → Plugins lists the registry with no network and no consent, from the shipped copy:

- A line says how old the list is, "Plugin list from 2 Oct 2026", with **Check for new plugins**, which asks for `plugins.surfsense.com` once. Once allowed, the screen refreshes on its own when opened.
- **By SurfSense** comes first: each plugin with its description, its access ("License required"), and the host it runs on.
- **Other publishers** follow, partners marked "Verified", community plugins by their author, greyed while Restricted mode is on.
- **Add a plugin by URL** is last.
- **Connect** asks for every host the plugin needs in one prompt, then for its sign-in.

## Bundle entries (later)

When bundles arrive ([`bundles/`](../bundles/README.md)), a bundle is one more entry in the same list:

```json
{
  "id": "acme-local",
  "kind": "bundle",
  "publisher": "community",
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

How versions are built, scanned, verified and blocked is in [`bundles/`](../bundles/README.md).

## Acceptance

- The check fails an entry with a bad id, an `http` URL, `auth: license` on a non-SurfSense publisher, an `external` entry with no `access_note`, or a host list missing the URL's host, each with a line naming the field.
- A pull request changing `plugins/registry/` cannot merge without a maintainer's approval.
- With no network and no consent, Settings → Plugins lists the shipped registry with its date, and no request leaves the machine.
- The first Connect of any plugin offers `plugins.surfsense.com` for the registry, ticked; unticking it connects the plugin and leaves the host off.
- A registry merged to `main` with a new entry reaches a running app at its next refresh; one with an entry moved to `removed` stops its tools and shows the reason.
- A fetched registry with a bad signature is ignored and the previous copy kept.
- A third-party plugin cannot be connected while Restricted mode is on, and its tools never reach a caller.
- A tool a fake server adds after connecting is listed off and never reaches a caller until switched on.
