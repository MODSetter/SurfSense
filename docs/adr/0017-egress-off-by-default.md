# ADR 0017: Every outbound destination is off until the user allows it

- **Status:** Accepted; the list of destinations is superseded by [ADR 0027](0027-egress-consent-per-host.md)
- **Date:** 2026-09-08
- **Source:** [Pivot plan L84](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/00d-pivot-plan.md#L84), [Pivot plan L235](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/00d-pivot-plan.md#L235)

## Context

The app is airgapped by design, yet some features need the network: downloading and searching models on Hugging Face, pulling image models, calling a remote model endpoint, checking for updates. Each of those sends something off the machine, and a remote model connection carries the user's prompts and documents. Egress as built is in [egress](../architecture/egress.md).

## Decision

- One `egress_destinations` row per destination, `enabled` false by default, with the time of its last call ([`modules/egress/`](../../surfsense_local/backend/modules/egress/)).
- Every outbound call goes through `egress.require()`. A destination with no row, or a disabled one, raises `EgressDeniedError`, which the API answers with `403` and the code `egress_disabled`.
- The frontend turns that into a just-in-time consent dialog on a user action, retries the request once on Allow, and never prompts for a background read ([`features/egress/egress-prompt.tsx`](../../surfsense_local/frontend/src/features/egress/egress-prompt.tsx)).
- Loopback is not egress. `host_destination()` returns no destination for `localhost` or a loopback address.
- The destinations today are `model_download` and `model_search` (both `huggingface.co`), `image_model_pull` (`huggingface.co`), and `host:<hostname>` for each remote connection ([`modules/egress/service.py`](../../surfsense_local/backend/modules/egress/service.py)).
- App updates are a separate Electron pref in `updates.json`, off by default ([`electron/src/main/updater.ts`](../../surfsense_local/electron/src/main/updater.ts)). Settings › Network lists every destination plus that pref (recorded 14 Sep 2026).
- There is no Keygen destination, because license files are verified offline ([ADR 0019](0019-offline-licenses.md)) (recorded 12 Sep 2026; the 8 Sep plan listed Keygen activation as a destination).
- Plugins will add a consent for each host a plugin declares in `plugin.json`, asked before its first run ([ADR 0025](0025-scraper-client-as-paid-plugin.md), [plugins proposal](../proposals/plugins/README.md)).

## Consequences

- With every destination off, the app still works with what is on the machine: installed models, the bundled embedder, and loopback endpoints such as LM Studio.
- `request()` in [`frontend/src/lib/api.ts`](../../surfsense_local/frontend/src/lib/api.ts) uses the HTTP method as the stand-in for a user action: only a non-GET request raises the dialog, and its `ponytail:` says so.
- Consent is per destination, not per call. An allowed destination stays allowed until the user turns it off in Settings.
- A plugin's own traffic is not intercepted, so a plugin consent covers the hosts it declares, not every call it makes.

## Where the code stands

- `_download_image()` in [`providers/openai_compatible/image.py`](../../surfsense_local/backend/modules/llm/providers/openai_compatible/image.py) fetches the URL a remote image model returns, which need not be the connection host the user allowed. It checks the scheme, rejects embedded credentials, bounds the body and withholds the endpoint's bearer token, but takes no egress decision.
- Electron's Chromium spellchecker is not configured in [`electron/src/main/index.ts`](../../surfsense_local/electron/src/main/index.ts), and Electron's type definitions say it downloads Hunspell dictionaries from the Chromium CDN by default. Whether it does so here, on Windows and Linux, has not been checked at runtime.
- Adding a `.gguf` from disk has no screen, so offline the installed models are the ones downloaded earlier or copied into the models directory by hand ([catalog](../architecture/local-models/catalog.md)).
