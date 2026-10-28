# ADR 0076: The legacy self-hosted stack lives on its own branch, tagged `legacy-v*`, and its install paths on `main` pass to the new stack

- **Status:** Accepted
- **Date:** 2026-10-28
- **Source:** the legacy split proposal, now [Legacy stack](../architecture/legacy.md)

## Context

The hosted user data was purged on 18 Oct 2026. `surfsense_backend` and `surfsense_web` still carried three things that outlived it: the license portal, the marketing site and the legacy self-host images. Self-hosters still run those images, and their one-line installer downloads from `main`.

## Decision

- **The legacy stack moves to a `legacy` branch** and is deleted from `dev` and `main`. A fix is a pull request into `legacy`; phasing it out needs no cleanup on `dev`, since the branch simply stops being used.
- **What still ships leaves it first:** the license portal and the plugins into `backend/`, the marketing site into `www/`.
- **Its tags are `legacy-v*`,** since tags are repo-wide, and the desktop and Docker releases start only on `v[1-9]*`.
- **The legacy images keep their names;** the new stack publishes `ghcr.io/modsetter/surfsense`, so no tag is shared.
- **The install paths on `main` pass to the new stack,** with no stub forwarding to `legacy`. The new installer installs only the new image and never looks for the legacy stack; it refuses only a `./surfsense` that is not its own.
- Rejected: keeping the legacy trees on `dev` behind path filters, which leaves every later change working around them; forwarding stubs at the old install paths, which would keep sending new users to the legacy stack.

## Consequences

- `dev` and `main` carry no legacy code, CI or hooks, and `legacy`'s CI is scoped by branch.
- Until the new installer reaches `main`, the old one-line command answers 404.
- A legacy self-hoster moves to 2.0 through the markdown export and import ([ADR 0022](0022-markdown-only-cloud-import.md)), not a database migration.
