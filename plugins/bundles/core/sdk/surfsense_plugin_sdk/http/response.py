"""What a source answered, whatever its status."""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from email.message import Message
from typing import Any


@dataclass(frozen=True)
class Response:
    """Returned for every status: the plugin decides what a 404 means."""

    status: int
    # Found however a name is written: "Content-Type" and "content-type" alike.
    headers: Mapping[str, str]
    content: bytes

    @property
    def text(self) -> str:
        """The body as text, in the charset the source declared, else UTF-8."""
        declared = Message()
        declared["content-type"] = self.headers.get("content-type", "")
        charset = declared.get_content_charset() or "utf-8"
        return self.content.decode(charset, errors="replace")

    def json(self) -> Any:
        """Any: a source's JSON has whatever shape the source gives it."""
        return json.loads(self.content)
