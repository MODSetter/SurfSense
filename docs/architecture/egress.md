# Egress

Nothing is meant to leave the machine until the user allows where it goes. Before a call reaches the network, the backend names its destination and calls `egress.require()`, which refuses with `403 egress_disabled` unless the user has allowed that destination, so a refused call never opens a connection. A destination is a host, off by default, and loopback is not egress; the calls that escape the check are listed under Known gaps. The renderer turns a refusal of something the user just did into a consent dialog, and never asks on a background read.

**Code:** [`surfsense_local/backend/modules/egress/`](../../surfsense_local/backend/modules/egress/), [`surfsense_local/frontend/src/features/egress/`](../../surfsense_local/frontend/src/features/egress/), [`surfsense_local/frontend/src/lib/api.ts`](../../surfsense_local/frontend/src/lib/api.ts)
**Decisions:** [ADR 0017](../adr/0017-egress-off-by-default.md)

## Destinations

| Destination | Host | Covers |
|---|---|---|
| `host:huggingface.co` | `huggingface.co` | searching Hugging Face and reading a repo on the model screen, downloading a GGUF for the llama.cpp runtime, and downloading weights for the bundled sd-server |
| `host:plugins.surfsense.com` | `plugins.surfsense.com` | fetching the third-party plugin registry and its icons ([plugin registry](plugin-registry.md)), and SurfSense's own plugins on the [plugin host](plugin-host.md) |
| `host:<hostname>` | that host | everything sent to one remote OpenAI-compatible connection: probes, model lists, tests, chat, image generation; or to one plugin's server: listing its tools and calling them; or to its authorization server: signing in and refreshing |
| `host:downloadarchive.documentfoundation.org` | `downloadarchive.documentfoundation.org` | downloading the Office pack, The Document Foundation's LibreOffice build, when the user turns Office support on ([office pack](office-pack.md)) |

There is one row per host by construction: the key is the hostname, so a destination cannot exist twice under two names, and the user is asked about the host rather than about each errand sent to it. `host:huggingface.co` and `host:plugins.surfsense.com` are built in (`BUILT_IN` in `modules/egress/service.py`), so they are listed before anything names them. Its dialog names every errand, search first because it is the widest: searching sends what the user types, as they type it; downloading sends the name of the model they chose; both send their IP address, and neither sends chats or documents.

State is one table, `egress_destinations`: a row per destination with `enabled`, false by default, and `last_call_at`, which every allowed call stamps. `GET /egress` lists the built-in destinations, one `host:` row per non-loopback host among the stored connections, off when never allowed, and every other `host:` row, such as a host an image endpoint named. `PUT /egress` turns the destinations it lists on or off, all or none: every one is checked before any is written, the request's one transaction commits them together, and anything that is not a `host:` name or built-in destination answers 422 with nothing changed. Settings › Network sends a list of one; a consent question sends every host it named ([`modules/egress/router.py`](../../surfsense_local/backend/modules/egress/router.py)). Deleting the last connection to a host deletes that host's row (`forget_if_unused()`), so a later connection there is asked about again; a host another connection still uses keeps its grant, and a built-in destination is never dropped.

`host_destination()` returns no destination for `localhost` or a loopback address, so a model server on the same machine needs no consent and has no row. A server elsewhere on the LAN is a destination like any other.

A plugin's hosts are asked about before it connects: the refusal carries `hosts`, every host still to allow, and `purpose: "plugin"`, which the prompt words its question by, saying the host gets what a tool is sent rather than every chat. A refused plugin host with no row is recorded off, so Settings › Network lists it ([plugins](plugins.md)). An OAuth plugin's authorization server is asked about the same way, once discovery names it and before any request reaches it.

Fetching the registry is refused with `purpose: "plugin_registry"`, and its prompt says the list is fetched from `plugins.surfsense.com`, sending the IP address and nothing else, and that SurfSense's own plugins run on the same host, so the one answer covers both ([`features/egress/api.ts`](../../surfsense_local/frontend/src/features/egress/api.ts)).

## Where the check runs

`egress.require(session, destination)` raises `EgressDeniedError` when the row is missing or off, and `api/main.py` turns that into a `403` whose `detail` carries `code: "egress_disabled"`, the `destination`, its `host`, `hosts` (every host still to allow, `host` first), `purpose` when the host alone does not say what the call is for (`plugin` or `plugin_registry`), and a message. The check sits in front of each call site, in whichever process makes the call:

