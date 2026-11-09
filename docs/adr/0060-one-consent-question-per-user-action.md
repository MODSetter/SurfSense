# ADR 0060: One consent question asks for every host a user action needs, including hosts its background work will reach

- **Status:** Accepted; amended by [ADR 0070](0070-opt-in-id-less-update-checks-and-usage-statistics.md): on a new install, the first-run privacy step is the user action the update and usage questions belong to
- **Date:** 2026-10-16

## Context

Egress consent is per host ([ADR 0027](0027-egress-consent-per-host.md)) and asked just in time, on a user action, never on a background call ([ADR 0017](0017-egress-off-by-default.md)). Some actions need several hosts: a ChatGPT sign-in reaches OpenAI's sign-in host and its API; a plugin can sign in on a host of its own; a Claude plan's Claude Code calls `api.anthropic.com` and refreshes its sign-in on `platform.claude.com`. The prompt asked about one host at a time, so a user could allow one and cancel the next, leaving a connection that cannot work.

A host one action needs is not always reached during it. Claude Code refreshes its sign-in in the background, whenever its token is near expiry, at the start of any run; the first run is the model list right after connecting. No dialog can be raised then, so a host left to be asked later is a refusal the user never sees: their Claude plan stops answering once its token expires.

## Decision

- One question per user action, naming every host that action may reach, including a host that work started by it reaches in the background, since that host can never be asked about later.
- A host reached only by a later, separate user action is asked about then, in its own question.
- One Allow switches every host the question named, in one request committed whole (`PUT /egress`): all are allowed or none is.
- Consent stays per host: each is its own row in Settings › Network, switched off alone, and checked on every call.
- The question says what each host receives when they differ: a Claude plan's API host gets what is sent to the model, its sign-in host only the sign-in's refresh.
- Only hosts SurfSense names are ever asked about. A host a program SurfSense runs tries on its own, such as a new one in a future Claude Code, is refused until a release adds it, reviewed and described, to that program's list.

## Consequences

- Connecting a Claude plan, signing in with ChatGPT, or connecting a plugin with its own sign-in host is one question.
- A user cannot allow part of what one action needs from the question itself; they can turn any host off afterwards in Settings › Network.
- A feature whose background work reaches a host its own action did not name fails closed: the host is refused, and the refusal is logged.
