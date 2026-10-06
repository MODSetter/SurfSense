"""The events that end a Responses stream. Nothing before one counts as a finished reply.

From OpenAI's streaming events reference. The chat's client and the agent's
relay both read this list, so a new ending is added once.
"""

COMPLETED = "response.completed"
INCOMPLETE = "response.incomplete"
FAILED = frozenset({"response.failed", "error"})

ENDINGS = frozenset({COMPLETED, INCOMPLETE, *FAILED})
