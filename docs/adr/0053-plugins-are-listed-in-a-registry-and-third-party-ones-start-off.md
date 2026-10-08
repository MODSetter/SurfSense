# ADR 0053: Plugins are listed in a registry in this repository, and every plugin not published by SurfSense starts off

- **Status:** Proposed, with the [plugins proposal](../proposals/plugins/README.md)
- **Date:** 2026-10-08
- **Source:** maintainer decision, 8 Oct 2026 (no permalink); [obsidianmd/obsidian-releases](https://github.com/obsidianmd/obsidian-releases), [Obsidian plugin security](https://obsidian.md/help/Extending+Obsidian/Plugin+security)

## Context

Remote plugins are servers their publishers run ([ADR 0051](0051-plugins-are-mcp-servers-behind-one-tool-gateway.md)). The app needs a list of them it can show with no network, a way for companies and community developers to join it, and a way to keep third-party plugins away from users who never chose them. SurfSense's users are mostly not developers.

Obsidian keeps its community plugins as one list, served from its own server with a mirror in a public repository, each entry pointing at the author's repository, whose GitHub releases hold the files. It ships with community plugins off until the user turns them on.

## Decision

- One file, `plugins/registry/plugins.json` in this repository, lists every plugin the app shows, SurfSense's own included; nothing is maintained beside it. An entry is added by pull request and reviewed once by a maintainer. A change to the server behind it needs no review.
- The list points at plugins and never holds them: a plugin's code, and later its bundle files, stay with its publisher, in its own host or repository.
- Each entry has a `kind`, `remote` now, with `bundle` reserved. Its publisher, `surfsense`, `partner` or `community`, is set by the registry, and only maintainers merge `surfsense` and `partner` entries.
- Every plugin not published by SurfSense, a custom one added by URL included, is off until the user turns third-party plugins on once.
- A tool a server adds after the user connected, or whose description or annotations change, starts off until the user turns it on.
- A maintainer delists a plugin by moving its entry to `removed` with a reason; apps stop offering its tools.
- On each merge to `main`, CI signs the list and publishes it to SurfSense's own plugin host. The app fetches it from there after consent and checks the signature against a key compiled in, so the list grows without app updates. The installer's copy is only the fallback with no network.

## Consequences

- A company or developer joins with one pull request and no build pipeline.
- Review sees the listing and the tools at the time; it does not see later deploys, which is why later tools start off.
- SurfSense needs a host for the signed list, and a signing key kept as a CI secret.

## Where the code stands

`plugins/registry/` does not exist, and the app has no catalog, Restricted mode or plugin screen. The only plugin interface is a "Plugins / Coming soon" button in [`dashboard-page.tsx`](../../surfsense_local/frontend/src/features/dashboard/dashboard-page.tsx).
