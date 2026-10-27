# ADR 0075: What differs in the Docker image is gated by one build flag, the Electron bridge, or the API's own setting

- **Status:** Accepted
- **Date:** 2026-10-28
- **Source:** [Docker proposal, The frontend without Electron](../proposals/docker/README.md#the-frontend-without-electron)

## Context

The desktop app and the image share one frontend and one backend ([ADR 0072](0072-the-desktop-and-the-container-are-two-entries-over-one-core.md)). Some behaviour differs between them, and the first Docker branches each compared `import.meta.env.VITE_SURFSENSE_RUNTIME` to `"docker"` where they stood, with nothing to catch a misspelt value and no rule for when a branch belongs to Docker rather than to "no Electron". The Claude dialog learned the same fact from the API at run time instead.

## Decision

- **What only Electron can do is gated on its bridge,** `window.surfsense?.…`, with the browser's fallback where one exists. A browser running `pnpm dev` lacks it too, so it is never a Docker check: updates, the session log, the privacy choices, the OS theme and locale, opening and revealing files.
- **What the Docker build does differently reads one flag,** `IN_CONTAINER` in [`app/in-container.ts`](../../surfsense_local/frontend/src/app/in-container.ts), fixed when the image's frontend is built. `VITE_SURFSENSE_RUNTIME` is typed `"docker" | undefined`, so a misspelt comparison fails typecheck. Each feature reads it through a predicate named for the behaviour (`downloadsOriginals()`, `needsPastedCallback()`), kept in that feature's folder.
- **The backend has one check,** `get_settings().in_container()`, from `SURFSENSE_LOCAL_RUNTIME=docker`, which the headless entry sets. The API reports to the frontend only what the running container alone knows, such as its domain; never whether it is Docker, which the build already knows.
- **A browser's rule is gated on the browser,** not on Docker: the microphone outside a secure context is `window.isSecureContext`.
- **The image keeps no usage statistics.** Nothing in it reports them, so the API neither counts activity nor serves `/usage-statistics` there ([`kept.py`](../../surfsense_local/backend/modules/usage_statistics/kept.py)).
- A Docker-only feature is a feature folder of its own, as `features/access/` is. A small Docker branch inside a shared feature stays beside the desktop code.
- Rejected: a `docker/` or `platform/` folder of overrides, which splits each feature by where it runs; a runtime flag fetched from the API, which the build already fixes and which would keep both builds' branches in each bundle.

## Consequences

- Each build drops the other's branches, and a new Docker branch is one predicate in its feature reading `IN_CONTAINER`.
- Frontend branches are tested with the `docker` tag, and backend ones by setting `runtime` to `"docker"`, plus `pytest.mark.image` where the image itself matters ([`surfsense_local/AGENTS.md`](../../surfsense_local/AGENTS.md)).

## Where the code stands

Built: the flag, the predicates, the usage-statistics gate, the ChatGPT paste-back route answering only in the container, and the secure-context microphone message.
