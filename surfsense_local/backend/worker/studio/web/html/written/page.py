"""A model at the agent's bar writes the whole page in one reply, or rewrites it for a Refine (ADR 0066).

No screenshot comes back to Studio, so a page is checked for structure only:
a reply that is no page, too large or cut off before </html> is shown back,
three times at most, as an Office script's failure is.
"""

import re
from html.parser import HTMLParser

from modules.artifacts.script_documents.spec import DocumentSpec
from modules.artifacts.studio_documents.recipe import Refinement
from modules.artifacts.web_pages.design_guide import design_guide
from modules.artifacts.web_pages.no_network import without_network
from modules.artifacts.web_pages.page_checks import PageCheckError, checked_page
from modules.artifacts.web_pages.page_text import page_text
from modules.llm import prompting
from modules.llm.providers.types import Message
from modules.llm.resolution import ResolvedGeneration
from shared import cancellation
from worker.studio.shared import generate
from worker.studio.shared.artifact import Built, Source, fallback_title
from worker.studio.shared.text import file_stem

ATTEMPTS = 3
# About the most one reply carries; the agent's pages, written over many
# calls, may be far larger (save_page.PAGE_BYTES).
PAGE_BYTES = 300 * 1024
MIME = "text/html"
# A page is found by its own markers, never by a code fence: a page may hold
# fenced samples of its own, and a fence round the page lies outside them.
_DOCTYPE = re.compile(r"<!doctype html", re.IGNORECASE)
_HTML_TAG = re.compile(r"<html\b", re.IGNORECASE)
_PAGE_END = re.compile(r"</html\s*>", re.IGNORECASE)


class PageDraftFailedError(RuntimeError):
    """Three replies were no page to keep; Retry asks the model again."""


class _NoPageError(ValueError):
    """Why a reply is no page, as the model is shown it."""


def draft(
    model: ResolvedGeneration, sources: list[Source], user_prompt: str | None
) -> Built:
    system = prompting.load(
        __package__,
        model.tier,
        case="draft",
        focus=prompting.focus(user_prompt),
        design=design_guide(),
        limit=f"{PAGE_BYTES // 1024} KB",
    )
    fallback = fallback_title(user_prompt, sources, "Web page")
    repair: generate.Repair | None = None
    for attempt in range(ATTEMPTS):
        cancellation.raise_if_cancelled()
        raw = generate.run_model(model, system, sources, repair=repair)
        try:
            return built(reply_page(raw), fallback)
        except _NoPageError as error:
            if attempt == ATTEMPTS - 1:
                raise PageDraftFailedError(f"The web page failed: {error}") from error
            repair = generate.Repair(
                reply=raw,
                instruction=(
                    f"That was no page to keep: {error} Return the whole page "
                    "again, from <!doctype html> to </html>, and nothing else."
                ),
            )
    raise AssertionError("unreachable")  # pragma: no cover


def refine(model: ResolvedGeneration, refinement: Refinement, title: str) -> Built:
    """The whole page and the instruction in one call; a reply that is no page is shown back."""
    system = prompting.load(
        __package__,
        model.tier,
        case="refine",
        design=design_guide(),
        limit=f"{PAGE_BYTES // 1024} KB",
    )
    messages = [
        Message(role="system", content=system),
        Message(role="user", content=_request(refinement)),
    ]
    for attempt in range(ATTEMPTS):
        cancellation.raise_if_cancelled()
        raw = generate.complete(model, messages)
        try:
            return built(reply_page(raw), title)
        except _NoPageError as error:
            if attempt == ATTEMPTS - 1:
                raise PageDraftFailedError(f"The web page failed: {error}") from error
            messages += [
                Message(role="assistant", content=raw),
                Message(
                    role="user",
                    content=(
                        f"That was no page to keep: {error} Return the whole "
                        "revised page again, from <!doctype html> to </html>."
                    ),
                ),
            ]
    raise AssertionError("unreachable")  # pragma: no cover


def _request(refinement: Refinement) -> str:
    """The current page, fenced longer than any run of backticks in it, then the change."""
    page = refinement.base.text
    longest = max((len(run) for run in re.findall(r"`+", page)), default=0)
    fence = "`" * max(3, longest + 1)
    return (
        f"The current page:\n\n{fence}html\n{page}\n{fence}\n\n"
        f"Change it as follows: {refinement.instruction}"
    )


def reply_page(raw: str) -> str:
    """The page in the reply: from its doctype, else its <html> tag, to the last </html>.

    The doctype first, so an <html> named in prose before the page is not taken for it.
    """
    start = _DOCTYPE.search(raw) or _HTML_TAG.search(raw)
    if start is None:
        raise _NoPageError("The reply has no HTML page in it.")
    text = raw[start.start() :]
    ends = list(_PAGE_END.finditer(text))
    if not ends:
        raise _NoPageError(
            "The page was cut off before </html>. Make it shorter so it ends in "
            "one reply."
        )
    return text[: ends[-1].end()]


def built(page: str, fallback: str) -> Built:
    stored = without_network(page)
    try:
        checked_page(stored.encode("utf-8"), PAGE_BYTES)
    except PageCheckError as error:
        raise _NoPageError(str(error)) from error
    body = page_text(page)
    title = _title(page) or _first_heading(body) or fallback
    return Built(
        title=title,
        markdown=body or f"# {title}",
        primary=stored.encode("utf-8"),
        primary_mime=MIME,
        primary_filename=f"{file_stem(title, 'page')}.html",
        # The page as the model wrote it, so a Refine rewrites its words, not SurfSense's policy.
        spec=DocumentSpec("html", page, "html", ()).as_metadata(),
    )


class _Title(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._in_title = False
        self._in_svg = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._in_svg += tag == "svg"
        self._in_title = tag == "title" and not self._in_svg and not self.parts

    def handle_endtag(self, tag: str) -> None:
        self._in_svg -= tag == "svg" and self._in_svg > 0
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.parts.append(data)


def _title(page: str) -> str | None:
    reader = _Title()
    reader.feed(page)
    title = " ".join("".join(reader.parts).split())
    return title[:200] or None


def _first_heading(body: str) -> str | None:
    first = body.split("\n", 1)[0]
    return first[2:].strip() or None if first.startswith("# ") else None
