"""What a tool's definition costs the model, in tokens, sent with every request."""

import json

from modules.plugins.gateway.ready_tool import ReadyTool

# opencode's own estimate of a token, used for its tool output too.
CHARS_PER_TOKEN = 4


def tool_tokens(tool: ReadyTool) -> int:
    told = [tool.tool, tool.title or "", tool.description or "", tool.input_schema]
    return len(json.dumps(told)) // CHARS_PER_TOKEN
