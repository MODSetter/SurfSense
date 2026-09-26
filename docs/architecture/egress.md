# Egress

Nothing is meant to leave the machine until the user allows where it goes. Before a call reaches the network, the backend names its destination and calls `egress.require()`, which refuses with `403 egress_disabled` unless the user has allowed that destination, so a refused call never opens a connection. A destination is a host, off by default, and loopback is not egress; the calls that escape the check are listed under Known gaps. The renderer turns a refusal of something the user just did into a consent dialog, and never asks on a background read.

**Code:** [`surfsense_local/backend/modules/egress/`](../../surfsense_local/backend/modules/egress/), [`surfsense_local/frontend/src/features/egress/`](../../surfsense_local/frontend/src/features/egress/), [`surfsense_local/frontend/src/lib/api.ts`](../../surfsense_local/frontend/src/lib/api.ts)
**Decisions:** [ADR 0017](../adr/0017-egress-off-by-default.md)

## Destinations

| Destination | Host | Covers |
|---|---|---|
| `host:huggingface.co` | `huggingface.co` | searching Hugging Face and reading a repo on the model screen, downloading a GGUF for the llama.cpp runtime, and downloading weights for the bundled sd-server |
| `host:<hostname>` | that host | everything sent to one remote OpenAI-compatible connection: probes, model lists, tests, chat, image generation |

There is one row per host by construction: the key is the hostname, so a destination cannot exist twice under two names, and the user is asked about the host rather than about each errand sent to it. `host:huggingface.co` is built in (`BUILT_IN` in `modules/egress/service.py`), so it is listed before any connection names it. Its dialog names every errand, search first because it is the widest: searching sends what the user types, as they type it; downloading sends the name of the model they chose; both send their IP address, and neither sends chats or documents.

State is one table, `egress_destinations`: a row per destination with `enabled`, false by default, and `last_call_at`, which every allowed call stamps. `GET /egress` lists `host:huggingface.co` and one `host:` row per non-loopback host among the stored connections, off when never allowed. `PUT /egress/{destination}` turns one on or off, and answers 422 for anything that is not a `host:` name.

`host_destination()` returns no destination for `localhost` or a loopback address, so a model server on the same machine needs no consent and has no row. A server elsewhere on the LAN is a destination like any other.

The plugins proposal adds a consent for each host a plugin declares, asked before the plugin's first run ([plugins](../proposals/plugins/README.md)).

## Where the check runs

`egress.require(session, destination)` raises `EgressDeniedError` when the row is missing or off, and `api/main.py` turns that into a `403` whose `detail` carries `code: "egress_disabled"`, the `destination`, its `host` and a message. The check sits in front of each call site, in whichever process makes the call:

| Call | Where | Destination |
|---|---|---|
| Probing a connection when it is created or updated, listing its models, running its chat and image tests | `modules/llm/connections/router.py` | `host:` |
| Choosing a remote model | `modules/llm/selection.py`, through `allowed_connection()` | `host:` |
| Checking a connection's rows against its live listing | `GET /llm/catalog/remote/connections/{id}` in `modules/llm/catalog/remote/router.py`, through `allowed_connection()` | `host:` |
| Chat and Studio generation, text or image, through a remote connection | `_connection()` in `modules/llm/resolution.py` | `host:` |
| Downloading a GGUF | `POST /llm/install` in `modules/llm/catalog/local/router.py` | `host:huggingface.co` |
| Hugging Face search and repo reads | `GET /llm/catalog/local/search` and `GET /llm/catalog/local/search/{repo}` in the same file | `host:huggingface.co` |
| Downloading sd-server weights | `POST /llm/install`, the same stream as chat models | `host:huggingface.co` |

The GGUF download runs inside the API (`modules/llm/providers/llamacpp/download.py`) instead of through llama-server's own fetch. llama-server is a second process the app does not proxy, so an in-process fetch is the only place the check can hold.

