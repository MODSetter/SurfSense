from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from modules.documents.schemas import DocumentRead

# Per Add, as the dialog takes them.
MAX_LINKS = 20


class WebSearch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)
    ]
    # The whole web, or only YouTube's videos.
    source: Literal["web", "youtube"] = "web"
    # 0 for the first results; Show more asks for the next, up to 4.
    page: int = Field(default=0, ge=0, le=4)


class WebResult(BaseModel):
    url: str
    title: str
    description: str | None
    # The page's host, so a user can judge where it comes from.
    site: str
    # Which puller would pull it, so the row can say a video comes with its transcript.
    puller: str


class WebResults(BaseModel):
    results: list[WebResult]
    # Show more would find more.
    more: bool


# http(s) only: a file path or another scheme is never fetched.
WebLink = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, pattern=r"^https?://\S+$", max_length=2048
    ),
]


class WebLinksOpen(BaseModel):
    model_config = ConfigDict(extra="forbid")

    urls: list[WebLink] = Field(min_length=1, max_length=MAX_LINKS)


class WebLinksAdd(BaseModel):
    model_config = ConfigDict(extra="forbid")

    urls: list[WebLink] = Field(min_length=1, max_length=MAX_LINKS)


class WebLinkDuplicate(BaseModel):
    url: str
    document_id: int


class WebLinksOutcome(BaseModel):
    created: list[DocumentRead]
    duplicates: list[WebLinkDuplicate]
