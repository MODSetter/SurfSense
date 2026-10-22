"""A plugin's HTML description as plain lines, list items kept as markdown bullets."""

from html.parser import HTMLParser

_BLOCKS = {"p", "div", "br", "ul", "ol", "li", "h1", "h2", "h3", "h4", "tr"}


def plain_text(html: str) -> str:
    reader = _Reader()
    reader.feed(html)
    reader.close()
    lines = (" ".join(line.split()) for line in "".join(reader.parts).splitlines())
    return "\n".join(line for line in lines if line)


class _Reader(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in _BLOCKS:
            self.parts.append("\n")
        if tag == "li":
            self.parts.append("- ")

    def handle_endtag(self, tag: str) -> None:
        if tag in _BLOCKS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)
