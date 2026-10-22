from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from modules.documents.schemas import DocumentRead
from modules.documents.web_sources.pullers.puller import Fit

# Per Add, as the dialog takes them.
MAX_LINKS = 20


class WebSearch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)
    ]


class WebResult(BaseModel):
    url: str
    title: str
    description: str | None
    # The page's host, so a user can judge where it comes from.
    site: str
    # Which puller would pull it, so the list can say a video comes with its transcript.
    puller: str
    # One to add, a list to open, or a short link that cannot be added.
    fit: Fit


class WebSearchRead(BaseModel):
    results: list[WebResult]


class WebGroup(BaseModel):
    # The list link these rows came from; None for single links pasted together.
    link: str | None
    results: list[WebResult]
    # The list has items past these: Show more asks for the next page.
    more: bool
    # The list could not be opened.
    failed: bool


class WebOpenRead(BaseModel):
    groups: list[WebGroup]


# http(s) only: a file path or another scheme never reaches a plugin.
WebLink = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, pattern=r"^https?://\S+$", max_length=2048
    ),
]


class WebLinksOpen(BaseModel):
    model_config = ConfigDict(extra="forbid")

    urls: list[WebLink] = Field(min_length=1, max_length=MAX_LINKS)


class WebListPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: WebLink
    # 0 for the first 20 items; 4 for the last a list shows.
    page: int = Field(ge=0, le=4)


class WebLinksAdd(BaseModel):
    model_config = ConfigDict(extra="forbid")

    urls: list[WebLink] = Field(min_length=1, max_length=MAX_LINKS)


class WebLinkDuplicate(BaseModel):
    url: str
    document_id: int


class WebLinkRejected(BaseModel):
    url: str
    reason: Fit


class WebLinksOutcome(BaseModel):
    created: list[DocumentRead]
    duplicates: list[WebLinkDuplicate]
    rejected: list[WebLinkRejected]
