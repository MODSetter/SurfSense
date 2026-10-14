"""The page the browser lands on after the provider: what happened, and to go back to SurfSense."""

from html import escape

from fastapi import status
from fastapi.responses import HTMLResponse

_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SurfSense</title>
<style>
body{{font:16px/1.5 system-ui,sans-serif;margin:0;display:grid;place-items:center;
min-height:100vh;background:#fafafa;color:#171717}}
main{{max-width:28rem;padding:0 16px;text-align:center}}
@media (prefers-color-scheme:dark){{body{{background:#171717;color:#fafafa}}}}
</style></head>
<body><main><h1>{title}</h1><p>{body}</p></main></body></html>"""


def signed_in_page(name: str) -> HTMLResponse:
    return HTMLResponse(
        _PAGE.format(
            title=f"Signed in to {escape(name)}.",
            body="You can close this tab and return to SurfSense.",
        )
    )


def failed_page(name: str | None, reason: str) -> HTMLResponse:
    title = (
        f"Couldn't sign in to {escape(name)}."
        if name
        else "This sign-in isn't one SurfSense started."
    )
    return HTMLResponse(
        _PAGE.format(
            title=title, body=f"{escape(reason)} Return to SurfSense to try again."
        ),
        status.HTTP_400_BAD_REQUEST,
    )
