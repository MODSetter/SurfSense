# Add your plugin to SurfSense

Thanks for building something for SurfSense users. This page takes you from an MCP server to a plugin anyone can connect in the app. It is written for people and for coding agents alike; if you are an agent helping someone list a plugin, also read [the checklist for agents](#for-coding-agents).

**The short version:** a SurfSense plugin *is* an MCP server. You run the server; this folder only holds a short JSON entry pointing at it. Listing a plugin is [one form](https://github.com/MODSetter/SurfSense/issues/new?template=plugin-submit.yml): a bot checks your server and writes that entry, and a maintainer accepts it.

## What a plugin is

[MCP](https://modelcontextprotocol.io), the Model Context Protocol, is an open standard for giving AI apps tools. An **MCP server** offers tools, each with a name, a description, an input schema and a few hints about what it does. An **MCP client** connects to the server, lists those tools and calls them.

In SurfSense, the agent is the client:

```
 Settings → Plugins                         your MCP server
 ┌──────────────────┐   lists your tools    ┌──────────────────┐
 │ user clicks      │ ────────────────────► │ search_docs      │
 │ Connect          │                       │ read_page        │
 └──────────────────┘                       └──────────────────┘
          │                                          ▲
          ▼                                          │ calls a tool,
 an Agentic chat: "what do Acme's docs say           │ with approval
 about rate limits?" ────────────────────────────────┘ when needed
```

1. A user turns on **Allow third-party plugins** in **Settings → Plugins → Browse**, finds your plugin there, reads its page, and presses **Connect**, signing in if your server needs it. Third-party plugins stay hidden and unused until the user allows them.
2. In an Agentic chat, the agent sees your tools beside SurfSense's own and calls them when they help. The user can also type `@your-plugin` to point the agent at it.
3. Your server does the work and answers. SurfSense shows the result as a step in the reply.

So there is nothing SurfSense-specific to build. **If your server works in other MCP clients, it works here unchanged**, and the server you write for SurfSense works in them too. Your code never enters this repository and never runs on the user's computer.

## 1. Get your server ready

- **Remote, over Streamable HTTP, on HTTPS**, reachable from the public internet. SurfSense does not start servers from a command (`npx`, `uvx`) and does not speak the older SSE transport. Every official [MCP SDK](https://github.com/modelcontextprotocol) serves Streamable HTTP.
- **Protocol `2025-03-26` or newer**, the first with Streamable HTTP; `2025-11-25` or later is best.
- **Stateless if you can.** A server that keeps no session between requests survives restarts and scaling, and loses nothing when SurfSense reconnects.
- **Annotate every tool.** `readOnlyHint` and `destructiveHint` decide when SurfSense asks the user before a call:

  | Your tool says | SurfSense |
  |---|---|
  | `readOnlyHint: true`, or `destructiveHint: false` | Asks until the user picks **Always allow** |
  | Neither, or `destructiveHint: true` | Asks before every call: MCP assumes a tool that says nothing may destroy |

- **Describe tools for a model.** Say what the tool does and when to use it, briefly: every description reaches the model on every turn. Text that tells the model what to do, such as "always call this first", is turned away in review.
- **Keep the tool list short.** A chat offers the agent at most 24 plugin tools across all of a user's plugins, so a few well-chosen tools beat many narrow ones.
- **Pick how users sign in:**

  | `auth` | The user | Your server receives |
  |---|---|---|
  | `none` | Does nothing | No credentials |
  | `token` | Pastes a key you give them | `Authorization: Bearer <key>` |
  | `headers` | Pastes a key you give them | The key in the header your entry names, such as `x-api-key` |
  | `oauth` | Signs in on your page in their browser | `Authorization: Bearer <access token>` |

  OAuth follows [MCP's authorization spec](https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization): serve protected resource metadata, and accept Client ID Metadata Documents or dynamic client registration. SurfSense signs in as `https://plugins.surfsense.com/oauth/client.json` and comes back to `https://plugins.surfsense.com/oauth/callback`. If you only accept clients registered in advance, each user registers their own app with you and enters its client ID, and secret if you give one, in SurfSense; your entry says `auth.user_client: true`, which the bot sets for you. SurfSense itself never holds a client secret.

- **Have a privacy policy.** The user's requests and sign-in reach your server, so the policy must be yours, not your API provider's.

## 2. Submit it

The form is the only step: nothing needs checking before you send it, since the bot checks your server itself.


Fill in the **[Submit a plugin](https://github.com/MODSetter/SurfSense/issues/new?template=plugin-submit.yml)** form. It asks only what your server cannot say about itself: a name, your server's URL, who runs it, a one-line description and a short about, your privacy policy, your tools' names, and an icon you can drag straight into the form. Nothing about keys: if your server takes one, each user pastes their own when they connect.

A bot then connects to your server the way the app does and comments on the issue within a few minutes, with either:

- **what to fix**, each item named by the form's question, such as `Privacy policy URL: required` or `MCP server URL: could not be reached: timed out`. Edit the issue and the checks run again; or
- **the entry it made**, which is what users will see. How users sign in and the hosts SurfSense contacts are read from your server, not typed by you. Your tool names are checked against what your server lists without sign-in: one it lists that you left out is a problem, and one you list that it shows only after sign-in is a note. A server behind sign-in passes too: its tools are confirmed by the maintainer who connects it in review.

A maintainer then connects your plugin, reviews it, and adds the `registry: accept` label. The bot opens the pull request itself and links it to your issue. You never touch git.

Never put a key, token or password in the issue. If a reviewer needs to sign in, say so in the form, and a maintainer will arrange it with you, or reach the maintainers on [Discord](https://discord.gg/ejRNvftDp9).

### Optional: try it before you submit

Not required, but it catches what only you can judge, such as whether the agent picks the right tool from your descriptions:

- **[MCP Inspector](https://github.com/modelcontextprotocol/inspector):** `npx @modelcontextprotocol/inspector`, choose Streamable HTTP and paste your URL. It shows each tool, its description and hints, lets you call one, and walks through your sign-in.
- **SurfSense itself:** in the desktop app, **Settings → Plugins**, turn on **Allow third-party plugins**, then **Add custom plugin** with your URL and, if it needs one, a key. Ask an Agentic chat for something your tools do. A server added this way stays on that one computer, and its **⋯** menu has **Submit to the registry**, which opens the form with its name and URL filled in.

### What review looks at

A maintainer reviews your submission, and before accepting it, or once a pull request you opened is merged into `dev`, connects your plugin, signing in if it needs it, before it reaches a release. They check once:

- who runs the server, and that `author` names them, and that whoever submitted it may list it: the submitter's account, the server's domain and the publisher's own docs;
- what each tool does, and that its annotations are honest;
- that no description carries instructions aimed at the model;
- that `hosts` is complete, and the privacy policy is real and yours.

Once merged, CI signs the list. It reaches every app that allows third-party plugins with SurfSense's next release from `dev` to `main`, with no app update.


## Or open the pull request yourself

The form makes this same pull request for you. If you would rather write it, or are changing an entry already listed, here are the steps.

### Write your entry

Add one object to the `plugins` array in [`plugins.json`](plugins.json):

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

[DeepWiki's entry](plugins.json) is a real one to compare with.

| Field | What to put |
|---|---|
| `id` | Lowercase letters, digits and hyphens, starting with a letter. Unique, and never reused once listed |
| `kind` | `remote` |
| `verification` | `community`. Only a maintainer sets `verified` ([below](#verified-or-community)) |
| `name`, `author` | Up to 80 characters. `author` is the company or project that runs the server, not a person |
| `description` | Up to 200 characters: the one line on your card |
| `url` | Your server's MCP endpoint, `https`, with no credentials in it |
| `auth` | `{"type": "none"}`; `{"type": "token"}`, with an optional `title` and `description` to word the key prompt, which otherwise uses the app's own; `{"type": "headers", "headers": [{"name": "x-api-key", "label": "Acme API key"}]}` for a key in any other header, each with an optional `prefix` such as `Bearer `, `label` and `description`; or `{"type": "oauth"}`, with an optional `client_id` and `scopes`, and `"user_client": true` when your sign-in takes only apps registered in advance. Never a secret or a key |
| `transport` | Optional: `sse` if your server offers only the older HTTP+SSE transport |
| `hosts` | Every host SurfSense contacts for your plugin: your server's, and for OAuth your authorization server's. The user agrees to each before anything is sent |
| `access` | `free`, or `external` with an `access_note` (up to 200 characters) saying what the user must buy or have, such as an Acme subscription |
| `privacy_policy` | Required, `https` |
| `homepage` | Optional, `https` |
| `icon` | A file you add to [`icons/`](icons/): SVG or PNG, square, at most 32 KB, a PNG at least 64×64, an SVG with no scripts, event handlers or outside references. Without one, SurfSense shows your name's first letter |
| `about` | Up to 600 characters for your plugin's page: what it lets someone do, and when it helps |
| `tools` | Required: the name of every tool your server offers, including the ones that appear only after sign-in, as your plugin's page shows them before anyone connects |
| `added` | This month, like `2026-10` |
| `min_app_version` | Optional: the oldest SurfSense version your plugin works with, like `2.3.0` |

The check lets `about` and `added` out, but review asks for both, since they make your plugin's page.

### Check it

From [`check/`](check/), with [uv](https://docs.astral.sh/uv/) installed:

```bash
uv sync
uv run python -m registry_check static   # the entry rules and your icon
uv run python -m registry_check live     # connects to your server, as the app would
```

It prints `static check: passed`, or one line per problem naming your entry and the field, such as `plugins[1] "acme-docs": hosts: must include the url's host, mcp.acme.example`. `live` connects to your server with the app's own MCP client and fails if the app could not use it: unreachable, not MCP over Streamable HTTP, asking for sign-in when `auth` is `none`, listing a tool `tools` leaves out, or, for OAuth, no authorization server, a sign-in host missing from `hosts`, or no way for SurfSense to register. What MCP leaves optional, such as tool hints, only warns. It never signs in, so a server behind a key or an account is checked up to its sign-in. CI runs both on your pull request.

### Open the pull request

Fork the repository, branch from `dev`, and open the pull request **into `dev`**. Change only `plugins.json` and your icon. [`published/`](published/README.md) is written by CI, and a pull request that touches it fails.

Fill in the template's headings, What, Why and How to test, and include:

- **A prompt to try**, such as "What do Acme's docs say about rate limits?", and the tools it should call.
- **How a reviewer signs in**, if your plugin needs a key or an account. Never put a key or password in the pull request: say that one is needed, and a maintainer will arrange it with you, or reach the maintainers on [Discord](https://discord.gg/ejRNvftDp9).

A title in [Conventional Commits](https://www.conventionalcommits.org) form helps, such as `feat(registry): list Acme Docs`.

## Verified or Community

Every plugin starts as **Community**: the app shows a small badge and, before connecting, reminds the user who runs the server. **Verified** shows a checkmark instead, and means a maintainer is satisfied that `author` runs the server.

A maintainer decides it, on whatever convinces them that `author` runs the server: your own docs linking it, the pull request coming from your company's account, or someone they can ask. Nothing in the entry proves it, and no check decides it, so never set it yourself.

## After your plugin is listed

- **Updating your server needs no pull request.** Deploy whenever you like. A tool you add, or one whose description changes or whose annotations become less safe, is switched off in every app until the user turns it on, so tell your users when you add or reword something.
- **Changing your entry** (name, URL, hosts, sign-in) is a pull request, [opened yourself](#or-open-the-pull-request-yourself), and another review.
- **Removing your plugin** moves its entry to `removed`, as `{"id": "acme-docs", "reason": "..."}`. Apps stop offering its tools and show the reason; users keep their connection in case it returns. An id is never reused.
- **Reports.** Anyone can report a listed plugin that is broken, misleading or unsafe with the [Report a plugin](https://github.com/MODSetter/SurfSense/issues/new?template=plugin-report.yml) form. A maintainer may then remove it, with the reason users see.

## Questions

- **Can I charge for my plugin?** Yes: bill on your own service, set `access: external` with an `access_note`, and sign users in with `token` or `oauth`. The SurfSense license is only for SurfSense's own plugins, and your server never sees it.
- **Can my plugin run on the user's computer?** Not yet. Local plugins are planned as [bundles](../../../docs/proposals/plugins/bundles/README.md).
- **Where are SurfSense's own plugins?** In [`../remote/`](../), run by SurfSense's plugin host and listed in the app itself, not here ([plugin host](../../../docs/architecture/plugin-host.md#adding-a-plugin)). Only maintainers change the paid ones, in `remote/proprietary/`.
- **How does the app handle all this?** [Plugins](../../../docs/architecture/plugins.md) and the [plugin registry](../../../docs/architecture/plugin-registry.md) describe it in full.

## For coding agents

If you are helping someone list a plugin:

1. Confirm the server is remote, Streamable HTTP, on HTTPS. If it only runs from a command or over SSE, stop and say so; it cannot be listed yet.
2. Prefer the [submission form](https://github.com/MODSetter/SurfSense/issues/new?template=plugin-submit.yml). From a terminal, open it with `gh issue create --repo MODSetter/SurfSense --title "[plugin submission] <name>" --body-file <file>`. The body is the form's answers, each under `### <question>` as the form names it in [`plugin-submit.yml`](../../../.github/ISSUE_TEMPLATE/plugin-submit.yml), `_No response_` for a blank one, and the confirmation as a ticked `- [X]` line under `### Before you send`. The title prefix is what marks it, since a label you pass is dropped unless you have write access.
3. Never invent tool names. Read every one from the server, signed in where it needs it (the MCP Inspector lists them), and put one per line under **Tool names**, including the ones that appear only after sign-in.
4. Put no key, token, password or client secret anywhere: not in the issue, a pull request or a commit message.
5. Read the bot's comment and fix each item by editing the issue body. Do not open a second issue.
6. Opening the pull request yourself instead: touch only `plugins.json` and `icons/<file>`, with `verification: "community"`, never `published/`, `check/` or another entry; run `uv run python -m registry_check static` and `live` in `check/` and fix every problem; open it into `dev` with What, Why and How to test, and a prompt to try.
