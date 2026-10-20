# ADR 0063: A plugin's connection is a transport and one sign-in, detected from the server

- **Status:** Accepted
- **Date:** 2026-10-20
- **Source:** maintainer decision, 19–20 Oct 2026 (no permalink)

## Context

A plugin connected to a remote MCP server over Streamable HTTP, signed in with nothing, OAuth that registered itself, or one key sent as `Authorization: Bearer`. Measured on 19 Oct 2026 against 35 public servers: Exa reads its key from `x-api-key`; GitHub, Slack, HubSpot, Box and Asana take OAuth only from apps registered in advance, each with a client secret, which an app SurfSense ships cannot hold; older servers speak only the 2024-11-05 HTTP+SSE transport. The MCP authorization spec puts pre-registration between the client and the provider: a client hardcodes one, or lets the user enter their own app's details.

## Decision

- A plugin's connection is a **transport**, `streamable_http` or `sse`, and **one sign-in**: `none`; `headers`, any number of named headers holding the user's key; or `oauth`, which registers itself by client ID metadata document or dynamic registration, or uses the user's own app.
- The transport is found as the spec's backward compatibility says: Streamable HTTP first, the older SSE only when the POST is refused with `400`, `404` or `405`. It is recorded on the plugin, and the agent's runtimes are given it.
- The transport is found again at a check when the recorded one answers `400`, `404` or `405`, since servers move from SSE to Streamable HTTP.
- OAuth registers in the spec's order and stops at the first that works: a client registered in advance, the client ID metadata document, dynamic registration as a public client, then as a confidential client whose secret that registration issues to this install. A provider with no registration at all asks for the user's own app; one whose registration refused SurfSense is told apart, since it may take only apps it approved.
- An OAuth plugin is stored once its sign-in's page is ready, needing a sign-in, so closing the browser loses nothing typed and the plugin signs in later from its row.
- Every connect path names a failure the same way, from its HTTP status, never the server's own text: needs a key or a sign-in, not an MCP server, or out of reach.
- Adding a server is one screen: name, URL and Connect, which tries it at once. Headers sit folded under Advanced settings, rows of a name and a value as other MCP clients take them, the first named `Authorization`, opened by a refusal asking for a key; the same rows edit a connected plugin's connection in place. The user's own OAuth app is never asked for there: a provider taking only registered apps keeps the plugin, needing one, which is set up from its details, as Claude keeps a server that needs authorizing. Every OAuth connect, from Add or Browse, saves the plugin and finishes it in its details the same way.
- The user's own OAuth app, a client ID, an optional secret and scopes, is the user's: its secret is encrypted with the sign-in, never in an entry, a log or a response. The publisher is never asked for one; a registry entry says only `user_client: true`.
- A registry entry names the headers a key goes in, with their wording and prefix, never a value. A key's wording is optional; without it the app asks in its own, translated words.
- Left out: a key in the URL, which the spec forbids for tokens and which is stored in the clear; the OAuth Client Credentials and Enterprise-Managed Authorization extensions, built for services and company identity providers; custom transports; request signing and client certificates; and local servers started by a command, which come with bundles.

## Consequences

- Any remote server that keys in headers, or signs in with OAuth by any of the spec's registrations, can be connected, and the dialog asks only for what its server needs.
- A provider taking only registered apps works once the user registers one; SurfSense registers nothing with providers itself.
- A server is not asked what it needs before it is added: Connect is that question, so the screen shows no tool count or sign-in kind ahead of time.
- A server on SSE only signs in when its POST asks for it, as Asana's, Atlassian's and PayPal's `/sse` do; one asking only on its stream cannot, since a sign-in starts from the POST's `401`.
