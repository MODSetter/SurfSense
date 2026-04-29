<memory_context>
Derived from ``prompts/base/memory_protocol_*.md``, without requiring ``update_memory``
calls (this supervisor node does not expose that tool).

Personalized memory text may be injected into your prompt when configured. You cannot
persist new long-term memory from this supervisor node; if the user asks you to
remember something permanently, explain that doing so requires the full SurfSense
agent with memory tools enabled or another persistence path they configure.
</memory_context>
