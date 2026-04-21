# SurfSense for Obsidian

Sync your Obsidian vault to [SurfSense](https://github.com/MODSetter/SurfSense)
so your notes become searchable alongside the rest of your knowledge sources
(GitHub, Slack, Linear, Drive, web pages, etc.) from any SurfSense chat.

The plugin runs inside Obsidian itself, on desktop and mobile, so it works
the same way for SurfSense Cloud and self-hosted deployments. There is no
server-side vault mount and no Electron-only path; everything goes over HTTPS.

## What it does

- Realtime sync as you create, edit, rename, or delete notes
- Initial scan + reconciliation against the server manifest on startup,
  so vault edits made while the plugin was offline still show up
- Persistent upload queue, so a crash or offline window never loses changes
- Frontmatter, `[[wiki links]]`, `#tags`, headings, and resolved/unresolved
  links are extracted and indexed
- Each chat citation links straight back into Obsidian via the
  `obsidian://open?vault=…&file=…` deep link
- Multi-vault aware: each vault you enable the plugin in becomes its own
  connector row in SurfSense, named after the vault

## Install

### Via [BRAT](https://github.com/TfTHacker/obsidian42-brat) (current)

1. Install the BRAT community plugin.
2. Run **BRAT: Add a beta plugin for testing**.
3. Paste `MODSetter/SurfSense` and pick the latest release.
4. Enable **SurfSense** in *Settings → Community plugins*.

### Manual sideload

1. Download `main.js`, `manifest.json`, and `styles.css` from the latest
   GitHub release tagged with the plugin version (e.g. `0.1.0`, with no `v`
   prefix, matching the `version` field in `manifest.json`).
2. Copy them into `<vault>/.obsidian/plugins/surfsense/`.
3. Restart Obsidian and enable the plugin.

### Community plugin store

Submission to the official Obsidian community plugin store is in progress.
Once approved you will be able to install from *Settings → Community plugins*
inside Obsidian.

## Configure

Open **Settings → SurfSense** in Obsidian and fill in:

| Setting | Value |
| --- | --- |
| Server URL | `https://api.surfsense.com` for SurfSense Cloud, or your self-hosted URL |
| API token | Copy from the *Connectors → Obsidian* dialog in the SurfSense web app |
| Search space | Pick the search space this vault should sync into |
| Vault name | Defaults to your Obsidian vault name; rename if you have multiple vaults |
| Sync mode | *Auto* (recommended) or *Manual* |
| Exclude patterns | Glob patterns of folders/files to skip (e.g. `.trash`, `_attachments`, `templates/**`) |
| Include attachments | Off by default; enable to sync non-`.md` files |

The connector row appears automatically inside SurfSense the first time the
plugin successfully calls `/obsidian/connect`. You can manage or delete it
from *Connectors → Obsidian* in the web app.

> **Token lifetime.** The web app currently issues 24-hour JWTs. If you see
> *"token expired"* in the plugin status bar, paste a fresh token from the
> SurfSense web app. Long-lived personal access tokens are coming in a future
> release.

## Mobile

The plugin works on Obsidian for iOS and Android. Sync runs whenever the
app is in the foreground and once more on app close. Mobile OSes
aggressively suspend background apps, so mobile sync is near-realtime rather
than instant. Desktop is the source of truth for live editing.

## Privacy & safety

The SurfSense backend qualifies as server-side telemetry under Obsidian's
[Developer policies](https://github.com/obsidianmd/obsidian-developer-docs/blob/main/en/Developer%20policies.md),
so here is the full list of what the plugin sends and stores. The
canonical SurfSense privacy policy lives at
<https://surfsense.com/privacy>; this section is the plugin-specific
addendum.

**Sent on `/connect` (once per onload):**

- `vault_id`: a random UUID minted in the plugin's `data.json` on first run
- `vault_name`: the Obsidian vault folder name
- `search_space_id`: the SurfSense search space you picked

**Sent per note on `/sync`, `/rename`, `/delete`:**

- `path`, `name`, `extension`
- `content` (plain text of the note)
- `frontmatter`, `tags`, `headings`, resolved and unresolved links,
  `embeds`, `aliases`
- `content_hash` (SHA-256 of the note body), `mtime`, `ctime`

**Stored server-side per vault:**

- One connector row keyed by `vault_id` with `{vault_name, source: "plugin",
  last_connect_at}`. Nothing per-device, no plugin version, no analytics.
- One `documents` row per note (soft-deleted rather than hard-deleted so
  existing chat citations remain valid).

**What never leaves the plugin:**

- No remote code loading, no `eval`, no analytics.
- All network traffic goes to your configured **Server URL** only.
- The `Authorization: Bearer …` header is set per-request with the token
  you paste; the plugin never reads cookies or other Obsidian state.
- The plugin uses Obsidian's `requestUrl` (no `fetch`, no `node:http`,
  no `node:https`) and Web Crypto for hashing, per Obsidian's mobile guidance.

For retention, deletion, and contact details see
<https://surfsense.com/privacy>.

## Development

This plugin lives in [`surfsense_obsidian/`](.) inside the SurfSense
monorepo. To work on it locally:

```sh
cd surfsense_obsidian
npm install
npm run dev   # esbuild in watch mode → main.js
```

Symlink the folder into a test vault's `.obsidian/plugins/surfsense/`,
enable the plugin, then **Cmd+R** in Obsidian whenever `main.js` rebuilds.

Lint:

```sh
npm run lint
```

The release pipeline lives at
[`.github/workflows/release-obsidian-plugin.yml`](../.github/workflows/release-obsidian-plugin.yml)
in the repo root and is triggered by tags of the form `obsidian-v0.1.0`.
It verifies the tag matches `manifest.json`, builds the plugin, attaches
`main.js` + `manifest.json` + `styles.css` to a GitHub release tagged with
the bare version (e.g. `0.1.0`, the form BRAT and the Obsidian community
store look for), and mirrors `manifest.json` + `versions.json` to the repo
root so Obsidian's community plugin browser can discover them.

## License

[Apache-2.0](LICENSE), same as the rest of SurfSense.