| Call | Where | Destination |
|---|---|---|
| Probing a connection when it is created or updated, listing its models, running its chat and image tests | `modules/llm/connections/router.py` | `host:` |
| Choosing a remote model | `modules/llm/selection.py`, through `allowed_connection()` | `host:` |
| Checking a connection's rows against its live listing | `GET /llm/catalog/remote/connections/{id}` in `modules/llm/catalog/remote/router.py`, through `allowed_connection()` | `host:` |
| Chat and Studio generation, text or image, through a remote connection | `_connection()` in `modules/llm/resolution.py` | `host:` |
| The agent's turns, which opencode sends to SurfSense's model endpoint and SurfSense forwards to a remote connection | `address_selected_model()` in `modules/agent/model_endpoint/model_address.py`, through `allowed_connection()`; a refusal answers opencode with a `403` whose message names the host | `host:` |
| Downloading an image an endpoint returned as a URL, whose host the endpoint chose | `refused_named_host()`, called before the download through the image provider's `allow_url_host`: by `POST /llm/connections/{id}/image-test` (a `403`) and by `resolution.py` for Studio (the job fails with the refusal, not retried, since the image was already billed). A refused host with no row is recorded off, so it is listed | `host:` |
| Adding a plugin by URL, before its server is contacted | `POST /plugins/custom` in `modules/plugins/routes.py`, through `refused_hosts()` | `host:` |
| Connecting a plugin from the registry, for every host its entry lists | `POST /plugins/registry/{id}` in `modules/plugins/lists/registry/routes.py`, through `refused_hosts()` | `host:` |
| Fetching the registry, its signature and its icons | `GET /plugins/registry` and `POST /plugins/registry/{id}`, through `registry_refusal()` in `modules/plugins/lists/registry/registry_consent.py`; never while third-party plugins are off, and not in an unpackaged build, which reads the checkout | `host:plugins.surfsense.com` |
| An OAuth sign-in's discovery, registration and code exchange | the connect routes, through `refused_hosts()` for the authorization server's host, then every request through `consented_client()` in `modules/plugins/remote/sign_in/oauth/consented_client.py`, which refuses a host not allowed before it leaves | `host:` |
| Refreshing an OAuth plugin's token | `refresh_sign_in()` in `modules/plugins/remote/sign_in/oauth/token_refresh.py`, through `require()`; a host turned off leaves the sign-in as it was | `host:` |
| Offering a plugin's tools | `list_tools()` in `modules/plugins/gateway/listing.py` offers nothing from a plugin whose hosts are not all allowed | `host:` |
| The agent's calls to a plugin, which opencode makes itself | each connection through the plugin proxy, `may_connect()` in `modules/agent/plugin_proxy/allowed_hosts.py`: only a ready plugin's host, recorded through `require()` ([agent](agent.md#network)) | `host:` |
| Downloading a GGUF | `POST /llm/installs` in `modules/llm/catalog/local/install_jobs/router.py`, checked before the job starts | `host:huggingface.co` |
| Hugging Face search and repo reads | `GET /llm/catalog/local/search` and `GET /llm/catalog/local/search/{repo}` in `modules/llm/catalog/local/router.py` | `host:huggingface.co` |
| Downloading sd-server weights | `POST /llm/installs`, the same job as chat models | `host:huggingface.co` |
| Downloading the Office pack | `POST /runtime-packs/office/install` in `modules/runtime_packs/office/router.py`, checked before the install starts | `host:downloadarchive.documentfoundation.org` |

The GGUF download runs inside the API (`modules/llm/providers/llamacpp/download.py`) instead of through llama-server's own fetch. llama-server is a second process the app does not proxy, so an in-process fetch is the only place the check can hold.

## Not egress

- llama-server and sd-server, which the backend reaches on `127.0.0.1`.
- The worker's `POST /internal/events` to the API, and Electron polling the API: `/health` at startup, the image runtime every few seconds.
- App updates. electron-updater talks to GitHub from the Electron main process, out of reach of `egress.require()`, so it is gated by the `automatic` preference in `updates.json` and by consent in the renderer instead ([updates](updates.md)). Settings › Network shows it as the App updates row, host `github.com`.
- Links. The main process refuses new windows and `https:` navigations inside the app, and hands a URL on `surfsense.com` or `www.surfsense.com`, under `github.com/MODSetter/SurfSense`, the project's Discord invite, an OpenRouter page shaped `/<author>/<model>` (where OpenRouter names a speech model's voices), or a plugin's OAuth authorization page, recognised on any host by its query (an S256 PKCE code request with SurfSense's `state` and one of its two callbacks), to `shell.openExternal` (`electron/src/main/external-url.ts`); that request is the browser's. Two more reach the browser, each by its own bridge call and never by `window.open` or navigation: a link from content, a chat reply, a Studio document or a tool's result, that the user confirmed in the app's link popup ([`external-link-dialog.tsx`](../../surfsense_local/frontend/src/features/external-links/external-link-dialog.tsx)), which names its host, shows the whole address, and warns when the address carries more than 100 characters after its path, room for the conversation; any `https` page, never another scheme or an address with a user name or password (`confirmedExternalUrl`). And a listed plugin's homepage or privacy policy, opened on a click with no popup: the page names the plugin and the page, and the main process opens the address the registry lists for it, read from the app's API, never one the page passes (`electron/src/main/plugin-page-url.ts`). Report issue opens one such link, a GitHub bug form with the user's description in it; its session log goes to the clipboard, never into the link ([issue reports](issue-reports.md)).
- Docling. Packaged Python sidecars run with `HF_HUB_OFFLINE=1` (`electron/src/main/sidecars/python.ts`) and parse with the bundled parser pack ([packaging](packaging.md)). [`test_parsing.py`](../../surfsense_local/backend/tests/integration/worker/test_parsing.py) converts a scanned PDF and images from the parser pack with every outbound connection refused and an empty Hugging Face cache; it runs from source and skips where the pack is not staged.
- Spellchecking. Chromium fetches a Hunspell dictionary from Google's CDN (`redirector.gvt1.com/edgedl/chrome/dict/`) for each language in a session's spellchecker list, when the session is created. Measured on Electron 44.2.0 on Linux, `webPreferences.spellcheck: false` and `setSpellCheckerEnabled(false)` do not stop it, and `webRequest` never sees it. The main process empties the list on `session-created`, before the app is ready ([`spellcheck.ts`](../../surfsense_local/electron/src/main/spellcheck.ts)), and no request is made after that. So Windows and Linux have no spellchecking. macOS uses the OS spellchecker, downloads nothing and ignores the call, so it keeps working there. Not measured on Windows, which runs the same code.
- Licenses. The app verifies license files offline and never contacts Keygen ([license](license/app.md)); `keygen` is refused by `PUT /egress` as unknown.

