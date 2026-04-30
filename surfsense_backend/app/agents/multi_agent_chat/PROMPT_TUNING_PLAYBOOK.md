# Multi-Agent Prompt Tuning Playbook

This playbook defines how to tune `multi_agent_chat` prompts for better outcomes than `new_chat` on delegation quality, lower confusion, and stable tool behavior.

It is intentionally architecture-aware: this system is a **supervisor + expert tools** pattern, not a single flat tool agent.

## Why this matters in our architecture

- The supervisor only sees **routing tools** (e.g. `research`, `gmail`, `calendar`), not low-level connector APIs.
- Experts are invoked through `routing/from_domain_agents.py` and receive a single natural-language task via `compose_child_task(...)`.
- Because expert context is compact and delegated, prompt quality is the primary control lever for routing accuracy and downstream tool behavior.

## Authoritative guidance we should follow

- Anthropic prompt engineering best practices (role clarity, XML structure, explicit tool-use policy, few-shot examples): [Anthropic docs](https://docs.anthropic.com/en/docs/use-xml-tags)
- OpenAI function-calling reliability guidance (clear tool descriptions, when/when-not tool usage, small callable surface): [OpenAI function calling guide](https://developers.openai.com/docs/guides/function-calling)
- OpenAI prompt engineering (instruction hierarchy and explicit output contracts): [OpenAI prompt engineering guide](https://developers.openai.com/api/docs/guides/prompt-engineering)
- LangChain supervisor/subagents guidance (clear subagent names/descriptions, context engineering, routing intent): [LangChain supervisor docs](https://docs.langchain.com/oss/python/langchain/supervisor), [LangChain subagents docs](https://docs.langchain.com/oss/python/langchain/multi-agent/subagents)

## Current weakness audit (as of now)

- `supervisor/supervisor_prompt.md` is short and does not define decision policy for ambiguous/multi-domain tasks.
- Most expert `domain_prompt.md` files are one-line role statements with no:
  - scope boundaries and refusal policy,
  - parameter-resolution behavior,
  - completion criteria (what must be returned),
  - failure handling rules,
  - concrete examples.
- Tool descriptions in routing are generic ("Pass a clear natural-language task"), which weakens handoff quality.

## Prompt design standards (required)

Apply these standards to supervisor and every expert prompt.

1. **Role + objective first**
   - One sentence for identity.
   - One sentence for success criterion.

2. **Explicit routing/usage rules**
   - Tell the model when to use this agent/tool.
   - Tell it when not to use it.
   - Include ambiguity fallback ("ask one clarifying question" or "do X conservative default").

3. **Structured task contract**
   - Require concise but complete execution reports.
   - Require IDs/links/timestamps when tool outputs produce them.
   - For no-op paths, explain why no action was taken.

4. **Safety + reliability contract**
   - Never fabricate tool results.
   - Never claim action if no successful tool call happened.
   - Surface irreversible/risky actions clearly.

5. **Few-shot examples**
   - Include 2-4 minimal examples per domain:
     - direct success,
     - ambiguous input,
     - out-of-scope reroute.

6. **Concise formatting rules**
   - Avoid verbosity.
   - Stable response structure improves orchestration and observability.

## Supervisor prompt blueprint

The supervisor prompt should contain these sections in order:

1. `Role`
2. `Available experts` (name + scope + non-scope)
3. `Delegation policy`
   - single-domain -> one expert
   - multi-domain -> sequence or parallel where independent
   - no expert needed -> answer directly
4. `Task-writing policy` for delegated calls
   - include user goal, constraints, success criteria
   - include only needed context
5. `Result synthesis policy`
   - merge expert outputs into one user-facing response
   - preserve concrete identifiers from expert outputs
6. `Failure policy`
   - retry on recoverable mismatch
   - ask clarifying question when required field is missing

## Expert prompt blueprint (per domain)

Each `domain_prompt.md` should include:

1. `Role and scope`
2. `In-scope actions` (mapped to the exact provided tools)
3. `Out-of-scope behavior` (what to return for reroute)
4. `Execution rules`
   - choose the minimum tool sequence that satisfies request
   - do not guess IDs or parameters
   - ask concise clarification only when necessary
5. `Output contract`
   - action summary
   - concrete artifacts/IDs/links generated
   - unresolved items and next step
6. `Examples` (2-4 realistic, short)

## Domain-specific tuning checklist

- `research`: enforce source-grounded summaries and explicit uncertainty.
- `memory`: strict save criteria (durable preference/fact only) and secret-handling policy.
- `deliverables`: require output artifact references and constraints echo.
- `gmail` / `calendar`: require recipient/date-time disambiguation policy and timezone handling.
- `docs connectors` (`notion`, `confluence`, `drive`, `dropbox`, `onedrive`): require exact page/file target resolution before mutate actions.
- chat connectors (`discord`, `teams`, `slack`): require channel/thread context clarity before send actions.
- MCP experts: require strict tool-description adherence and no assumption about unavailable endpoints.

## Tool description tuning rules (routing layer)

Routing tool descriptions should include:

- best-fit task types,
- disallowed task types,
- required task payload hints (e.g. "include recipient + intent + constraints"),
- expected result shape.

This is especially important because supervisor tool choice is heavily influenced by `name + description`.

## Evaluation plan (before wiring to production)

Create a prompt eval set with at least 20 tasks:

- 8 single-domain tasks,
- 6 ambiguous tasks (should clarify or route conservatively),
- 6 multi-domain tasks (should sequence experts correctly).

Track:

- routing accuracy,
- unnecessary delegation rate,
- tool-call success rate,
- clarification precision (ask only when needed),
- final answer completeness.

Use same test set against:

- current prompts,
- tuned prompts v1,
- tuned prompts v2.

Promote only when v2 improves routing accuracy and reduces unnecessary delegation with no regression in tool-call success.

## Immediate implementation plan

1. Rewrite `supervisor/supervisor_prompt.md` using the supervisor blueprint.
2. Rewrite all expert `domain_prompt.md` files with the expert blueprint.
3. Upgrade routing tool descriptions in `routing/supervisor_routing.py` to add "when to use / when not to use".
4. Add a lightweight prompt eval script or fixture set for reproducible tuning.

## Definition of done

- Every supervisor/expert prompt has explicit scope, failure policy, and output contract.
- Every route description encodes clear decision boundaries.
- Prompt eval shows measurable gains on routing accuracy and lower unnecessary delegation.
- Team can iterate prompt versions without changing core orchestration code.

