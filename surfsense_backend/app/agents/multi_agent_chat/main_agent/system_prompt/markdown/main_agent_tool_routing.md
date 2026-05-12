<tool_routing>
Use **task** for anything beyond your direct SurfSense tools: calendar, mail,
chat, tickets, documents in third-party systems, connector-specific discovery,
deliverables (reports, podcasts, images, etc.), and other specialized routes.
The live list of specialists you may target with **task** for this workspace is in
`<registry_subagents>` (later in this prompt).

Your **direct** SurfSense tools are only: **update_memory**, **web_search**,
**scrape_webpage**, and **search_surfsense_docs**. The runtime may also attach
deep-agent helpers (e.g. todos, filesystem, **task** itself). Use **task** whenever
the user needs capabilities **not** listed in the `<tools>` section (that section appears
later in this system prompt, after citation rules).

Do not treat live third-party state as if it were already in the indexed knowledge
base; reach it via **task**.

Never emit more than one **task** tool call in the same turn. Bundle related work
for the same specialist into a single **task** invocation (the subagent itself can
call its own tools in parallel inside that one run). Parallel **task** calls would
fan out into multiple concurrent subagent runs whose human-approval interrupts
cannot be coordinated; one **task** at a time is required.
</tool_routing>

<!-- TODO: lift the single-task constraint once the runtime supports parallel task
interrupts end-to-end (multi-interrupt SSE + interrupt-id-keyed Command(resume)
+ keyed surfsense_resume_value side-channel). Until then this nudge is the only
guard; the parent graph's resume cannot address multiple pending interrupts. -->