## Asking for consent

`request()` in `lib/api.ts` catches `egress_disabled` on a non-GET request and hands it to `EgressPrompt`, which shows that destination's copy. A refusal naming several hosts in `hosts` is one question: the copy names the others, and Allow enables every one of them in one `PUT /egress`, so a failed Allow enables none, before the request is retried once; Cancel rethrows the refusal. A Claude plan's refusal, `purpose: "claude_plan"`, says what each of its two hosts gets ([`features/egress/api.ts`](../../surfsense_local/frontend/src/features/egress/api.ts)). The method stands in for "the user just did something", a `ponytail:` simplification, because reads also run unattended at boot and must never raise a dialog.

A refused GET therefore surfaces as an error without a prompt.

One question covers one user action: it names every host that action may reach, including a host that background work started by it reaches, which no dialog could ask about later, and leaves a host only a later action reaches to that action's own question ([ADR 0060](../adr/0060-one-consent-question-per-user-action.md)). Only hosts SurfSense names are asked about; a host a program it runs tries on its own is refused.

Studio resolves its model in the worker, where no dialog can reach the user, so a job whose connection host is off fails with the refusal as its reason. Choosing a remote model already requires its host, so this happens only after the user turns the host off again.

`askEgress()` in `features/egress/ask-egress.ts` raises the same dialog without a refused request, in two places:

- **Updates**, because their call is not the backend's to refuse: Check now asks while `automatic` is off, and Allow turns it on.
- **Model search**, because the answer is wanted before the request: focusing the search box asks while `host:huggingface.co` is off, once per visit to the screen, so a refused search is not the first news that search is off. After Cancel, search says it needs `huggingface.co`, while curated and installed models keep working.

Refused requests and `askEgress()` queue for one prompt, an app dialog (`AppDialogs` in `components/ui/app-dialog-slot.tsx`): it renders inside the innermost open dialog, so the question opens as that dialog's nested dialog and the dialog steps back behind it, or on its own when none is open. Questions still waiting when no prompt is mounted are answered no.

Settings › Network lists the App updates row and every destination with its host and last call. Unticking one refuses the next call outright.

## Known gaps

- Document scripts, Studio's Office formats and the agent's, run model-written code in the script runner's process, and that code can open connections of its own ([studio](studio.md#script-documents)).
- The Office pack's download is allowed by its host, `downloadarchive.documentfoundation.org`, which redirects to one of TDF's mirrors; the mirror sees the user's IP address and is not asked about ([office pack](office-pack.md)).
