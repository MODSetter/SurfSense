# ADR 0094: The star goes to a model that runs the agent here, and to a small one without a graphics card

- **Status:** Accepted
- **Date:** 2026-11-22
- **Revises:** the recommendation rule in [ADR 0026](0026-curated-order-is-list-position.md). Position stays the only preference, and nothing is scored.
- **Source:** the weak-hardware tests of 21 and 22 Nov 2026: 30 local models through the live agent suite's screening cases on llama.cpp `b11050`, with an RTX 3080 held to an 8 GB or 6 GB card's budget. Spark-X2.6-4B's results are the committed input [`local-screen-v1.json`](../../surfsense_local/backend/scripts/capability_list/local/local-screen-v1.json), Nemotron 3.5 Bolt E4B's [`local-screen-v2.json`](../../surfsense_local/backend/scripts/capability_list/local/local-screen-v2.json). The order of the two is the maintainer's call of 23 Nov 2026, after using the app with both (#2451, #2454 and #2455 together): "Spark failed on a lot of studio tasks. Nemotron was more reliable so I think we should move nemotron above spark in star rating for now."

## Context

The star went to the first curated model, in manifest order, with a build that runs well on the machine. Two things went wrong with it.

- **It did not ask whether the agent runs.** Agentic chats need a model that carries the agent and a 32,768-token window ([`agent_gate.py`](../../surfsense_local/backend/modules/llm/capability/agent_gate.py)). Of 30 local models screened on an 8 GB card's memory, only Spark-X2.6-4B passed every case; Qwen3 32B, 14B and 8B, the stars on 12 to 24 GB machines, never passed one. A model can also fit while the load plan gives it only 8K or 16K.
- **Without a graphics card, every build that fits is full speed.** So a 32 GB laptop with no card was offered Qwen3.8 27B. Reading the prompt comes first there: even 1.7B and 2B models waited 86 s or more for the first word of the agent's opening request on a Ryzen 7 5800X.

## Decision

- **On a graphics card or Apple's unified memory, the star goes to the first model the shipped capability list says runs the agent on this computer.** That means `capability_of(id, None)` at `agent` or `agent_limited`, a template that calls tools, and a build the load plan keeps resident at the agent's window. Its recommended build is then the largest, at or below its default, that the plan keeps resident there. When no model qualifies, the star goes as before: the first model with a build that runs well.
- **Without a graphics card, no model carries the agent, and only a build of 3 GiB or less is recommended** (`PROCESSOR_STAR_CEILING_BYTES`, about Qwen3 4B at `UD-Q4_K_XL`). The star is then a quick model for Basic chat. Integrated graphics count as the processor.
- **Nemotron 3.5 Bolt E4B ranks above Spark-X2.6-4B, for now.** The rule is unchanged: position picks among the models measured to run the agent here, so Nemotron takes the star wherever its 4-bit build keeps the agent's window resident, from about 7.5 GiB free (10 GB cards and up, Macs from 16 GB), and an 8 GB card, about 7 GiB free, keeps Spark. Its row was measured with the documents helper, short skill, syntax check and no-format rule of #2455 (pdf-brief and board-pack two of two each; without them one of four), and again on #2455's final text on 23 Nov 2026 (four of four), so this change is stacked on #2455 and reaches `dev` only with it.
- **An entry may name its own default build** (`default_quantization`) where a measurement beats the preference order: Spark-X2.6-4B's `Q8_0` passed six of six agent cases, its `Q4_K_M` three.
- **The chat models are Qwen3.8 27B, Nemotron 3.5 Bolt E4B, Spark-X2.6-4B, Qwen3 4B, Gemma 3 4B, Qwen3 1.7B and 0.6B.** Qwen3 32B, 14B and 8B are dropped; a copy already downloaded stays usable as a found file.
- **A capability row can come from the two screening cases run on this computer's llama.cpp** (`local-screen`), for a model no provider serves. It holds only for a local copy, as a provider's row holds only on its host.

## Consequences

- **What each machine is offered.** Shares are from PostHog's opt-in usage reports, 393 of them, read on 22 Nov 2026.

  | Machine | Share | Starred |
  |---|---|---|
  | Card of 12 GB or more | 10.2% | Nemotron 3.5 Bolt E4B `UD-Q4_K_XL` at 32K, Agentic |
  | Card of 8 to 11 GB | 14.0% | Spark-X2.6-4B `Q8_0` at 32K on an 8 GB card, Nemotron `UD-Q4_K_XL` at 32K from 10 GB, Agentic |
  | Mac with 16 GB or more | 9.9% | Nemotron 3.5 Bolt E4B `UD-Q4_K_XL` at 32K, Agentic |
  | Card of 4 to 7 GB | 15.8% | Spark-X2.6-4B at 8K on a 6 GB card, Qwen3 1.7B on a 4 GB one, Basic |
  | Mac with 8 GB | 1.8% | Spark-X2.6-4B at 8K, Basic |
  | Card under 4 GB | 5.9% | Qwen3 1.7B or 0.6B, Basic |
  | No card, or integrated graphics | 33.6% | Qwen3 4B, Basic |

- **A 24 GB card gets Nemotron too.** Qwen3.8 27B leads the list, but the plan keeps an `f16` cache and gives it 8K there.
- **A 6 GB card cannot run the agent yet.** Spark's `Q4_K_M` needs about 4.3 GB at 32K even with a `q8_0` cache, against 4.2 GB usable on an RTX 3050.
- **The order of Nemotron and Spark is chosen, not measured.** Spark's failures in Studio were seen in the app, and which tasks failed was not recorded; the screening has no Studio case. A Studio case in the suite would let the order be measured.
- **The star reads the capability list as well as the manifest.** A model gains the agent preference only by a measured row, never by its size or its template.
- **Cost:** one more load plan per measured model on each catalog read. It is pure and cheap.
- **Not done:**
  - a `q8_0` cache where it is what reaches the agent's window (6 GB cards, Qwen3.8 27B on 24 GB);
  - a "Slow on this computer" badge for the builds the processor's ceiling skips;
  - speed measured per machine instead of a size cap.
