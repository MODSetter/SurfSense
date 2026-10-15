from typing import Annotated

from fastapi import Depends, Request

from modules.chat.runs.registry import ChatRuns


def get_chat_runs(request: Request) -> ChatRuns:
    return request.app.state.chat_runs


ChatRunsDep = Annotated[ChatRuns, Depends(get_chat_runs)]
