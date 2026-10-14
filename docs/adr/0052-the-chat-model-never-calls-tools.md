# ADR 0052: The chat engine's model never calls tools; SurfSense chooses a plugin tool through structured output and calls it

- **Status:** Proposed, with the [plugins proposal](../proposals/plugins/README.md); deferred until plugins reach the chat engine, after agent threads
- **Date:** 2026-10-08
- **Source:** maintainer decision, 8 Oct 2026 (no permalink); [agent: which engine a model gets](../proposals/agent/01-which-engine.md)

## Context

The chat engine answers every model with one call and no tools; a thread that needs tools is the agent's ([chat](../architecture/chat.md)). It serves models as small as Qwen3-0.6B, which scores 3.62% on multi-turn function calling against 41.75% for Qwen3-8B on the Berkeley leaderboard, and models whose template has no tool support at all, such as Gemma 3 4B. Plugins have to reach chat threads too.

Every text route the chat engine uses already takes a JSON schema, and the remote catalog records which remote models support structured output ([agent/01](../proposals/agent/01-which-engine.md)). A schema is not a guarantee: llama-server rejects one for some templates, and some endpoints ignore it.

## Decision

- The chat engine's model never receives tools and never makes a tool call.
- When ready plugin tools exist and the router is on for the model, a router step runs before the answer: one call held to a schema choosing a tool or `none`, then one call held to the chosen tool's flat input schema filling its inputs. SurfSense makes the call through the Tool Gateway, and the result joins the answer's prompt.
- The router is on by default for a model that passes the chat eval's router test, a remote model the catalog says supports structured output, and a ChatGPT plan's model. For a local model not yet measured, a model the catalog says nothing about, or a custom connection's model, it is off until the user turns it on. A model the catalog says lacks structured output never runs it.
- Every router reply is validated against its schema; one that does not match counts as `none`, and a failed router call leaves the turn to answer as it does today.
- An `@` mention names the tool, so the model only fills its inputs, and where it cannot, the user fills a small form. It works on every model.

## Consequences

- Plugins reach every model in a chat thread, with no tool-calling support needed.
- A turn with the router costs one or two extra model calls; a turn without ready tools costs nothing more.
- A small model may choose badly. Measuring it, gating the router per model, approval showing the exact arguments, and `@` mentions bound the cost.
- Destructive tools and tools without a flat schema are never chosen by the router.
- On a ChatGPT plan, each router call counts against the user's plan.

## Where the code stands

The chat engine has no router step, `@` mentions, or plugin steps, and the chat eval has no router test.
