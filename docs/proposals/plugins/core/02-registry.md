# Plugin lists

> Owns: the built-in list (`surfsense_local/backend/modules/plugins/built_in/`), the registry (`plugins/registry/`: `plugins.json`, the entry schema both lists follow, its check, the signing job, later the bundle scanner), the app's cached copy of the registry and its refresh (`modules/plugins/registry/`), the `CODEOWNERS` line for `plugins/registry/`.
> Decision: [ADR 0053](../../../adr/0053-plugins-are-listed-in-a-registry-and-third-party-ones-start-off.md).

## Two lists

The app knows plugins from two lists that share one entry schema. Only custom plugins added by URL live outside them, in the user's app.

| | The built-in list | The registry |
|---|---|---|
| Lists | SurfSense's plugins | Partners' and community plugins, plus removed ones |
| Lives in | `surfsense_local/backend/modules/plugins/built_in/plugins.json` | `plugins/registry/plugins.json` |
| Reaches the app | Packaged into the API binary, as the model catalogs are | Fetched, signed, from `plugins.surfsense.com` once the user turns on other publishers, then cached |
| Changes with | An app release | A merged pull request, with no app update |
| Shown | Always, with no network and no consent | Once the user turns on other publishers |

- **Lists point at plugins and never hold them.** A plugin's code, and later its bundle files, stay with its publisher. A built-in entry is a few hundred bytes, so the app does not grow with plugins, and a third-party plugin never changes the app.
- **The built-in list changes only when SurfSense adds or retires a plugin.** What changes more often, a server's tools or a bundle's versions, is read from where the plugin is hosted.
- **Only the built-in list speaks for SurfSense.** `publisher: surfsense`, `auth: license` and `access: license` appear in it alone. The registry check refuses them, and the app drops them from a fetched registry, so no fetched file can claim to be SurfSense or receive the license key ([`05-paid.md`](05-paid.md)).

