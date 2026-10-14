# Plugins

A plugin is a remote [MCP](https://modelcontextprotocol.io) server that gives SurfSense's agent tools. You host the server; SurfSense lists it, asks the user before connecting, and calls it. Any MCP server that works in other MCP clients works here unchanged. How SurfSense handles plugins is in [plugins](../docs/architecture/plugins.md).

| Folder | What it holds |
|---|---|
| [`registry/`](registry/) | The list of third-party plugins, their icons, the check every entry passes, and the container that serves them |
| [`remote/`](remote/) | SurfSense's own plugins and the plugin host that runs them. Maintainers only for `remote/proprietary/` |
| [`bundles/`](bundles/README.md) | Deferred. The earlier, local design's SDK and tooling, kept for plugins that run on the user's machine |

The rest of this page is for publishers: companies and developers listing their own MCP server.

## 1. Build a server

- **Remote, over Streamable HTTP, on HTTPS.** SurfSense does not run servers started by a command (`npx`, `uvx`), and does not speak the legacy SSE transport. Any official MCP SDK serves Streamable HTTP.
- **Protocol `2025-11-25` or newer.** SurfSense also speaks `2026-07-28`.
- **Stateless if you can.** A server that keeps no session between requests survives restarts and scaling, and loses nothing when SurfSense reconnects it, as it does when a sign-in token is refreshed.
- **Annotate every tool.** `readOnlyHint` and `destructiveHint` decide whether SurfSense asks the user before a call. A tool that says neither may destroy, as MCP's defaults say, so it asks before every call; a read-only one, or one marked `destructiveHint: false`, asks until the user chooses to always allow it.
- **Describe tools for a model.** Say what the tool does and when to use it, as briefly as that allows: every description reaches the model on every turn. Instructions aimed at the model, such as "always call this first", are rejected in review.
- **Sign-in**, one of:

  | `auth` | The user | Your server receives |
  |---|---|---|
  | `none` | Does nothing | No credentials |
  | `token` | Pastes a key you give them | `Authorization: Bearer <key>` |
  | `oauth` | Signs in on your page in their browser | `Authorization: Bearer <access token>` |

  OAuth follows [MCP's authorization spec](https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization): serve protected resource metadata, and support Client ID Metadata Documents or dynamic client registration. SurfSense signs in as `https://plugins.surfsense.com/oauth/client.json` and redirects to `https://plugins.surfsense.com/oauth/callback`. If you only accept clients registered in advance, register SurfSense with those values and put the client id in your entry's `auth.client_id`. SurfSense is a public client: it never holds a client secret.

## 2. Try it in SurfSense

You need no listing to try your server:

1. Settings → Plugins → turn on **Allow third-party plugins**.
2. **Add custom plugin**, with a name, its URL and, if it needs one, a key.
3. Allow the tools you want, then ask the agent to use them in an Agentic thread.

A server added this way is marked third-party, not reviewed by SurfSense, and stays on that one computer.

## 3. List it

Open a pull request into `dev` that adds your entry to [`registry/plugins.json`](registry/plugins.json) and your icon to [`registry/icons/`](registry/icons/).

```json
{
  "id": "acme-docs",
  "kind": "remote",
  "verification": "community",
  "name": "Acme Docs",
  "description": "Search and read Acme's public documentation.",
  "author": "Acme Inc.",
  "url": "https://mcp.acme.example/mcp",
  "auth": { "type": "none" },
  "hosts": ["mcp.acme.example"],
  "access": "free",
  "privacy_policy": "https://acme.example/privacy",
  "homepage": "https://acme.example",
  "icon": "acme-docs.svg",
  "about": "Search Acme's public documentation and read any page of it in full, so the agent answers from the current docs rather than from memory.",
  "tools": ["search_docs", "read_page"],
  "added": "2026-10"
}
```

- **`id`**: lowercase letters, digits and hyphens, unique, never reused once listed.
- **`verification`**: `community`, unless you prove you run the server; then a maintainer sets `verified`, shown with a checkmark, and adds `domain`, the registered domain you proved. Prove it with one of:
  - a file at `https://<domain>/.well-known/surfsense-plugins.json` holding `{"plugins": ["<id>"]}`;
  - a DNS TXT record `surfsense-plugin=<id>` on `<domain>`;
  - your server URL in the [MCP Registry](https://modelcontextprotocol.io/registry/about) under that domain's namespace.

  Your server's host must be on `domain`, and so must every other host unless you sign in with OAuth. A shared suffix such as `vercel.app` is not a domain you own. The proof is checked again whenever your entry's URL, hosts or domain change.
- **`name`** and **`author`** up to 80 characters, **`description`** up to 200. `author` is the company or project that runs the server, not a person.
- **`auth`**: `{"type": "none"}`, `{"type": "token", "title": ..., "description": ...}` saying what to paste, or `{"type": "oauth"}` with an optional `client_id` and `scopes`. Never a secret.
- **`hosts`**: every host SurfSense contacts for your plugin: your server's, and for OAuth your authorization server's. The user consents to each.
- **`access`**: `free`, or `external` with an `access_note` saying what the user must buy or have.
- **`privacy_policy`**: required. The user's requests and credentials reach your server, so this is yours, not your API provider's.
- **`icon`**: SVG or PNG, square, at most 32 KB; PNG at least 64×64; SVG with no scripts, event handlers or external references. Without one, SurfSense shows your name's first letter.
- **`about`**, **`tools`** and **`added`**: what your plugin's page in SurfSense shows before anyone connects it. `about` is up to 600 characters, `tools` names every tool your server lists, and `added` is the month, like `2026-10`. The check lets them out; review asks for all three.
- **`min_app_version`**, optional: the oldest SurfSense version your plugin works with, like `2.3.0`.

The full rules are in [plugin registry](../docs/architecture/plugin-registry.md#the-entry-rules).

### What happens to your pull request

1. **CI checks the entry** against the rules above, and your icon.
2. **A maintainer reviews it once**: they connect your plugin, signing in if it needs it, and check who runs the server, what its tools do, that no description carries instructions aimed at the model, that `hosts` is complete, and that the privacy policy is real.
3. **Once merged into `dev`**, CI signs the list. It is published at `plugins.surfsense.com/plugins.json` with SurfSense's next release from `dev` to `main`, and reaches every app that allows third-party plugins with no app update.

To run the same check yourself, from `plugins/registry/check/`:

```bash
uv sync
uv run python -m registry_check static   # the entry rules and your icon
```

## 4. After it is listed

- **Changing your server needs no pull request.** Deploy when you like. A tool you add, or one whose description or annotations change, starts off in every app until the user turns it on.
- **Changing your entry** is another pull request and another review.
- **Removing a plugin** moves its entry to `removed` with a reason. Apps stop offering its tools and show the reason; users keep their connection in case it returns.
