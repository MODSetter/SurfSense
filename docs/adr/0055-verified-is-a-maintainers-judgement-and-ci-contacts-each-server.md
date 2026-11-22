# ADR 0055: Verified is a maintainer's judgement, and CI contacts each server a pull request adds

- **Status:** Accepted
- **Date:** 2026-10-14
- **Supersedes:** [ADR 0053](0053-plugins-are-listed-in-a-registry-and-third-party-ones-start-off.md) in part: a verified entry proven by its `domain`
- **Source:** maintainer decision, 14 Oct 2026 (no permalink); [#2249](https://github.com/MODSetter/SurfSense/pull/2249)

## Context

A `verified` registry entry had to name a `domain` its publisher proved they own, by a file, a DNS record or the MCP Registry, and the check required the server's hosts to sit on it. The check never fetched the proof: a maintainer did that by hand, so the rule only checked that the entry agreed with itself. DeepWiki was marked verified without a `domain`, the check failed, and the sign job stopped before 2.2.1's list was signed; with no proof published by its author, it became `community` ([#2249](https://github.com/MODSetter/SurfSense/pull/2249)). Meanwhile nothing checked what review actually needed: that the server answers MCP, lists the tools its entry names, and signs in on the hosts the user is asked about.

## Decision

- `verified` is set by a maintainer when they are satisfied, on any evidence, that `author` runs the server. The entry carries no `domain`, and no check reads one.
- Only a maintainer's approval merges a registry change (CODEOWNERS), so only a maintainer sets or keeps `verified`.
- On every pull request, CI connects to each entry it adds or changes with the MCP client the app uses, and fails it when the app could not use it: unreachable, not MCP over Streamable HTTP, sign-in asked where `auth` says none, tools that differ from `tools`, or OAuth that cannot be found, registered with, or reached on the listed `hosts`.
- What MCP leaves optional, such as a tool's safety hints, only warns, so any server the app could use passes.
- The sign job never contacts servers: a third-party server that is down must not hold up the list.

## Consequences

- The checkmark means SurfSense's maintainers vouch for who runs the server, not that a proof was published; maintainers can verify a well-known publisher that will never add a file or a record.
- A broken listing is caught before merge, not when a maintainer or a user connects it.
- CI holds no credentials, so a server behind a key or an account is checked for reachability and sign-in, not its tools; the maintainer still connects it.
- A pull request's check depends on the third party's server being up at that moment; rerunning it is the fix.
