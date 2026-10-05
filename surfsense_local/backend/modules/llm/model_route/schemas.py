import base64
import enum
from typing import Annotated, Any

from pydantic import BaseModel, Field

from modules.llm.admission.pool import Priority
from modules.llm.providers.types import Image, Message


class ModelRef(BaseModel):
    """A text model by what identifies it, selected now or not."""

    provider: str
    name: str
    connection_id: int | None = None


class RouteImage(BaseModel):
    mime: str
    # Base64, so a message's images travel in JSON.
    data: str


class RouteMessage(BaseModel):
    role: str
    content: str
    images: list[RouteImage] = []

    def as_message(self) -> Message:
        return Message(
            role=self.role,
            content=self.content,
            images=tuple(
                Image(mime=image.mime, data=base64.b64decode(image.data))
                for image in self.images
            ),
        )


class RouteClass(enum.StrEnum):
    """Who is asking, which sets their place in line for the local runtime.

    Interactive work runs in the API and never comes through the route.
    """

    BACKGROUND = "background"

    def priority(self) -> Priority:
        return Priority.BACKGROUND


class GenerateRequest(BaseModel):
    """What `Generator.chat` takes, plus the model and who is asking.

    `model` left out means the current selection.
    """

    model: ModelRef | None = None
    messages: Annotated[list[RouteMessage], Field(min_length=1)]
    max_tokens: Annotated[int, Field(gt=0)] | None = None
    temperature: float | None = None
    reasoning: bool | None = None
    json_schema: dict[str, Any] | None = None
    priority: RouteClass = RouteClass.BACKGROUND
