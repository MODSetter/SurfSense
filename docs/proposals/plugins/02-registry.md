# Registry

> Owns: `plugins/registry/` (`connectors.json`, its schema, its check), the catalog the app bundles and refreshes (`modules/plugins/registry/`), the `CODEOWNERS` line for `plugins/registry/` and `plugins/proprietary/`.
> Decision: [ADR 0053](../../adr/0053-plugins-are-listed-in-a-registry-and-third-party-ones-start-off.md).

## The list

`plugins/registry/connectors.json` lists every plugin the app shows. Obsidian keeps its community list the same way, a JSON file in [obsidianmd/obsidian-releases](https://github.com/obsidianmd/obsidian-releases) that points at code living elsewhere; here an entry points at a server. An illustrative entry, not a real listing:

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
| `kind` | `remote`. `bundle` is reserved for [bundles](bundles/README.md) |
| `publisher` | `surfsense`, `partner` or `community`. Only maintainers merge `surfsense` and `partner` entries |
| `name`, `description`, `author` | Display text, 1–80, 1–200 and 1–80 characters |
| `url` | `https`, no credentials in it; the server's MCP endpoint |
| `auth` | `{ "type": "oauth" }`, `{ "type": "token", "title", "description" }`, `{ "type": "license" }` (SurfSense only) or `{ "type": "none" }` |
| `hosts` | Every host the app contacts for this plugin: the URL's host and, for OAuth, the authorization server's hosts. Exact hostnames, no loopback |
| `access` | `free`, `license` (SurfSense only, [`06-paid.md`](06-paid.md)) or `external` |
| `access_note` | Required when `access` is `external`: what the user must buy or have, in a sentence |
| `privacy_policy` | Required for every publisher other than `surfsense` |
| `homepage`, `icon` | Optional. Icons live in `plugins/registry/icons/` |
| `min_app_version` | Optional. Older apps do not list the entry |

Unknown fields are ignored, so a newer field does not break an older app. `schema_version` rises only when the structure breaks.

## Adding a plugin

1. The publisher opens a pull request into `dev` adding one entry, and its icon.
2. CI runs the registry check:
   - the entry matches the rules above;
   - the server answers `initialize` and `tools/list` at `url`, or, for one that needs sign-in, its protected resource metadata names an authorization server on a declared host;
   - every tool has a description, and the tool list, with names, descriptions and annotations, is posted on the pull request.
3. A maintainer reviews the entry once: who runs the server, what its tools do, whether their descriptions carry instructions aimed at the model, whether the hosts are complete, whether the privacy policy is real. `partner` needs evidence the author speaks for the company.
4. Merged into `dev`, the entry reaches users on the next registry refresh after it reaches `main`.

A later change to an entry is the same pull request and the same review. A change to the server needs none: the publisher deploys when they like, which is why tools added later start off ([below](#tools-added-later)).

## Publishers

| Publisher | Shown as | Restricted mode |
|---|---|---|
| `surfsense` | "By SurfSense" | Not affected |
| `partner` | The company's name, "Verified" | Off until turned on |
| `community` | The author's name | Off until turned on |
| custom (not in the registry) | "Not reviewed by SurfSense" | Off until turned on |

The publisher is the registry's, never the plugin's, so no server can claim to be SurfSense.

## Restricted mode

Every plugin not published by SurfSense starts off. Settings → Plugins shows them greyed until the user turns third-party plugins on once, with a sentence saying they are run by other people, that what a tool is sent goes to its publisher, and that SurfSense reviews the listing, not every change to the server. Turning it back off disconnects nothing, but every third-party tool stops being offered until it is on again. Obsidian ships its community plugins the same way.

## Tools added later

A remote server can change any day. The tools a user saw when connecting are recorded in `plugin_tools`. A tool that appears afterwards starts off, and the plugin's row says "Notion added 1 tool: delete page", with a switch. A tool whose annotations change from read-only to anything else is switched off again the same way. A removed tool disappears.

## Removing a plugin

A maintainer moves an entry to `removed` with a reason. An app that refreshes such a registry stops offering the plugin's tools, keeps the user's connection so nothing is lost if it comes back, and shows the reason on its row.

## In the app

- The installer carries the registry as it was at build, so the list shows with no network.
- A refresh fetches `https://raw.githubusercontent.com/MODSetter/SurfSense/main/plugins/registry/connectors.json`, a URL compiled into the app, after consent for `raw.githubusercontent.com`, which [`egress/service.py`](../../../surfsense_local/backend/modules/egress/service.py) adds to `BUILT_IN`, off by default. Settings → Plugins has a Refresh button and refreshes on its own when opened, once allowed.
- Of the bundled and the refreshed copy, the one with the later `generated_at` the check writes into it wins. A copy with an unknown `schema_version` is ignored.
- `main` is protected, and only a merged pull request changes the file, so the refresh needs no signature of its own.

## Acceptance

- The check fails an entry with a bad id, an `http` URL, `auth: license` on a non-SurfSense publisher, an `external` entry with no `access_note`, or a host list missing the URL's host, each with a line naming the field.
- With no network, Settings → Plugins lists the bundled registry.
- A refreshed registry with a new entry lists it; one with an entry moved to `removed` stops its tools and shows the reason.
- A third-party plugin cannot be connected while Restricted mode is on, and its tools never reach a caller.
- A tool a fake server adds after connecting is listed off and never reaches a caller until switched on.
