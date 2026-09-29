# App — screen

> Owns: `surfsense_local/frontend/src/features/plugins/`.
> Calls: [`01-api.md`](01-api.md).

## Goal

Maya installs a plugin from a list, then uses it where she already works. An entry that returns documents is a sidebar action next to New chat, not a job she runs from an admin page. The list shows only what her computer can run.

## Work

- Installed entries are `SidebarNavAction` rows on the existing left sidebar, below Chats. The label is the entry title. Click opens a dialog built from the entry's declared inputs with the app's own components, one per kind: text field, number field, checkbox, each labelled with its `title`. Submit starts the run in the current workspace.
- The dialog shows waiting while the run is `queued`, then running, then how it ended, with the log tail and a cancel button. A failed run says why in words: the exit code, "took longer than its limit of N minutes" with the entry's timeout, or "SurfSense was closed during this run". The log tail sits right below, since that is where a plugin explains itself.
- The dialog does not draw what the run produced. A plugin writes through the app's own API, so a note it added appears in the sources list the way any other note does, while the run is still going.
- Settings holds the catalog, not the run. It shows what `GET /plugins` returns and never a plugin this computer cannot run. Each row: name, `description`, author, version, the `hosts` list or the word "none", `free` or `paid`, download size, and installed version when present.
- Each row has one button that fits its state: Install, Update when `update` is set, and Uninstall once installed. A row with `needs_newer_app` says "Needs a newer SurfSense" with Install disabled. A `paid` row that is locked explains that a SurfSense license is required and links to the existing license settings, with Install disabled. An installed row with `withdrawn` shows "Withdrawn:" and the reason, and its sidebar actions are disabled.
- The egress prompt (`features/egress/egress-prompt.tsx`) reads one `destination` and `host` today. It learns to read `hosts` and to list several, with one Allow that grants each, so `request()` in `lib/api.ts` still retries once. A refusal with one host looks as it does now.
- Install, Update and Refresh need `ghcr.io` and `pkg-containers.githubusercontent.com`. Their 403 opens that prompt once for both hosts, naming the errands, and retries once on Allow. The list is already on screen from the bundled catalog before either host is allowed.
- The first run of a plugin that declares `hosts` gets a 403 listing every host not yet allowed, and the same prompt asks for all of them at once.
- Settings → Network shows a plugin's hosts with the plugin's name beside them, so a grant made for a plugin can be seen and revoked there like any other.
- An installed plugin with secrets shows a field per secret in Settings, labelled with its `title`, with its `description` as help text. Saving calls `PUT`. The field shows only whether it is set and never redisplays the value. While a declared secret has no value, each of the plugin's sidebar actions is replaced by a "Set up" action that opens those fields.
- Uninstall asks once, then `DELETE`. A run in progress stops. The sidebar row disappears. Notes already created stay in Sources.
- Freshness: poll the run while it is `queued` or `running`, as Sources and Studio poll today. The frontend does not subscribe to workspace events yet ([ADR 0009](../../../adr/0009-freshness-by-invalidation.md)); once it does, `plugin.run.updated` replaces the poll.

Follow the frontend workflow. The dialog and the settings list use the components the app already has. A plugin does not ship a layout.

The app's own words on these screens are interface strings and follow the translate skill. What a plugin declares, its name, description and titles, is shown as the author wrote it and never translated.

## Acceptance

- With both hosts off, the screen lists the bundled catalog and no request has left the machine.
- Install of `example` from a local fixture server adds a sidebar row. Running it with text `hi` from that row reaches `succeeded`, and Sources contains a note with content `hi`.
- A fixture plugin built only for Windows is not listed on macOS or Linux.
- The first run of a fixture plugin with two hosts shows one prompt naming both, and after Allow both appear in Settings → Network beside the plugin's name.
- A run past its timeout shows the timeout reason and the log tail.
- A fixture plugin declaring one input of every kind gets a matching form with no plugin-specific code.
- A plugin with a secret not yet set shows "Set up" in the sidebar, and runs once it is saved.
- A run that exits with a reason on stderr shows that reason in the log tail under the failure.
- A `paid` plugin with no license on disk cannot be installed from the screen.

## Needs from

[`01-api.md`](01-api.md). The screen can be built against those paths before the handlers exist.
