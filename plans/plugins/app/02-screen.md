# App — screen

> Owns: `surfsense_local/frontend/src/features/plugins/`.
> Calls: [`01-api.md`](01-api.md).

## Goal

Maya installs a plugin from a list, then uses it where she already works. An entry that returns documents is a sidebar action next to New chat, not a job she runs from an admin page.

## Work

- Installed entries are `SidebarNavAction` rows on the existing left sidebar, below Chats. The label is the entry title. Click opens a dialog built from the app's own inputs: text, number, checkbox. Submit starts the run in the current workspace. The dialog shows running, then succeeded, failed, or cancelled, with the error and the log tail, and a cancel button.
- The dialog does not draw what the run produced. A plugin writes through the app's own API, so a note it added appears in the sources list the way any other note does, while the run is still going. The dialog shows status, error, and the log tail.
- Settings holds the catalog, not the run. Each row: name, author, version, the `hosts` list or the word "none", `free` or `paid`, and installed version when present.
- A `paid` row that is locked explains that a SurfSense license is required and links to the existing license settings. The install button is disabled.
- Install calls `POST /plugins/{id}/install`. Egress 403 shows the same Settings → Network explanation the other destinations use, naming `plugin_install`.
- Refresh calls `POST /plugins/catalog/refresh`. The same 403 names `plugin_catalog`. The list is already on screen from the bundled catalog before either destination is enabled.
- An installed plugin with a secret shows a field per name in Settings. Saving calls `PUT`. The field does not redisplay the value. The sidebar action stays disabled until every declared secret is set.
- Uninstall asks once, then `DELETE`. The sidebar row disappears. Notes already created stay in Sources.
- Freshness for the dialog is the existing SSE invalidate on `plugin.run.updated`, with a refetch interval while `running` as the fallback.

Follow the frontend workflow. The dialog and the settings list use the components the app already has. A plugin does not ship a layout.

## Acceptance

- With both egress destinations off, the screen lists the bundled catalog and no request has left the machine.
- Install of `example` from a local fixture server adds a sidebar row. Running it with text `hi` from that row reaches `succeeded`, and Sources contains a note with content `hi`.
- A `paid` plugin with no license on disk cannot be installed from the screen.
- A failed run shows the error and the log tail.

## Needs from

[`01-api.md`](01-api.md). The screen can be built against those paths before the handlers exist.