## Not egress

- llama-server and sd-server, which the backend reaches on `127.0.0.1`.
- The worker's `POST /internal/events` to the API, and Electron polling the API: `/health` at startup, the image runtime every few seconds.
- App updates. electron-updater talks to GitHub from the Electron main process, out of reach of `egress.require()`, so it is gated by the `automatic` preference in `updates.json` and by consent in the renderer instead ([updates](updates.md)). Settings › Network shows it as the App updates row, host `github.com`.
- Links. The main process refuses new windows and `https:` navigations inside the app, and hands a URL on `surfsense.com` or `www.surfsense.com`, under `github.com/MODSetter/SurfSense`, or the project's Discord invite to `shell.openExternal` (`electron/src/main/external-url.ts`); that request is the browser's. Report issue opens one such link, a GitHub bug form with the user's description in it; its session log goes to the clipboard, never into the link ([issue reports](issue-reports.md)).
- Docling. Packaged Python sidecars run with `HF_HUB_OFFLINE=1` (`electron/src/main/sidecars/python.ts`) and parse with the bundled parser pack ([packaging](packaging.md)). No test yet ingests a PDF with networking off, so this rests on that configuration rather than on a check.
- Licenses. The app verifies license files offline and never contacts Keygen ([license](license/app.md)); `PUT /egress/keygen` is refused as unknown.

## Asking for consent

`request()` in `lib/api.ts` catches `egress_disabled` on a non-GET request and hands it to `EgressPrompt`, which shows that destination's copy. Allow enables the destination and the request is retried once; Cancel rethrows the refusal. The method stands in for "the user just did something", a `ponytail:` simplification, because reads also run unattended at boot and must never raise a dialog.

A refused GET therefore surfaces as an error without a prompt.

Studio resolves its model in the worker, where no dialog can reach the user, so a job whose connection host is off fails with the refusal as its reason. Choosing a remote model already requires its host, so this happens only after the user turns the host off again.

`askEgress()` in `features/egress/ask-egress.ts` raises the same dialog without a refused request, in two places:

- **Updates**, because their call is not the backend's to refuse: Check now asks while `automatic` is off, and Allow turns it on.
- **Model search**, because the answer is wanted before the request: focusing the search box asks while `host:huggingface.co` is off, once per visit to the screen, so a refused search is not the first news that search is off. After Cancel, search says it needs `huggingface.co`, while curated and installed models keep working.

Refused requests and `askEgress()` queue for one prompt, an app dialog (`AppDialogs` in `components/ui/app-dialog-slot.tsx`): it renders inside the innermost open dialog, so the question opens as that dialog's nested dialog and the dialog steps back behind it, or on its own when none is open. Questions still waiting when no prompt is mounted are answered no.

Settings › Network lists the App updates row and every destination with its host and last call. Unticking one refuses the next call outright.

## Known gaps

- `_download_image()` in `modules/llm/providers/openai_compatible/image.py` fetches an image URL the remote model returns with no egress decision; it checks the scheme, rejects embedded credentials, bounds the body and withholds the endpoint's bearer token.
- Electron's Chromium spellchecker is not configured in `electron/src/main/index.ts`. Electron's type definitions say it downloads Hunspell dictionaries from the Chromium CDN by default, and `spellcheck` is on unless turned off, so on Windows and Linux it likely makes that call; nobody has checked at runtime.
- The Office Studio formats run model-written code in the worker, and that code can open connections of its own ([studio](studio.md)).
- Deleting a connection leaves its host's grant in `egress_destinations`, hidden from Settings › Network, so a later connection to the same host is allowed without asking.
- Grants stored under the earlier destination names, `model_download`, `model_search` and `image_model_pull`, are not carried over to `host:huggingface.co`. Nothing reads them any more, so someone who had allowed model downloads is asked again, and the old rows stay in the table; revision 0012 still turns an Ollama-era `ollama_pull` grant into `model_download`.
