"""SubAgent ``task`` tool wiring required for HITL inside subagents.

Replaces upstream ``SubAgentMiddleware`` to:

- share the parent's checkpointer with each subagent,
- forward ``runtime.config`` (thread_id, recursion_limit, …) into nested invokes,
- isolate each parallel ``task`` call in its own checkpoint slot via
  per-call ``thread_id`` namespacing,
- bridge ``Command(resume=...)`` from the parent into the subagent via the
  ``config["configurable"]["surfsense_resume_value"]`` side-channel, keyed by
  ``tool_call_id`` so parallel siblings never race on a shared scalar,
- target the resume at the captured interrupt id so a follow-up
  ``HumanInTheLoopMiddleware.after_model`` does not consume the same payload,
- stamp each subagent's pending interrupt with the parent's ``tool_call_id``
  so ``stream_resume_chat`` can route a flat ``decisions`` list back to the
  right paused subagent.

Module layout
-------------

- ``constants``     — shared keys / limits.
- ``config``        — RunnableConfig + side-channel resume read + per-call ``thread_id``.
- ``resume``        — pending-interrupt detection, fan-out, ``Command(resume=...)`` builder.
- ``propagation``   — ``wrap_with_tool_call_id`` helper for stamping interrupt values.
- ``resume_routing``— slice a flat decisions list to per-``tool_call_id`` payloads.
- ``task_tool``     — the ``task`` tool factory (sync + async), and the catch-and-stamp chokepoint.
- ``middleware``    — :class:`SurfSenseCheckpointedSubAgentMiddleware` itself.
"""

from .middleware import SurfSenseCheckpointedSubAgentMiddleware

__all__ = ["SurfSenseCheckpointedSubAgentMiddleware"]
