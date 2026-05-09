"""SubAgent ``task`` tool wiring required for HITL inside subagents.

Replaces upstream ``SubAgentMiddleware`` to:

- share the parent's checkpointer with each subagent,
- forward ``runtime.config`` (thread_id, recursion_limit, …) into nested invokes,
- bridge ``Command(resume=...)`` from the parent into the subagent via the
  ``config["configurable"]["surfsense_resume_value"]`` side-channel,
- target the resume at the captured interrupt id so a follow-up
  ``HumanInTheLoopMiddleware.after_model`` does not consume the same payload,
- re-raise any new subagent interrupt at the parent so the SSE stream surfaces it.

Module layout
-------------

- ``constants``   — shared keys / limits.
- ``config``      — RunnableConfig + side-channel resume read.
- ``resume``      — pending-interrupt detection, fan-out, ``Command(resume=...)`` builder.
- ``propagation`` — re-raise pending subagent interrupts at the parent.
- ``task_tool``   — the ``task`` tool factory (sync + async).
- ``middleware``  — :class:`SurfSenseCheckpointedSubAgentMiddleware` itself.
"""

from .middleware import SurfSenseCheckpointedSubAgentMiddleware

__all__ = ["SurfSenseCheckpointedSubAgentMiddleware"]
