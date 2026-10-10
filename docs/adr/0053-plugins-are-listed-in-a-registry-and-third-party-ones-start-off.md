# ADR 0053: SurfSense's plugins are listed in the app, every other publisher's in a registry in this repository, and those start off

- **Status:** Proposed, with the [plugins proposal](../proposals/plugins/README.md)
- **Date:** 2026-10-08
- **Source:** maintainer decision, 8 Oct 2026 (no permalink); [obsidianmd/obsidian-releases](https://github.com/obsidianmd/obsidian-releases), [Obsidian plugin security](https://obsidian.md/help/Extending+Obsidian/Plugin+security)

## Context

Remote plugins are servers their publishers run ([ADR 0051](0051-plugins-are-mcp-servers-behind-one-tool-gateway.md)). The app needs plugins it can show with no network, while egress is off by default ([ADR 0017](0017-egress-off-by-default.md)), a way for companies and community developers to join without an app release, and a way to keep third-party plugins away from users who never chose them. SurfSense's users are mostly not developers.

Obsidian keeps its community plugins as one list, served from its own server with a mirror in a public repository, each entry pointing at the author's repository, whose GitHub releases hold the files. It ships with community plugins off until the user turns them on.

## Decision

- SurfSense's plugins are listed in a built-in list packaged into the app, shown with no network and no consent. It changes with app releases. It holds entries only, a few hundred bytes each, never plugin code, bundle files or version lists.
- Every other publisher's plugin is listed in one file, `plugins/registry/plugins.json` in this repository. An entry is added by pull request and reviewed once by a maintainer. A change to the server behind it needs no review.
- Neither list holds plugins: a plugin's code, and later its bundle files, stay with its publisher, in its own host or repository.
- Both lists share one entry schema with a `kind`, `remote` now, with `bundle` reserved. The publisher is set by the list: `surfsense` only in the built-in list, `partner` or `community` in the registry. `auth: license` and `access: license` appear only in the built-in list, so a fetched file can never claim to be SurfSense or receive the license key. `CODEOWNERS` requires a maintainer's approval for every change to the registry.
- Every plugin not published by SurfSense, a custom one added by URL included, is off until the user turns other publishers on once.
- A tool a server adds after the user connected, or one that changes as the proposal's rule says, starts off until the user turns it on ([tools added later](../proposals/plugins/core/02-registry.md#tools-added-later)).
- A maintainer delists a registry plugin by moving its entry to `removed` with a reason; apps stop offering its tools.
- On each merge to `main`, CI signs the registry and publishes it to SurfSense's own plugin host. The app fetches it when the user turns on other publishers, after consent, checks the signature against a key compiled in, and caches it. No installer carries it, so the registry grows and shrinks without app updates.

## Consequences

- A company or developer joins with one pull request and no build pipeline.
- Review sees the listing and the tools at the time; it does not see later deploys, which is why later tools start off.
- SurfSense needs a host for the signed registry, and a signing key kept as a CI secret.
- A new SurfSense plugin reaches users with the next app release. Its server can refuse calls at once, so withdrawing one needs no release.

## Where the code stands

`plugins/registry/` and the built-in list do not exist, and the app has no copy of the registry, Restricted mode or plugin screen. The only plugin interface is a "Plugins / Coming soon" button in [`dashboard-page.tsx`](../../surfsense_local/frontend/src/features/dashboard/dashboard-page.tsx).
