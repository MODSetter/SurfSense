# Registry

> Owns: `plugins/registry/` (`plugins.json`, its schema, its check, the signing and publishing job, later the bundle scanner), the catalog the app ships and refreshes (`modules/plugins/registry/`), the `CODEOWNERS` lines for `plugins/registry/` and `plugins/proprietary/`.
> Decision: [ADR 0053](../../adr/0053-plugins-are-listed-in-a-registry-and-third-party-ones-start-off.md).

## One list

`plugins/registry/plugins.json` is the one list of plugins, and nothing else is maintained beside it. It holds every plugin the app shows, whoever publishes it and however it runs: SurfSense's own, free and paid, partners' and the community's, remote now and bundles later. It also holds removed plugins and, later, bundle versions and blocks. Only a plugin a user adds by URL is not in it; that one lives in the user's app alone ([`03-remote-plugins.md`](03-remote-plugins.md)).

The list says where a plugin is, never what it is made of. A plugin's code, its own manifest, and later its bundle files stay with its publisher; this repository holds an entry pointing at them. SurfSense's own plugins are the exception only because SurfSense is their publisher: their servers live in [`plugins/`](../../../plugins/README.md) ([`03-remote-plugins.md`](03-remote-plugins.md#surfsenses-own-servers)).

Obsidian works this way: one list of community plugins, each pointing at its author's GitHub repository, whose releases hold the files ([obsidianmd/obsidian-releases](https://github.com/obsidianmd/obsidian-releases)).

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
| `access` | `free`, `license` (SurfSense only, [`06-paid.md`](06-paid.md)) or `external` |
| `access_note` | Required when `access` is `external`: what the user must buy or have, in a sentence |
| `privacy_policy` | Required for every publisher other than `surfsense` |
| `homepage`, `icon` | Optional. Icons live in `plugins/registry/icons/` |
| `min_app_version` | Optional. Older apps do not list the entry |

Unknown fields are ignored, so a newer field does not break an older app. `schema_version` rises only when the structure breaks.

## Adding a plugin

1. The publisher opens a pull request into `dev` adding one entry, and its icon. A submission site can replace the pull request later, as Obsidian's community.obsidian.md did; the list stays the same.
2. CI runs the registry check:
   - the entry matches the rules above;
   - a remote server answers `initialize` and `tools/list` at `url`, or, for one that needs sign-in, its protected resource metadata names an authorization server on a declared host;
   - every tool has a description of at most 2,000 characters, and the tool list, with names, descriptions and annotations, is posted on the pull request.
3. A maintainer reviews the entry once: who runs the server, what its tools do, whether their descriptions carry instructions aimed at the model, whether the hosts are complete, whether the privacy policy is real. `partner` needs evidence the author speaks for the company.
4. Once merged and on `main`, the entry reaches every app at its next refresh, without an app update ([below](#how-the-app-gets-the-list)).

A later change to an entry is the same pull request and the same review. A change to a remote server needs none: the publisher deploys when they like, which is why tools added later start off ([below](#tools-added-later)).

`CODEOWNERS` requires a maintainer's approval for every change under `plugins/registry/`, and the check refuses an entry with `publisher: surfsense` or `partner` unless a maintainer opened or approved it.

## Who can publish what

| Publisher's situation | What they do |
|---|---|
| Already runs an MCP server, as many products do | One registry entry pointing at it. Nothing else to build |
| Has an API but no MCP server | Builds a remote MCP server over its API, with any MCP SDK, and hosts it: then it works in SurfSense and every other MCP client. Later, a bundle is the alternative for a publisher that will not host anything ([`bundles/`](bundles/README.md)) |
| Wants the agent to use its tools well | Adds skills to its entry once plugins carry them ([`07-later.md`](07-later.md)) |
| A community developer wrapping someone else's public API | Hosts the server themselves and lists it as `community`, never `partner`. The entry and the screen say who runs the server, and its privacy policy is the developer's, since the user's requests and credentials pass through it |
| SurfSense | Its own servers in [`plugins/`](../../../plugins/README.md) and `plugins/proprietary/` ([`03-remote-plugins.md`](03-remote-plugins.md#surfsenses-own-servers)), listed as `surfsense` |

A publisher never touches SurfSense's code, and the user sees the same Connect button whatever the publisher.

## Publishers

| Publisher | Shown as | Restricted mode |
|---|---|---|
| `surfsense` | "By SurfSense" | Not affected |
| `partner` | The company's name, "Verified" | Off until turned on |
| `community` | The author's name | Off until turned on |
| custom (not in the list) | "Not reviewed by SurfSense" | Off until turned on |

The publisher is the list's, never the plugin's, so no server can claim to be SurfSense.

## Restricted mode

Every plugin not published by SurfSense starts off. Settings → Plugins shows them greyed until the user turns third-party plugins on once, with a sentence saying they are run by other people, that what a tool is sent goes to its publisher, and that SurfSense reviews the listing, not every change to the server. Turning it back off disconnects nothing, but every third-party tool stops being offered until it is on again. Obsidian ships its community plugins the same way.

## Tools added later

A remote server can change any day. The tools a user saw when connecting are recorded in `plugin_tools`. A tool that appears afterwards starts off, and the plugin's row says "Notion added 1 tool: delete page", with a switch. A tool whose annotations change from read-only to anything else, or whose description changes, is switched off again the same way. A removed tool disappears.

## Removing a plugin

A maintainer moves an entry to `removed` with a reason. An app that refreshes such a list stops offering the plugin's tools, keeps the user's connection so nothing is lost if it comes back, and shows the reason on its row.

## How the app gets the list

The list grows without app updates. Obsidian serves its list from its own server, `community.obsidian.md`, and keeps the GitHub copy as a mirror; SurfSense serves its list from its own server too.

- On every merge to `main` that changes `plugins/registry/`, a CI job adds `generated_at`, signs the file with an Ed25519 key held in a CI secret, and uploads the file and its signature to SurfSense's plugin host, for example `https://plugins.surfsense.com/plugins.json`. This is the same list, published; nobody edits the copy on the server.
- The app compiles in that URL and the public key, as it compiles in the keys that verify licenses offline ([ADR 0019](../../adr/0019-offline-licenses.md)). A copy whose signature does not verify is ignored.
- Fetching it needs consent for SurfSense's plugin host, which [`egress/service.py`](../../../surfsense_local/backend/modules/egress/service.py) adds to `BUILT_IN`, off by default. Settings → Plugins has a Refresh button and refreshes on its own when opened, once allowed.
- The installer carries the list as it was at build, so Settings → Plugins is not empty with no network. Of the shipped and the fetched copy, the later `generated_at` wins, and a copy with an unknown `schema_version` is ignored.
- Serving from SurfSense's own host keeps the app independent of where the file is stored: a CDN or another provider can take over without an app update.

## Bundle entries (later)

When bundles arrive ([`bundles/`](bundles/README.md)), a bundle is one more entry in the same list:

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

- The code, the plugin's own manifest and its release files stay in the author's repository. Nothing of them is copied into this repository or rehosted by SurfSense.
- The author builds a release's files with a GitHub Action SurfSense provides in its plugin template, one archive per platform, and attaches them to a GitHub release in their repository, as Obsidian plugins attach `main.js` to theirs.
- A scanner job watches listed repositories for new releases, runs the bundle checks on the release's source and files, and, when they pass, commits the version with each file's URL and sha256 to the entry. People review the first version and any version that adds a host, a secret, or an open-world or destructive tool; the scanner holds those for them.
- The app downloads from the author's release and refuses a file whose sha256 differs from the list's, so a file swapped after the scan never runs.
- A maintainer blocks a version by adding a reason to its `blocked`.

## Acceptance

- The check fails an entry with a bad id, an `http` URL, `auth: license` on a non-SurfSense publisher, an `external` entry with no `access_note`, or a host list missing the URL's host, each with a line naming the field.
- A pull request adding a `surfsense` entry fails without a maintainer's approval.
- With no network, Settings → Plugins lists the shipped list.
- A list merged to `main` with a new entry reaches a running app at its next refresh; one with an entry moved to `removed` stops its tools and shows the reason.
- A fetched list with a bad signature is ignored and the previous copy kept.
- A third-party plugin cannot be connected while Restricted mode is on, and its tools never reach a caller.
- A tool a fake server adds after connecting is listed off and never reaches a caller until switched on.
