# ADR 0078: A picture a connected model returns is fetched with its connection

- **Status:** Accepted
- **Date:** 2026-11-02
- **Supersedes:** for a picture a remote image model returns as a link, the egress decision on that link's host, which `refused_named_host()` took before the download
- **Source:** maintainer decision, 2 Nov 2026 (no permalink)

## Context

A remote image model answers with the picture itself or with a link to it. A link was downloaded only once egress to its host was allowed, and the host is the provider's choice: OpenAI's DALL·E links point at Azure storage (`oaidalleapiprodscus.blob.core.windows.net`), not `api.openai.com`, and Azure OpenAI, xAI and Together link to storage hosts of their own. The user had already allowed the provider, yet the first image from it failed with "Sending data to … is off", to be allowed in Settings and retried. A Studio job cannot ask, so the image never appeared. A rule trusting only the connection's own site would not help: those hosts are on other sites.

## Decision

- Every image request asks for the picture itself, `response_format: "b64_json"`, so no link comes back where the model allows it. A model that refuses the setting with a `400`, as GPT image models do, which always answer with the picture, is asked once more without it.
- A link that still comes back is fetched as part of the connection the user allowed, its redirects included, with no egress decision of its own.
- The fetch keeps its other limits: no bearer token, HTTP(S) only on every hop, at most three redirects, bounded size, and bytes that must be the image they claim.

## Consequences

- Making or editing an image through an allowed provider never stops at an egress step; the one decision is allowing the provider.
- The provider decides which host the computer reaches for a linked picture. The request carries no prompt, document or key, but it tells that host the computer's address and when the picture was made. Allowing a provider now covers that.
- The check on each redirect hop, added for a review the day before, goes with it.
- `refused_named_host()` remains for the plugin registry, whose URL is fixed.
