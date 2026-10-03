"""Who may call the tools: the opencode SurfSense launched, and never a web page."""

from fastapi import HTTPException, Request, status


def refuse_web_pages(request: Request) -> None:
    """Refuse a request a browser sent: it names its page's origin, and opencode names none."""
    if "origin" in request.headers:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "web pages may not call the agent's tools"
        )
