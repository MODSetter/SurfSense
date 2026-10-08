# ADR 0052: The chat engine's model never calls tools; SurfSense chooses a plugin tool through structured output and calls it

- **Status:** Proposed, with the [plugins proposal](../proposals/plugins/README.md)
- **Date:** 2026-10-08
- **Source:** maintainer decision, 8 Oct 2026 (no permalink); [agent: which engine a model gets](../proposals/agent/01-which-engine.md)

## Context

The chat engine answers every model with one call and no tools; a thread that needs tools is the agent's ([chat](../architecture/chat.md)). It serves models as small as Qwen3-0.6B, which scores 3.62% on multi-turn function calling against 41.75% for Qwen3-8B on the Berkeley leaderboard, and models whose template has no tool support at all, such as Gemma 3 4B. Plugins have to reach chat threads too.

Any local model can be held to a JSON schema by llama.cpp's grammar, and the remote catalog records which remote models support structured output ([agent/01](../proposals/agent/01-which-engine.md)).

## Decision

- The chat engine's model never receives tools and never makes a tool call.
- When ready plugin tools exist and the router is on for the model, a router step runs before the answer: one call held to a schema choosing a tool or `none`, then one call held to the chosen tool's flat input schema filling its inputs. SurfSense makes the call through the Tool Gateway, and the result joins the answer's prompt.
- The router is on by default only for a model that passes the chat eval's router test; for others the user can turn it on. A remote model without structured output gets no router.
- An `@` mention names the tool, so the model only fills its inputs. It works on every model.

## Consequences

- Plugins reach every model in a chat thread, with no tool-calling support needed.
- A turn with the router costs one or two extra model calls; a turn without ready tools costs nothing more.
- A small model may choose badly. Measuring it, gating the router per model, approval showing the exact arguments, and `@` mentions bound the cost.
- Destructive tools and tools without a flat schema are never chosen by the router.

## Where the code stands

The chat engine has no router step, `@` mentions, or plugin steps, and the chat eval has no router test.