An illustrative registry entry, not a real listing:

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
| `id` | `^[a-z][a-z0-9-]{0,63}$`, unique across both lists, never reused once listed |
| `kind` | `remote`. `bundle` is reserved ([below](#bundle-entries-later)) |
| `publisher` | `surfsense` in the built-in list; `partner` or `community` in the registry |
| `name`, `description`, `author` | Display text, 1–80, 1–200 and 1–80 characters |
| `url` | `remote` only. `https`, no credentials in it; the server's MCP endpoint |
| `auth` | `{ "type": "oauth" }`, `{ "type": "token", "title", "description" }`, `{ "type": "none" }`, or `{ "type": "license" }` in the built-in list only |
| `hosts` | Every host the app contacts for this plugin: for a remote one, the URL's host and the authorization server's hosts. Exact hostnames, no loopback |
| `access` | `free` or `external`, or `license` in the built-in list only ([`05-paid.md`](05-paid.md)) |
| `access_note` | Required when `access` is `external`: what the user must buy or have, in a sentence |
| `privacy_policy` | Required in the registry |
| `homepage`, `icon` | Optional. Icons live beside their list: `plugins/registry/icons/`, or `built_in/icons/` in the app |
| `min_app_version` | Registry only, optional. Older apps do not list the entry |

Unknown fields are ignored, so a newer field does not break an older app. `schema_version` rises only when the structure breaks.

## Adding a plugin

A partner or a community developer:

1. Opens a pull request into `dev` adding one entry to the registry, and its icon. A submission site can replace the pull request later.
2. CI runs the check:
   - the entry matches the rules above;
   - a remote server answers `initialize` and `tools/list` at `url`, or, for one that needs sign-in, its protected resource metadata names an authorization server on a declared host;
   - every tool has a description of at most 2,000 characters, and the tool list, with names, descriptions and annotations, is posted on the pull request.
3. A maintainer reviews the entry once: who runs the server, what its tools do, whether their descriptions carry instructions aimed at the model, whether the hosts are complete, whether the privacy policy is real. `partner` needs evidence the author speaks for the company.
4. Once merged and on `main`, the entry reaches every app that lists other publishers at its next refresh, without an app update ([below](#how-the-app-gets-the-registry)).

A later change to an entry is the same pull request and the same review. A change to a remote server needs none: the publisher deploys when they like, which is why tools added later start off ([below](#tools-added-later)).

SurfSense adds a plugin by adding its entry to the built-in list in the same change as the plugin itself ([`../remote/02-surfsense-servers.md`](../remote/02-surfsense-servers.md)). The same check runs on the built-in list.

`CODEOWNERS` requires a maintainer's approval for every change under `plugins/registry/`.

## Who can publish what

| Publisher's situation | What they do |
|---|---|
| Already runs an MCP server, as many products do | One registry entry pointing at it. Nothing else to build |
| Has an API but no MCP server | Builds a remote MCP server over its API, with any MCP SDK, and hosts it: then it works in SurfSense and every other MCP client. Later, a bundle is the alternative for a publisher that will not host anything ([`bundles/`](../bundles/README.md)) |
| Wants the agent to use its tools well | Adds skills to its entry once plugins carry them ([`06-later.md`](06-later.md)) |
| A community developer wrapping someone else's public API | Hosts the server themselves and lists it as `community`, never `partner`. The entry and the screen say who runs the server, and its privacy policy is the developer's, since the user's requests and credentials pass through it |
| SurfSense | Its own plugins in `plugins/remote/` and `plugins/remote/proprietary/`, run on its plugin host and listed in the built-in list ([`../remote/02-surfsense-servers.md`](../remote/02-surfsense-servers.md#surfsenses-own-servers)) |

A publisher never touches SurfSense's code, and the user sees the same Connect button whatever the publisher.

## Publishers

| Publisher | Listed in | Shown as | Restricted mode |
|---|---|---|---|
| `surfsense` | The built-in list | "By SurfSense" | Not affected |
| `partner` | The registry | The company's name, "Verified" | Off until turned on |
| `community` | The registry | The author's name | Off until turned on |
| custom | The user's app | "Not reviewed by SurfSense" | Off until turned on |

The publisher is the list's, never the plugin's, and only the built-in list can say `surfsense`, so no server can claim to be SurfSense.

## Restricted mode

Every plugin not published by SurfSense starts off. Settings → Plugins shows SurfSense's plugins and, below them, a section for other publishers with one button. Turning other publishers on, once, says they are run by other people, that what a tool is sent goes to its publisher, and that SurfSense reviews the listing, not every change to the server; then it asks for `plugins.surfsense.com` if it is not yet allowed, fetches the registry, and lists its plugins. Custom plugins added by URL wait for the same switch. Turning it back off disconnects nothing, but the section collapses and every third-party tool stops being offered until it is on again.

## Tools added later

A remote server can change any day, so every listing is compared with what `plugin_tools` recorded. The rule, which the rest of these docs refer to:

- a new tool starts off;
- a tool whose description changes, or whose annotations become less safe (no longer read-only, newly destructive or open world), is switched off;
- a removed tool disappears.

The plugin's row says what changed, such as "Notion added 1 tool: delete page", with a switch.

## Removing a plugin

- **From the registry:** a maintainer moves the entry to `removed` with a reason. An app that refreshes such a list stops offering the plugin's tools, keeps the user's connection so nothing is lost if it comes back, and shows the reason on its row. No installer carries a third-party entry, so a removed plugin is never listed again from an old copy.
- **From the built-in list:** SurfSense's server refuses the plugin's calls at once, which the user reads as the tool's refusal, and the next release drops the entry.

## How the app gets the registry

The registry grows without app updates. It is served by SurfSense's plugin host, `plugins.surfsense.com`, which also serves SurfSense's own plugins ([`../remote/02-surfsense-servers.md`](../remote/02-surfsense-servers.md#the-plugin-host)).

- On every merge to `main` that changes `plugins/registry/`, a CI job adds `generated_at`, signs the file with an Ed25519 key held in a CI secret, and deploys the plugin host with the signed file in its image, at `/plugins.json` and `/plugins.json.sig`. Nobody edits the copy on the server.
- The app compiles in the URL and the public key, as it compiles in the keys that verify licenses offline ([ADR 0019](../../../adr/0019-offline-licenses.md)). A copy whose signature does not verify is ignored and the cached copy kept. A copy with an unknown `schema_version` is ignored.
- Fetching needs consent for `plugins.surfsense.com`, which [`egress/service.py`](../../../../surfsense_local/backend/modules/egress/service.py) adds to `BUILT_IN`, off by default. It is the same host as SurfSense's plugins, so one consent covers both.
- The app fetches the registry when the user turns on other publishers, then whenever Settings → Plugins opens. The last verified copy is kept in the app's data folder, so the section stays listed offline, with the date it was fetched.
- In development the app reads `plugins/registry/plugins.json` from the repository.

The built-in list needs none of this: `bundling/api.spec` packages it into the API binary, and in development the API reads it from its own tree.

### On the screen

- **By SurfSense** comes first, from the built-in list, with no network and no consent: each plugin with its description, its access ("License required"), and the host it runs on.
- **Other publishers** follow. While Restricted mode is on, the section is one sentence and a button, **Show plugins from other publishers**. Once on, it lists the registry's plugins, partners marked "Verified" and community plugins by their author, with the date of the list.
- **Add a plugin by URL** is last.
- **Connect** asks for every host the plugin needs in one prompt, then for its sign-in.

## Bundle entries (later)

When bundles arrive ([`bundles/`](../bundles/README.md)), a bundle is one more entry, `kind: bundle`, in the list of its publisher.

A third party's bundle is a registry entry carrying each approved version's files:

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

A SurfSense bundle is a built-in entry that says who it is and where its versions are listed: SurfSense's plugin host for a free one, the license server for a paid one ([ADR 0047](../../../adr/0047-premium-plugins-are-source-available.md)). Its versions, files and sha256s are fetched when the user installs or updates it. A new version needs no app release, and no bundle's files are ever in the installer.

How versions are built, scanned, verified and blocked is in [`bundles/`](../bundles/README.md).

## Acceptance

- The check fails a registry entry with a bad id, an `http` URL, `publisher: surfsense`, `auth: license` or `access: license`, an `external` entry with no `access_note`, or a host list missing the URL's host, each with a line naming the field. It runs on the built-in list too.
- A pull request changing `plugins/registry/` cannot merge without a maintainer's approval.
- With no network and no consent, Settings → Plugins lists SurfSense's plugins from the built-in list, and no request leaves the machine.
- Turning on other publishers asks for `plugins.surfsense.com` once, fetches the registry and lists its plugins; turning them off collapses the section and no third-party tool reaches a caller.
- A registry merged to `main` with a new entry reaches a running app at its next refresh; one with an entry moved to `removed` stops its tools and shows the reason.
- A fetched registry with a bad signature is ignored and the cached copy kept. With no network, the cached copy is listed with its date.
- An entry in a fetched registry with `publisher: surfsense` or `auth: license` is dropped by the app, and no request carries the license key to it.
- A third-party plugin cannot be connected while Restricted mode is on, and its tools never reach a caller.
- A tool a fake server adds after connecting is listed off and never reaches a caller until switched on.
