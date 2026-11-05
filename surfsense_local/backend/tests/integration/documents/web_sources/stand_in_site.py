"""A web site and a SearXNG server on loopback, which needs no network consent."""

from collections.abc import Callable
from typing import Any

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import (
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
    RedirectResponse,
    Response,
)
from starlette.routing import Route

PARAGRAPH = (
    "The moon pulls the sea towards it, so the water rises in a bulge on the side "
    "facing it and on the far side too, and the coast sees two high tides a day."
)
ARTICLE = f"""<html><head><title>Tide tables explained</title></head><body>
<nav><a href="/">Home</a> <a href="/about">About</a></nav>
<article><h1>Tide tables explained</h1>{f"<p>{PARAGRAPH}</p>" * 12}</article>
<footer>Contact us at the harbour office.</footer></body></html>"""
NOT_FOUND = f"""<html><head><title>Page not found</title></head><body>
<article><h1>Page not found</h1>{f"<p>{PARAGRAPH}</p>" * 4}</article></body></html>"""
# Cloudflare's interstitial, as a reader without a browser meets it.
WALL = """<html><head><title>Just a moment...</title></head><body>
<div id="challenge-running">Checking your browser before accessing the site.</div>
<p>Enable JavaScript and cookies to continue.</p></body></html>"""
README = "# Tides\n\nThe moon pulls the sea.\n"


def site(asked: list[Request]) -> Starlette:
    """Every request is kept in `asked`, so a test sees what reached the site."""

    def answering(response: Callable[[Request], Response]):
        async def endpoint(request: Request) -> Response:
            asked.append(request)
            return response(request)

        return endpoint

    return Starlette(
        routes=[
            Route("/explained", answering(lambda _: HTMLResponse(ARTICLE))),
            Route(
                "/old-explained",
                answering(lambda _: RedirectResponse("/explained", status_code=301)),
            ),
            Route(
                "/elsewhere",
                answering(
                    lambda _: RedirectResponse(
                        "https://tides.example/explained", status_code=302
                    )
                ),
            ),
            Route(
                "/gone",
                answering(lambda _: HTMLResponse(NOT_FOUND, status_code=404)),
            ),
            Route("/wall", answering(lambda _: HTMLResponse(WALL, status_code=403))),
            Route(
                "/table.pdf",
                answering(
                    lambda _: Response(
                        b"%PDF-1.7 " + b"0" * 1000, media_type="application/pdf"
                    )
                ),
            ),
            Route(
                "/README.md",
                answering(lambda _: PlainTextResponse(README)),
            ),
            Route("/empty", answering(lambda _: HTMLResponse("<html></html>"))),
        ]
    )


def searxng(answer: Callable[[Request], Response], asked: list[Request]) -> Starlette:
    """A SearXNG server whose `/search` gives `answer`'s response, keeping each request."""

    async def search(request: Request) -> Response:
        asked.append(request)
        return answer(request)

    return Starlette(routes=[Route("/search", search)])


def results(*found: dict[str, Any], unresponsive: list | None = None) -> Response:
    """A SearXNG JSON answer, as `/search?format=json` gives it."""
    return JSONResponse(
        {
            "query": "tides",
            "number_of_results": 0,
            "results": list(found),
            "answers": [],
            "suggestions": [],
            "unresponsive_engines": unresponsive or [],
        }
    )


def found(url: str, title: str, content: str = "") -> dict[str, Any]:
    """One of SearXNG's results."""
    return {"url": url, "title": title, "content": content, "engine": "duckduckgo"}
