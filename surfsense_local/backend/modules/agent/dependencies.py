from typing import Annotated

from fastapi import Depends, Request


def get_launch_key(request: Request) -> str:
    """This API process's launch key, which opencode's configuration carries."""
    return request.app.state.agent_launch_key


LaunchKeyDep = Annotated[str, Depends(get_launch_key)]
